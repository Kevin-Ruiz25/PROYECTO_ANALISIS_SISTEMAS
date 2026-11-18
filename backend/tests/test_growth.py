from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import growth
from app.main import app


# ---------- Cálculo (valores de las tablas oficiales de la OMS)
def test_mediana_al_nacer_es_percentil_50():
    assert growth.percentile("weight", "M", 0, 3.3464) == pytest.approx(50.0, abs=0.1)
    assert growth.percentile("weight", "F", 0, 3.2322) == pytest.approx(50.0, abs=0.1)
    assert growth.percentile("height", "M", 0, 49.8842) == pytest.approx(50.0, abs=0.1)


def test_menos_2_desviaciones_es_aprox_percentil_2_3():
    # Niña al nacer: -2 DE de peso ≈ 2.4 kg
    p = growth.percentile("weight", "F", 0, 2.4)
    assert 1.5 < p < 3.5


def test_peso_bajo_y_alto():
    assert growth.percentile("weight", "M", 12, 6.0) < 5      # muy bajo a los 12 meses
    assert growth.percentile("weight", "M", 12, 13.0) > 95    # muy alto a los 12 meses


def test_fuera_de_rango_devuelve_none():
    assert growth.percentile("weight", "M", 61, 18) is None
    assert growth.percentile("weight", "M", -1, 3) is None


def test_escalon_longitud_talla_a_los_24_meses():
    antes = growth.lms_at("height", "M", 23.99)[1]
    despues = growth.lms_at("height", "M", 24.0)[1]
    assert antes - despues == pytest.approx(0.7, abs=0.15)  # convención OMS: 0.7 cm


@pytest.mark.parametrize("sex", ["M", "F"])
def test_curvas_ordenadas(sex):
    ref = growth.reference_curves(sex)
    for ind in ("weight", "height"):
        assert len(ref[ind]) == 61
        for r in ref[ind]:
            assert r["p5"] < r["p25"] < r["p50"] < r["p75"] < r["p95"]
        assert ref[ind][12]["p50"] > ref[ind][1]["p50"]


# ---------- API
def _login(c):
    r = c.post("/api/auth/login", data={"username": "admin@sccvi.org", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_api_crecimiento():
    with TestClient(app) as c:
        h = _login(c)
        birth = date.today() - timedelta(days=240)  # ~7.9 meses
        child = c.post("/api/children", headers=h, json={
            "full_name": "Ana Prueba", "birth_date": birth.isoformat(), "sex": "F"}).json()
        url = f"/api/children/{child['id']}/growth"

        r = c.post(url, headers=h, json={"measured_on": date.today().isoformat(), "weight_kg": 7.9, "height_cm": 68})
        assert r.status_code == 201
        rec = r.json()
        assert 7 < rec["age_months"] < 9
        assert 20 < rec["weight_percentile"] < 80
        assert rec["height_percentile"] is not None

        # peso muy bajo
        low = c.post(url, headers=h, json={"measured_on": date.today().isoformat(), "weight_kg": 5.5, "height_cm": 66}).json()
        assert low["weight_percentile"] < 5

        # validaciones de fecha
        future = (date.today() + timedelta(days=1)).isoformat()
        assert c.post(url, headers=h, json={"measured_on": future, "weight_kg": 8, "height_cm": 68}).status_code == 422
        before = (birth - timedelta(days=1)).isoformat()
        assert c.post(url, headers=h, json={"measured_on": before, "weight_kg": 8, "height_cm": 68}).status_code == 422
        # valores imposibles
        assert c.post(url, headers=h, json={"measured_on": date.today().isoformat(), "weight_kg": 800, "height_cm": 68}).status_code == 422

        assert len(c.get(url, headers=h).json()) == 2

        # cambiar el sexo recalcula los percentiles guardados
        before_p = c.get(url, headers=h).json()[0]["weight_percentile"]
        c.patch(f"/api/children/{child['id']}", headers=h, json={"sex": "M"})
        after_p = c.get(url, headers=h).json()[0]["weight_percentile"]
        assert before_p != after_p

        # referencia y borrado
        ref = c.get("/api/growth/reference?sex=M", headers=h).json()
        assert len(ref["weight"]) == 61
        assert c.delete(f"/api/growth/{rec['id']}", headers=h).status_code == 204
        assert len(c.get(url, headers=h).json()) == 1
        assert c.get("/api/growth/reference?sex=M").status_code == 401
