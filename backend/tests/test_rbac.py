def _token(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def test_viewer_can_list_users(client, seeded):
    token = _token(client, "viewer", "viewer123")
    resp = client.get("/api/v1/users", headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_viewer_cannot_create_user(client, seeded):
    token = _token(client, "viewer", "viewer123")
    resp = client.post(
        "/api/v1/users",
        headers={"Authorization": "Bearer " + token},
        json={"username": "newbie", "password": "secret123"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 10403


def test_admin_can_create_user_then_login(client, seeded):
    token = _token(client, "admin", "admin123")
    resp = client.post(
        "/api/v1/users",
        headers={"Authorization": "Bearer " + token},
        json={"username": "newbie", "password": "secret123", "real_name": "新人"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["username"] == "newbie"
    login = client.post("/api/v1/auth/login", json={"username": "newbie", "password": "secret123"})
    assert login.status_code == 200


def test_permissions_endpoint_requires_perm(client, seeded):
    token = _token(client, "viewer", "viewer123")
    resp = client.get("/api/v1/permissions", headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 403
