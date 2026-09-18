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
