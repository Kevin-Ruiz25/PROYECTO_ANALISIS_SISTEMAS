import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_flujo_completo():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", data={"username": "admin@sccvi.org", "password": "Admin1234!"})
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        assert c.get("/api/communities").status_code == 401

        com = c.post("/api/communities", headers=h, json={"name": "Aldea Test", "estimated_families": 40}).json()
        par = c.post("/api/parents", headers=h, json={
            "full_name": "María López", "dpi": "1234567890101", "email": "maria@correo.org",
            "community_id": com["id"]}).json()
        ch = c.post("/api/children", headers=h, json={
            "full_name": "Juan Pérez", "birth_date": "2024-03-10", "sex": "M",
            "community_id": com["id"], "parent_ids": [par["id"]]})
        assert ch.status_code == 201
        assert ch.json()["parents"][0]["full_name"] == "María López"

        assert c.get("/api/children?q=juan", headers=h).json()[0]["full_name"] == "Juan Pérez"
        assert c.delete(f"/api/communities/{com['id']}", headers=h).status_code == 409
