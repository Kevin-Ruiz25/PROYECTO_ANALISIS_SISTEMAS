from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import vaccination
from app.main import app


def test_add_months_casos_borde():
    assert vaccination.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert vaccination.add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert vaccination.add_months(date(2025, 11, 15), 2) == date(2026, 1, 15)
    assert vaccination.add_months(date(2026, 5, 10), 0) == date(2026, 5, 10)
    assert vaccination.add_months(date(2026, 5, 10), 48) == date(2030, 5, 10)


def test_estados():
    due = date(2026, 6, 1)
    assert vaccination.card_status(due, date(2026, 6, 3), today=date(2026, 9, 1)) == "completa"
    assert vaccination.card_status(due, None, today=date(2026, 5, 31)) == "proxima"
    assert vaccination.card_status(due, None, today=date(2026, 6, 1)) == "pendiente"
    assert vaccination.card_status(due, None, today=date(2026, 7, 1)) == "pendiente"
    assert vaccination.card_status(due, None, today=date(2026, 7, 2)) == "atrasada"


def _login(c, email="admin@sccvi.org", password="Admin1234!"):
    r = c.post("/api/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _find(card, name, dose):
    return next(i for i in card["items"] if i["vaccine"]["name"] == name and i["vaccine"]["dose_number"] == dose)


def test_catalogo_inicial_y_permisos():
    with TestClient(app) as c:
        admin = _login(c)
        vaccines = c.get("/api/vaccines", headers=admin).json()
        assert len(vaccines) == 23
        assert vaccines[0]["recommended_age_months"] == 0

        c.post("/api/auth/users", headers=admin, json={
            "email": "enfermera@sccvi.org", "full_name": "Enf. Prueba", "password": "Clave12345", "role": "health_staff"})
        staff = _login(c, "enfermera@sccvi.org", "Clave12345")
        assert c.get("/api/vaccines", headers=staff).status_code == 200
        new = {"name": "Vacuna Nueva", "recommended_age_months": 9, "dose_number": 1}
        assert c.post("/api/vaccines", headers=staff, json=new).status_code == 403

        created = c.post("/api/vaccines", headers=admin, json=new)
        assert created.status_code == 201
        assert c.post("/api/vaccines", headers=admin, json=new).status_code == 409
        vid = created.json()["id"]
        assert c.put(f"/api/vaccines/{vid}", headers=admin, json={**new, "recommended_age_months": 10}).json()["recommended_age_months"] == 10
        assert c.delete(f"/api/vaccines/{vid}", headers=admin).status_code == 204


def test_carnet_de_vacunacion():
    with TestClient(app) as c:
        h = _login(c)
        birth = date.today() - timedelta(days=210)
        cid = c.post("/api/children", headers=h, json={
            "full_name": "Luis Vacunas", "birth_date": birth.isoformat(), "sex": "M"}).json()["id"]

        card = c.get(f"/api/children/{cid}/vaccination-card", headers=h).json()
        s = card["summary"]
        assert s["total"] == 23 and s["completa"] == 0
        assert s["completa"] + s["atrasada"] + s["pendiente"] + s["proxima"] == s["total"]
        assert _find(card, "Hepatitis B", 1)["status"] == "atrasada"
        assert _find(card, "Rotavirus", 2)["status"] == "atrasada"
        assert _find(card, "Pentavalente / Hexavalente", 4)["status"] == "proxima"

        rota1 = _find(card, "Rotavirus", 1)["vaccine"]["id"]
        applied = (birth + timedelta(days=65)).isoformat()
        r = c.post(f"/api/children/{cid}/vaccinations", headers=h, json={"vaccine_id": rota1, "applied_on": applied})
        assert r.status_code == 201
        assert r.json()["status"] == "completa"
        assert r.json()["next_dose_on"] is not None

        card = c.get(f"/api/children/{cid}/vaccination-card", headers=h).json()
        assert _find(card, "Rotavirus", 1)["status"] == "completa"
        assert card["summary"]["completa"] == 1

        assert c.post(f"/api/children/{cid}/vaccinations", headers=h, json={"vaccine_id": rota1, "applied_on": applied}).status_code == 409
        other = _find(card, "BCG (tuberculosis)", 1)["vaccine"]["id"]
        future = (date.today() + timedelta(days=1)).isoformat()
        assert c.post(f"/api/children/{cid}/vaccinations", headers=h, json={"vaccine_id": other, "applied_on": future}).status_code == 422
        before = (birth - timedelta(days=1)).isoformat()
        assert c.post(f"/api/children/{cid}/vaccinations", headers=h, json={"vaccine_id": other, "applied_on": before}).status_code == 422
        assert c.post(f"/api/children/{cid}/vaccinations", headers=h, json={"vaccine_id": 99999, "applied_on": applied}).status_code == 422

        assert c.delete(f"/api/vaccines/{rota1}", headers=h).status_code == 409

        c.delete(f"/api/vaccinations/{r.json()['id']}", headers=h)
        card = c.get(f"/api/children/{cid}/vaccination-card", headers=h).json()
        assert _find(card, "Rotavirus", 1)["status"] == "atrasada"


def test_ultima_dosis_de_la_serie_no_sugiere_siguiente():
    with TestClient(app) as c:
        h = _login(c)
        birth = date.today() - timedelta(days=1900)
        cid = c.post("/api/children", headers=h, json={
            "full_name": "Sofía Cinco", "birth_date": birth.isoformat(), "sex": "F"}).json()["id"]
        card = c.get(f"/api/children/{cid}/vaccination-card", headers=h).json()
        dpt = _find(card, "DPT", 1)["vaccine"]["id"]
        r = c.post(f"/api/children/{cid}/vaccinations", headers=h, json={
            "vaccine_id": dpt, "applied_on": (birth + timedelta(days=1500)).isoformat()})
        assert r.status_code == 201 and r.json()["next_dose_on"] is None
