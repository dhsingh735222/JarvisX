import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_login_and_chat_without_key(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_me = client.get("/api/auth/me", headers=headers)
    assert resp_me.status_code == 200
    assert resp_me.json()["username"] == "alice"

    resp_chat = client.post("/api/chat", json={"message": "hi"}, headers=headers)
    assert resp_chat.status_code == 200
    data = resp_chat.json()
    assert "No API key configured" in data["messages"][0]["content"]


def test_settings_api_key_roundtrip(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_put = client.put("/api/settings/api-keys", json={"provider": "anthropic", "value": "sk-ant-test123"}, headers=headers)
    assert resp_put.status_code == 200
    assert resp_put.json()["configured"] is True

    resp_settings = client.get("/api/settings", headers=headers)
    keys = {k["provider"]: k["configured"] for k in resp_settings.json()["api_keys"]}
    assert keys["anthropic"] is True


def test_conversations_crud(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_create = client.post("/api/conversations", headers=headers)
    assert resp_create.status_code == 200
    convo_id = resp_create.json()["id"]

    resp_list = client.get("/api/conversations", headers=headers)
    assert any(c["id"] == convo_id for c in resp_list.json())

    resp_get = client.get(f"/api/conversations/{convo_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["messages"] == []

    resp_delete = client.delete(f"/api/conversations/{convo_id}", headers=headers)
    assert resp_delete.status_code == 204
