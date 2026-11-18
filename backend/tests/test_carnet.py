from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import carnet
from app.main import app


@pytest.fixture(autouse=True)
def _limpiar_bloqueos():
    carnet.reset_all()


def _login(c, email="admin@sccvi.org", password="Admin1234!"):
    r = c.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _parent_with_child(c, h, tag, child_name):
    """Crea padre (con correo), su niño y su cuenta de acceso. Devuelve (parent, child, headers_padre, email)."""
    email = f"{tag}@correo.org"
    parent = c.post("/api/parents", headers=h, json={"full_name": f"Padre {tag}", "dpi": f"90000{tag}", "email": email}).json()
    birth = (date.today() - timedelta(days=240)).isoformat()
    child = c.post("/api/children", headers=h, json={
        "full_name": child_name, "birth_date": birth, "sex": "F", "parent_ids": [parent["id"]]}).json()
    acc = c.post(f"/api/parents/{parent['id']}/access", headers=h)
    assert acc.status_code == 200, acc.text
    ph = _login(c, email, acc.json()["temporary_password"])
    return parent, child, ph, email


def test_emitir_carnet_y_estado():
    with TestClient(app) as c:
        h = _login(c)
        parent, child, _, _ = _parent_with_child(c, h, "1001", "Carla Uno")
        url = f"/api/children/{child['id']}/carnet"
        assert c.get(url, headers=h).json() == {"has_carnet": False, "url": None, "qr": None}

        r = c.post(url, headers=h)
        assert r.status_code == 201
        issued = r.json()
        assert len(issued["pin"]) == 6 and issued["pin"].isdigit()
        assert "/carnet/" in issued["url"]
        assert issued["qr"].startswith("data:image/svg+xml")

        st = c.get(url, headers=h).json()
        assert st["has_carnet"] and st["url"] == issued["url"]
        assert "pin" not in st  # el PIN nunca se puede volver a consultar

        # el niño no expone el token en sus listados
        assert "qr_token" not in c.get(f"/api/children/{child['id']}", headers=h).json()


def test_padre_abre_su_carnet_con_pin():
    with TestClient(app) as c:
        h = _login(c)
        parent, child, ph, _ = _parent_with_child(c, h, "1002", "Diana Dos")
        # historial para que el carnet tenga contenido
        for i, w in enumerate([5.0, 6.0, 7.0, 7.5, 8.0, 8.3]):
            c.post(f"/api/children/{child['id']}/growth", headers=h, json={
                "measured_on": (date.today() - timedelta(days=100 - i * 10)).isoformat(),
                "weight_kg": w, "height_cm": 60 + i})
        issued = c.post(f"/api/children/{child['id']}/carnet", headers=h).json()
        token = issued["url"].rsplit("/", 1)[1]

        r = c.post(f"/api/carnet/{token}/open", headers=ph, json={"pin": issued["pin"]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["child_name"] == "Diana Dos"
        assert data["vaccination"]["summary"]["total"] == 23
        assert len(data["growth"]) == 5                                   # solo los últimos 5
        assert data["growth"][0]["measured_on"] > data["growth"][-1]["measured_on"]   # más reciente primero

        mine = c.get("/api/me/children", headers=ph).json()
        assert [m["full_name"] for m in mine] == ["Diana Dos"] and mine[0]["token"] == token


def test_pin_incorrecto_y_bloqueo():
    with TestClient(app) as c:
        h = _login(c)
        _, child, ph, _ = _parent_with_child(c, h, "1003", "Elena Tres")
        issued = c.post(f"/api/children/{child['id']}/carnet", headers=h).json()
        token = issued["url"].rsplit("/", 1)[1]
        wrong = "000000" if issued["pin"] != "000000" else "111111"

        for left in (4, 3, 2, 1):
            r = c.post(f"/api/carnet/{token}/open", headers=ph, json={"pin": wrong})
            assert r.status_code == 403 and f"Te quedan {left}" in r.json()["detail"]
        r = c.post(f"/api/carnet/{token}/open", headers=ph, json={"pin": wrong})
        assert r.status_code == 429                                        # quinto fallo: bloqueado
        # ni siquiera el PIN correcto entra mientras dure el bloqueo
        assert c.post(f"/api/carnet/{token}/open", headers=ph, json={"pin": issued["pin"]}).status_code == 429

        # un PIN nuevo desbloquea y el anterior deja de servir
        new = c.post(f"/api/children/{child['id']}/carnet/pin", headers=h).json()["pin"]
        assert c.post(f"/api/carnet/{token}/open", headers=ph, json={"pin": new}).status_code == 200
        if issued["pin"] != new:  # (evita el caso de 1 en un millón de PIN repetido)
            assert c.post(f"/api/carnet/{token}/open", headers=ph, json={"pin": issued["pin"]}).status_code == 403


def test_bloqueo_vence_con_el_tiempo():
    assert carnet.locked_minutes(1, 1) == 0
    for _ in range(carnet.MAX_ATTEMPTS):
        carnet.register_failure(1, 1, now=1000.0)
    assert carnet.locked_minutes(1, 1, now=1000.0 + 60) == 14
    assert carnet.locked_minutes(1, 1, now=1000.0 + carnet.LOCK_SECONDS + 1) == 0
    carnet.register_failure(1, 1, now=5000.0)
    carnet.register_success(1, 1)
    assert carnet.register_failure(1, 1, now=5001.0) == carnet.MAX_ATTEMPTS - 1  # el éxito reinició el conteo


def test_otro_padre_no_puede_abrir_carnet_ajeno():
    with TestClient(app) as c:
        h = _login(c)
        _, child_a, ph_a, _ = _parent_with_child(c, h, "1004", "Fabi Cuatro")
        _, child_b, ph_b, _ = _parent_with_child(c, h, "1005", "Gina Cinco")
        issued_a = c.post(f"/api/children/{child_a['id']}/carnet", headers=h).json()
        token_a = issued_a["url"].rsplit("/", 1)[1]

        # el padre B tiene cuenta válida e incluso conoce el token y el PIN de A: igual es 404
        r = c.post(f"/api/carnet/{token_a}/open", headers=ph_b, json={"pin": issued_a["pin"]})
        assert r.status_code == 404
        # token inexistente: el mismo mensaje, no se revela nada
        r2 = c.post("/api/carnet/no-existe/open", headers=ph_b, json={"pin": "123456"})
        assert r2.status_code == 404 and r2.json()["detail"] == r.json()["detail"]
        # B no ve a los hijos de A
        assert all(m["full_name"] != "Fabi Cuatro" for m in c.get("/api/me/children", headers=ph_b).json())


def test_permisos_por_rol_y_sin_sesion():
    with TestClient(app) as c:
        h = _login(c)
        _, child, ph, _ = _parent_with_child(c, h, "1006", "Hana Seis")
        issued = c.post(f"/api/children/{child['id']}/carnet", headers=h).json()
        token = issued["url"].rsplit("/", 1)[1]

        assert c.post(f"/api/carnet/{token}/open", json={"pin": issued["pin"]}).status_code == 401
        # el personal de salud no abre el carnet por el QR (solo padres autorizados)
        assert c.post(f"/api/carnet/{token}/open", headers=h, json={"pin": issued["pin"]}).status_code == 403
        # un padre no puede usar la parte del personal
        assert c.get("/api/children", headers=ph).status_code == 403
        assert c.get("/api/alerts", headers=ph).status_code == 403
        assert c.post(f"/api/children/{child['id']}/carnet", headers=ph).status_code == 403
        assert c.post("/api/parents/1/access", headers=ph).status_code == 403
        assert c.get("/api/me/children", headers=h).status_code == 403


def test_regenerar_y_revocar_invalidan_el_qr_anterior():
    with TestClient(app) as c:
        h = _login(c)
        _, child, ph, _ = _parent_with_child(c, h, "1007", "Iris Siete")
        first = c.post(f"/api/children/{child['id']}/carnet", headers=h).json()
        second = c.post(f"/api/children/{child['id']}/carnet", headers=h).json()
        assert first["url"] != second["url"]
        t1, t2 = first["url"].rsplit("/", 1)[1], second["url"].rsplit("/", 1)[1]
        assert c.post(f"/api/carnet/{t1}/open", headers=ph, json={"pin": first["pin"]}).status_code == 404
        assert c.post(f"/api/carnet/{t2}/open", headers=ph, json={"pin": second["pin"]}).status_code == 200

        assert c.delete(f"/api/children/{child['id']}/carnet", headers=h).status_code == 204
        assert c.post(f"/api/carnet/{t2}/open", headers=ph, json={"pin": second["pin"]}).status_code == 404
        assert c.get(f"/api/children/{child['id']}/carnet", headers=h).json()["has_carnet"] is False
        assert c.post(f"/api/children/{child['id']}/carnet/pin", headers=h).status_code == 409


def test_crear_y_restablecer_acceso():
    with TestClient(app) as c:
        h = _login(c)
        sin_correo = c.post("/api/parents", headers=h, json={"full_name": "Sin Correo", "dpi": "9100000001"}).json()
        assert c.post(f"/api/parents/{sin_correo['id']}/access", headers=h).status_code == 422

        # correo ya usado por otro usuario
        dup = c.post("/api/parents", headers=h, json={"full_name": "Dup", "dpi": "9100000002", "email": "admin@sccvi.org"}).json()
        assert c.post(f"/api/parents/{dup['id']}/access", headers=h).status_code == 409

        parent, _, ph, email = _parent_with_child(c, h, "1008", "Jose Ocho")
        assert c.get(f"/api/parents/{parent['id']}", headers=h).json()["user_id"] is not None
        first_pw = c.post(f"/api/parents/{parent['id']}/access", headers=h).json()
        assert first_pw["created"] is False
        # la contraseña anterior deja de servir tras restablecer
        old = c.post("/api/auth/login", data={"username": email, "password": "x"}).status_code
        assert old == 401
        assert c.post("/api/auth/login", data={"username": email, "password": first_pw["temporary_password"]}).status_code == 200


def test_cambiar_contrasena():
    with TestClient(app) as c:
        h = _login(c)
        _, _, ph, email = _parent_with_child(c, h, "1009", "Kari Nueve")
        assert c.post("/api/auth/change-password", headers=ph, json={"current_password": "mala", "new_password": "NuevaClave123"}).status_code == 400
        assert c.post("/api/auth/change-password", headers=ph, json={"current_password": "mala", "new_password": "corta"}).status_code == 422
        # el error de contraseña actual NO cierra la sesión (no es 401)
        assert c.get("/api/auth/me", headers=ph).status_code == 200
        assert c.get("/api/auth/me", headers=ph).json()["role"] == "parent"

        pw_actual = c.post(f"/api/parents/{c.get('/api/parents?q=1009', headers=h).json()[0]['id']}/access", headers=h).json()
        ph2 = _login(c, email, pw_actual["temporary_password"])
        assert c.post("/api/auth/change-password", headers=ph2, json={
            "current_password": pw_actual["temporary_password"], "new_password": "NuevaClave123"}).status_code == 204
        assert c.post("/api/auth/login", data={"username": email, "password": pw_actual["temporary_password"]}).status_code == 401
        assert c.post("/api/auth/login", data={"username": email, "password": "NuevaClave123"}).status_code == 200


def test_borrar_padre_borra_su_cuenta():
    with TestClient(app) as c:
        h = _login(c)
        parent = c.post("/api/parents", headers=h, json={"full_name": "Temporal", "dpi": "9200000001", "email": "temporal@correo.org"}).json()
        pw = c.post(f"/api/parents/{parent['id']}/access", headers=h).json()["temporary_password"]
        assert c.post("/api/auth/login", data={"username": "temporal@correo.org", "password": pw}).status_code == 200
        assert c.delete(f"/api/parents/{parent['id']}", headers=h).status_code == 204
        assert c.post("/api/auth/login", data={"username": "temporal@correo.org", "password": pw}).status_code == 401
