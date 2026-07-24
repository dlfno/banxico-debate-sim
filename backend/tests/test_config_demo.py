"""Tests del endpoint público /api/config y del acceso de invitado /api/auth/demo."""
from __future__ import annotations


def test_config_public_defaults(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["demo_mode"] is False
    assert data["allow_registration"] is True


def test_demo_login_forbidden_without_demo_mode(client):
    res = client.post("/api/auth/demo")
    assert res.status_code == 403


def test_demo_login_creates_guest(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_MODE", True)

    res = client.post("/api/auth/demo")
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["token"]
    assert data["user"]["username"].startswith("invitado-")

    # El token emitido debe funcionar contra un endpoint autenticado.
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == data["user"]["username"]

    # Dos invitados sucesivos no colisionan en username.
    res2 = client.post("/api/auth/demo")
    assert res2.status_code == 201
    assert res2.json()["user"]["username"] != data["user"]["username"]


def test_config_reflects_demo_mode(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_MODE", True)
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["demo_mode"] is True
    # En demo el registro se reporta cerrado aunque ALLOW_REGISTRATION sea true.
    assert data["allow_registration"] is False


def test_register_blocked_in_demo_mode(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_MODE", True)
    res = client.post(
        "/api/auth/register",
        json={"username": "colado", "display_name": "Colado", "password": "secret123"},
    )
    assert res.status_code == 403
