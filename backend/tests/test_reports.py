import itertools
from datetime import date, timedelta
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import mailer
from app.main import app


def _login(c, email="admin@sccvi.org", pw="Admin1234!"):
    r = c.post("/api/auth/login", data={"username": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


_n = itertools.count(1)


def _setup(c, h):
    """Dos comunidades: Norte (bajo peso, sobrepeso) y Sur (niño sin controles ni vacunas)."""
    n = next(_n)
    norte = c.post("/api/communities", headers=h, json={"name": f"Aldea Norte R{n}"}).json()
    sur = c.post("/api/communities", headers=h, json={"name": f"Aldea Sur R{n}"}).json()
    mom = c.post("/api/parents", headers=h, json={"full_name": "Mamá Rep", "dpi": f"20000000{n:03d}01",
                                                  "email": f"rep{n}@correo.org", "community_id": norte["id"]}).json()
    nomail = c.post("/api/parents", headers=h, json={"full_name": "Papá Sin Correo", "dpi": f"20000000{n:03d}02",
                                                     "community_id": sur["id"]}).json()

    def child(name, days, sex, com, parents):
        return c.post("/api/children", headers=h, json={
            "full_name": name, "birth_date": (date.today() - timedelta(days=days)).isoformat(), "sex": sex,
            "community_id": com["id"], "parent_ids": [p["id"] for p in parents]}).json()

    flaco = child("Rep Flaca", 240, "F", norte, [mom])
    gordo = child("Rep Gordo", 365, "M", norte, [mom])        # misma madre: un solo aviso
    solo = child("Rep Sur", 300, "M", sur, [nomail])
    c.post(f"/api/children/{flaco['id']}/growth", headers=h,
           json={"measured_on": date.today().isoformat(), "weight_kg": 5.5, "height_cm": 66})
    c.post(f"/api/children/{gordo['id']}/growth", headers=h,
           json={"measured_on": date.today().isoformat(), "weight_kg": 13.5, "height_cm": 76})
    return norte, sur, flaco, gordo, solo, n


def test_requiere_rol_de_encargado():
    with TestClient(app) as c:
        h = _login(c)
        assert c.get("/api/reports/summary").status_code == 401
        c.post("/api/auth/users", headers=h, json={"email": "enf-reportes@sccvi.org", "full_name": "Enf",
                                                    "password": "Enfermera123", "role": "health_staff"})
        hs = _login(c, "enf-reportes@sccvi.org", "Enfermera123")
        assert c.get("/api/reports/summary", headers=hs).status_code == 403
        assert c.post("/api/campaigns/send", headers=hs, json={}).status_code in (403, 422)
        assert c.post("/api/campaigns/preview", headers=hs, json={}).status_code == 403


def test_reportes_de_peso_vacunas_cobertura_y_crecimiento():
    with TestClient(app) as c:
        h = _login(c)
        norte, sur, flaco, gordo, solo, n = _setup(c, h)

        s = c.get("/api/reports/summary", headers=h).json()
        assert s["low_weight"] >= 1 and s["high_weight"] >= 1 and s["children"] >= 3

        low = c.get("/api/reports/bajo-peso", headers=h).json()
        assert "Rep Flaca" in [r["name"] for r in low["rows"]]
        assert "Rep Gordo" not in [r["name"] for r in low["rows"]]
        hi = c.get("/api/reports/sobrepeso", headers=h).json()
        assert "Rep Gordo" in [r["name"] for r in hi["rows"]]

        # filtro por comunidad
        sur_low = c.get(f"/api/reports/bajo-peso?community_id={sur['id']}", headers=h).json()
        assert sur_low["rows"] == []

        inc = c.get(f"/api/reports/vacunas-incompletas?community_id={sur['id']}", headers=h).json()
        assert [r["name"] for r in inc["rows"]] == ["Rep Sur"]
        assert inc["rows"][0]["doses_overdue"] > 0

        cov = c.get("/api/reports/cobertura", headers=h).json()
        rows = {r["community"]: r for r in cov["rows"]}
        assert rows[f"Aldea Sur R{n}"]["children"] == 1 and rows[f"Aldea Sur R{n}"]["coverage"] == 0.0
        assert rows[f"Aldea Sur R{n}"]["up_to_date_pct"] == 0.0
        assert cov["rows"][-1]["community"] == "TOTAL"

        g = {r["community"]: r for r in c.get("/api/reports/crecimiento", headers=h).json()["rows"]}
        assert g[f"Aldea Norte R{n}"]["measured"] == 2 and g[f"Aldea Norte R{n}"]["low"] == 1 and g[f"Aldea Norte R{n}"]["high"] == 1
        assert g[f"Aldea Sur R{n}"]["measured"] == 0 and g[f"Aldea Sur R{n}"]["avg_weight"] is None
        assert c.get("/api/reports/crecimiento-edad", headers=h).json()["rows"]
        assert c.get("/api/reports/inexistente", headers=h).status_code == 404


def test_exportar_excel_y_pdf():
    with TestClient(app) as c:
        h = _login(c)
        _setup(c, h)
        for kind in ("bajo-peso", "sobrepeso", "vacunas-incompletas", "cobertura", "crecimiento", "crecimiento-edad"):
            x = c.get(f"/api/reports/{kind}/export?format=xlsx", headers=h)
            assert x.status_code == 200 and f"sccvi-{kind}" in x.headers["content-disposition"]
            assert load_workbook(BytesIO(x.content)).active.max_row >= 4
            p = c.get(f"/api/reports/{kind}/export?format=pdf", headers=h)
            assert p.status_code == 200 and p.content.startswith(b"%PDF")
        ws = load_workbook(BytesIO(c.get("/api/reports/bajo-peso/export?format=xlsx", headers=h).content)).active
        assert ws["A4"].value == "Niño"
        assert "Rep Flaca" in [ws.cell(row=r, column=1).value for r in range(5, ws.max_row + 1)]
        assert c.get("/api/reports/cobertura/export?format=doc", headers=h).status_code == 422


def test_campana_filtra_y_envia_un_aviso_por_padre(monkeypatch):
    sent = []
    def fake_send(to, subject, body):
        if subject.startswith("SCCVI: Jornada"):   # ignora avisos de alertas de otras pruebas
            sent.append((to, subject, body))
        return "enviada"
    monkeypatch.setattr(mailer, "send_email", fake_send)
    monkeypatch.setattr(mailer, "mode", lambda: "smtp")
    with TestClient(app) as c:
        h = _login(c)
        norte, sur, flaca, gordo, solo, n = _setup(c, h)

        f = {"community_ids": [norte["id"]], "age_min_months": 0, "age_max_months": 24, "vaccination": "todos"}
        pv = c.post("/api/campaigns/preview", headers=h, json=f).json()
        assert pv["children"] == 2 and pv["parents"] == 1 and pv["with_email"] == 1   # una madre, dos hijos

        # filtro por edad: solo el de ~8 meses
        young = c.post("/api/campaigns/preview", headers=h, json={**f, "age_max_months": 9}).json()
        assert [x["name"] for x in young["sample"]] == ["Rep Flaca"]

        # al día: nadie en esta base de pruebas cumple (todos tienen dosis atrasadas)
        assert c.post("/api/campaigns/preview", headers=h, json={**f, "vaccination": "al_dia"}).json()["children"] == 0
        # por vacuna concreta
        names = c.get("/api/campaigns/vaccine-names", headers=h).json()
        assert names
        vac = c.post("/api/campaigns/preview", headers=h,
                     json={**f, "vaccination": "atrasadas", "vaccine_name": names[0]}).json()
        assert vac["children"] <= 2
        bad = c.post("/api/campaigns/preview", headers=h, json={**f, "age_min_months": 30, "age_max_months": 10})
        assert bad.status_code == 422

        body = {**f, "vaccination": "atrasadas", "title": "Jornada de vacunación",
                "message": "Los invitamos a la jornada de vacunación de su comunidad.",
                "event_date": "2030-01-15", "place": "Salón comunal"}
        r = c.post("/api/campaigns/send", headers=h, json=body).json()
        assert r["parents"] == 1 and r["created"] == 1 and r["envio"]["enviadas"] >= 1
        assert len(sent) == 1
        to, subject, text = sent[0]
        assert to == f"rep{n}@correo.org" and subject == "SCCVI: Jornada de vacunación"
        assert "Rep Flaca" in text and "Rep Gordo" in text and "15/01/2030" in text and "Salón comunal" in text

        # padre sin correo: se registra como sin contacto y no se pierde
        r2 = c.post("/api/campaigns/send", headers=h, json={**body, "community_ids": [sur["id"]]}).json()
        assert r2["created"] == 1 and r2["without_contact"] == 1 and len(sent) == 1

        # sin destinatarios
        none = c.post("/api/campaigns/send", headers=h, json={**body, "vaccination": "al_dia"})
        assert none.status_code == 422
