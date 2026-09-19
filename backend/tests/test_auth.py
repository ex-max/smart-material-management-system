def _login(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["trace_id"]


def test_login_success_and_me(client, seeded):
    resp = _login(client, "admin", "admin123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    token = body["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "admin"


def test_login_wrong_password(client, seeded):
    resp = _login(client, "admin", "bad-password")
    assert resp.status_code == 400
    assert resp.json()["code"] != 0


def test_me_requires_token(client, seeded):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_login_returns_role_permissions(client, seeded):
    user = _login(client, "viewer", "viewer123").json()["data"]["user"]
    assert user["is_superuser"] is False
    assert "user:view" in user["permissions"]
    assert "user:create" not in user["permissions"]


def test_me_superuser_gets_all_permissions(client, seeded):
    token = _login(client, "admin", "admin123").json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    data = me.json()["data"]
    assert data["is_superuser"] is True
    assert {"user:view", "user:create"} <= set(data["permissions"])
