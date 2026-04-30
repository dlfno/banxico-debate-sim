def test_register_and_me(client):
    res = client.post(
        "/api/auth/register",
        json={"username": "alice", "display_name": "Alice", "password": "secret123"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["display_name"] == "Alice"
    token = body["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_register_duplicate_username(client):
    payload = {"username": "bob", "display_name": "Bob", "password": "secret123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


def test_login_success_and_failure(client):
    client.post(
        "/api/auth/register",
        json={"username": "carol", "display_name": "Carol", "password": "secret123"},
    )
    ok = client.post("/api/auth/login", json={"username": "carol", "password": "secret123"})
    assert ok.status_code == 200
    assert "token" in ok.json()

    bad = client.post("/api/auth/login", json={"username": "carol", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_chat_session_requires_auth(client):
    res = client.post("/api/chat/sessions", json={"agent_id": 1})
    assert res.status_code == 401


def test_chat_session_with_auth(client, auth_headers):
    res = client.post("/api/chat/sessions", json={"agent_id": 1}, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["agent_id"] == 1
    assert body["created_by"]["username"] == "tester"


def test_list_chat_sessions(client, auth_headers):
    client.post("/api/chat/sessions", json={"agent_id": 1}, headers=auth_headers)
    client.post("/api/chat/sessions", json={"agent_id": 2}, headers=auth_headers)
    res = client.get("/api/chat/sessions", headers=auth_headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    for item in items:
        assert item["created_by"]["username"] == "tester"
        assert "agent_name" in item
        assert "message_count" in item


def test_meetings_require_auth(client):
    assert client.get("/api/meetings").status_code == 401
    assert client.post("/api/meetings", json={"topic": "x", "rounds": 1}).status_code == 401
