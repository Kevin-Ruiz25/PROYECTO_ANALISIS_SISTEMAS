from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import config, mailer
from app.main import app


def _login(c):
    r = c.post("/api/auth/login", data={"username": "admin@sccvi.org", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _mk_parent(c, h, dpi, **extra):
    body = {"full_name": f"Padre {dpi}", "dpi": dpi, **extra}
    return c.post("/api/parents", headers=h, json=body).json()


def _mk_child(c, h, name, days_old, sex="F", parents=()):
    birth = (date.today() - timedelta(days=days_old)).isoformat()
    return c.post("/api/children", headers=h, json={
        "full_name": name, "birth_date": birth, "sex": sex, "parent_ids": [p["id"] for p in parents]}).json()


def _measure(c, h, child, weight, height, days_ago=0):
    on = (date.today() - timedelta(days=days_ago)).isoformat()
    r = c.post(f"/api/children/{child['id']}/growth", headers=h,
               json={"measured_on": on, "weight_kg": weight, "height_cm": height})
    assert r.status_code == 201, r.text
    return r.json()


def _open(c, h, child, status="open"):
    return {a["reason"]: a for a in c.get(f"/api/alerts?status={status}&child_id={child['id']}", headers=h).json()}


def test_requiere_autenticacion():
    with TestClient(app) as c:
        assert c.get("/api/alerts").status_code == 401
        assert c.post("/api/alerts/evaluate").status_code == 401
        assert c.get("/api/notifications").status_code == 401


def test_peso_bajo_es_critica_y_se_cierra_sola():
    with TestClient(app) as c:
        h = _login(c)
        mom = _mk_parent(c, h, "1000000000001", email="mama1@correo.org")
        child = _mk_child(c, h, "Ana Bajo", 240, "F", [mom])   # ~7.9 meses
        _measure(c, h, child, 5.5, 66)
        a = _open(c, h, child)
        assert a["peso_bajo"]["type"] == "critica"
        assert a["peso_bajo"]["message"].startswith("La niña Ana Bajo presenta peso bajo para su edad.")
        assert "acudir al centro de salud" in a["peso_bajo"]["message"]

        # un nuevo control normal cierra la alerta
        _measure(c, h, child, 7.9, 68)
        assert "peso_bajo" not in _open(c, h, child)
        assert "peso_bajo" in _open(c, h, child, "resolved")


def test_peso_alto_es_preventiva():
    with TestClient(app) as c:
        h = _login(c)
        child = _mk_child(c, h, "Beto Alto", 365, "M")
        _measure(c, h, child, 13.5, 76)
        a = _open(c, h, child)
        assert a["peso_alto"]["type"] == "preventiva"
        assert a["peso_alto"]["message"].startswith("El niño Beto Alto")


def test_sin_controles_por_edad():
    with TestClient(app) as c:
        h = _login(c)
        # menor de 2 años sin ningún control
        nuevo = _mk_child(c, h, "Sin Control Uno", 300, "M")
        assert _open(c, h, nuevo) == {}   # registrar al niño no dispara alertas por sí solo
        c.post("/api/alerts/evaluate", headers=h)
        assert "sin_controles" in _open(c, h, nuevo)
        # recién nacido (menos de 1 mes): todavía no se alerta
        rn = _mk_child(c, h, "Recien Nacido", 10, "F")
        # 2-5 años: control trimestral. Hace 5 meses -> alerta; hace 2 meses -> no.
        viejo = _mk_child(c, h, "Tres Años Viejo", 1100, "F")
        _measure(c, h, viejo, 13.5, 93, days_ago=150)
        c.post("/api/alerts/evaluate", headers=h)
        assert "sin_controles" in _open(c, h, viejo)
        reciente = _mk_child(c, h, "Tres Años Reciente", 1100, "F")
        _measure(c, h, reciente, 13.5, 93, days_ago=60)
        c.post("/api/alerts/evaluate", headers=h)
        assert "sin_controles" not in _open(c, h, reciente)
        assert "sin_controles" not in _open(c, h, rn)
        # menor de 2 años, control hace 3 meses -> alerta (mensual)
        bebe = _mk_child(c, h, "Bebe Tarde", 400, "M")
        _measure(c, h, bebe, 9.5, 74, days_ago=90)
        c.post("/api/alerts/evaluate", headers=h)
        assert "sin_controles" in _open(c, h, bebe)


def test_vacunas_atrasadas_y_escalada_a_critica():
    with TestClient(app) as c:
        h = _login(c)
        mom = _mk_parent(c, h, "1000000000002", email="mama2@correo.org")
        child = _mk_child(c, h, "Luz Vacunas", 210, "F", [mom])  # ~7 meses, muchas dosis atrasadas
        _measure(c, h, child, 7.5, 67)
        a = _open(c, h, child)["vacunas_atrasadas"]
        assert a["type"] == "critica" and "dosis de vacunas atrasadas" in a["message"]

        # cada aplicación reevalúa: al completar casi todo baja a preventiva y al final se cierra
        card = c.get(f"/api/children/{child['id']}/vaccination-card", headers=h).json()
        overdue = [i for i in card["items"] if i["status"] == "atrasada"]
        assert len(overdue) >= 3
        birth = date.today() - timedelta(days=210)
        for i in overdue[:-1]:
            c.post(f"/api/children/{child['id']}/vaccinations", headers=h,
                   json={"vaccine_id": i["vaccine"]["id"], "applied_on": (birth + timedelta(days=200)).isoformat()})
        assert _open(c, h, child)["vacunas_atrasadas"]["type"] == "preventiva"
        c.post(f"/api/children/{child['id']}/vaccinations", headers=h,
               json={"vaccine_id": overdue[-1]["vaccine"]["id"], "applied_on": (birth + timedelta(days=200)).isoformat()})
        assert "vacunas_atrasadas" not in _open(c, h, child)


def test_no_duplica_alertas_ni_notificaciones():
    with TestClient(app) as c:
        h = _login(c)
        mom = _mk_parent(c, h, "1000000000003", email="mama3@correo.org")
        child = _mk_child(c, h, "Dani Unico", 240, "M", [mom])
        _measure(c, h, child, 5.8, 66)
        before = len(c.get("/api/alerts?status=all&child_id=%d" % child["id"], headers=h).json())
        notif_before = len(c.get("/api/notifications?limit=1000", headers=h).json())
        for _ in range(3):
            assert c.post("/api/alerts/evaluate", headers=h).status_code == 200
        after = len(c.get("/api/alerts?status=all&child_id=%d" % child["id"], headers=h).json())
        assert before == after
        assert len(c.get("/api/notifications?limit=1000", headers=h).json()) == notif_before


def test_notificaciones_por_canal_y_envio_simulado(monkeypatch):
    sent = []
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.prueba.local")
    monkeypatch.setattr(mailer, "_smtp_send", lambda msg: sent.append(msg))
    with TestClient(app) as c:
        h = _login(c)
        con_correo = _mk_parent(c, h, "2000000000001", email="familia@correo.org")
        tg_sin_correo = _mk_parent(c, h, "2000000000002", preferred_channel="telegram")
        correo_vacio = _mk_parent(c, h, "2000000000003")  # prefiere email pero no lo registró
        child = _mk_child(c, h, "Eva Canales", 240, "F", [con_correo, tg_sin_correo, correo_vacio])
        _measure(c, h, child, 5.4, 66)   # genera alerta + notificaciones y las envía en segundo plano

        mine = [n for n in c.get("/api/notifications?limit=1000", headers=h).json() if n["child_id"] == child["id"]]
        by_parent = {n["parent_id"]: n for n in mine}
        statuses = {n["parent_id"]: n["status"] for n in mine}
        assert statuses[con_correo["id"]] == "enviada"
        assert statuses[tg_sin_correo["id"]] == "canal_no_disponible"
        assert statuses[correo_vacio["id"]] == "sin_contacto"
        assert any(m["To"] == "familia@correo.org" for m in sent)
        body = next(m for m in sent if m["To"] == "familia@correo.org").get_content()
        assert "La niña Eva Canales presenta peso bajo" in body
        assert by_parent[con_correo["id"]]["sent_at"] is not None


def test_fallo_de_envio_queda_en_error_y_se_reintenta(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.prueba.local")
    calls = {"fail": True}

    def flaky(msg):
        if calls["fail"]:
            raise ConnectionError("servidor caído")

    monkeypatch.setattr(mailer, "_smtp_send", flaky)
    with TestClient(app) as c:
        h = _login(c)
        mom = _mk_parent(c, h, "3000000000001", email="reintento@correo.org")
        child = _mk_child(c, h, "Flor Reintento", 240, "F", [mom])
        _measure(c, h, child, 5.4, 66)
        mine = [n for n in c.get("/api/notifications?limit=1000", headers=h).json() if n["child_id"] == child["id"]]
        assert mine and all(n["status"] == "error" for n in mine)

        calls["fail"] = False
        res = c.post("/api/notifications/dispatch", headers=h).json()
        assert res["enviadas"] >= 1
        mine = [n for n in c.get("/api/notifications?limit=1000", headers=h).json() if n["child_id"] == child["id"]]
        assert all(n["status"] == "enviada" for n in mine)


def test_sin_correo_configurado_quedan_pendientes_y_modo_consola(monkeypatch):
    with TestClient(app) as c:
        h = _login(c)
        assert c.get("/api/mail/status", headers=h).json()["mode"] == "none"
        mom = _mk_parent(c, h, "4000000000001", email="pend@correo.org")
        child = _mk_child(c, h, "Gael Pendiente", 240, "M", [mom])
        _measure(c, h, child, 5.6, 66)
        mine = [n for n in c.get("/api/notifications?limit=1000", headers=h).json() if n["child_id"] == child["id"]]
        assert mine and all(n["status"] == "pendiente" for n in mine)

        monkeypatch.setattr(config, "MAIL_MODE", "console")
        assert c.get("/api/mail/status", headers=h).json()["mode"] == "console"
        res = c.post("/api/notifications/dispatch", headers=h).json()
        assert res["simuladas"] >= 1
        mine = [n for n in c.get("/api/notifications?limit=1000", headers=h).json() if n["child_id"] == child["id"]]
        assert all(n["status"] == "simulada" for n in mine)


def test_borrar_nino_y_padre_con_notificaciones():
    with TestClient(app) as c:
        h = _login(c)
        mom = _mk_parent(c, h, "5000000000001", email="borrar@correo.org")
        child = _mk_child(c, h, "Hugo Borrar", 240, "M", [mom])
        _measure(c, h, child, 5.6, 66)
        assert c.delete(f"/api/children/{child['id']}", headers=h).status_code == 204
        assert c.delete(f"/api/parents/{mom['id']}", headers=h).status_code == 204
        assert not [n for n in c.get("/api/notifications?limit=1000", headers=h).json() if n["parent_id"] == mom["id"]]
