def _token(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _auth(token):
    return {"Authorization": "Bearer " + token}


def test_master_data_end_to_end(client, seeded):
    admin = _auth(_token(client, "admin", "admin123"))

    root = client.post("/api/v1/material-categories", headers=admin, json={"code": "C01", "name": "五金"}).json()["data"]
    assert root["level"] == 1
    assert root["path"].endswith("/")
    child = client.post(
        "/api/v1/material-categories",
        headers=admin,
        json={"code": "C0101", "name": "螺丝", "parent_id": root["id"]},
    ).json()["data"]
    assert child["level"] == 2

    unit = client.post("/api/v1/units", headers=admin, json={"code": "PCS", "name": "个"}).json()["data"]
    supplier = client.post(
        "/api/v1/suppliers", headers=admin, json={"code": "S01", "name": "供应商甲", "rating": "4.5"}
    ).json()["data"]
    wh = client.post("/api/v1/warehouses", headers=admin, json={"code": "WH01", "name": "主仓"}).json()["data"]
    loc = client.post(
        "/api/v1/locations", headers=admin, json={"warehouse_id": wh["id"], "code": "A-01", "zone": "A"}
    ).json()["data"]
    assert loc["warehouse_id"] == wh["id"]

    mat = client.post(
        "/api/v1/materials",
        headers=admin,
        json={
            "code": "M001",
            "name": "螺丝",
            "category_id": child["id"],
            "unit_id": unit["id"],
            "safety_stock": "10",
            "default_supplier_id": supplier["id"],
            "abc_class": "A",
        },
    ).json()["data"]
    assert mat["code"] == "M001"

    listed = client.get("/api/v1/materials", headers=admin).json()["data"]
    assert listed["total"] == 1
    assert client.get("/api/v1/materials/" + str(mat["id"]), headers=admin).json()["data"]["name"] == "螺丝"

    updated = client.put("/api/v1/materials/" + str(mat["id"]), headers=admin, json={"name": "螺丝-更新"}).json()["data"]
    assert updated["name"] == "螺丝-更新"

    assert client.delete("/api/v1/materials/" + str(mat["id"]), headers=admin).status_code == 200
    assert client.get("/api/v1/materials/" + str(mat["id"]), headers=admin).status_code == 404


def test_duplicate_code_conflict(client, seeded):
    admin = _auth(_token(client, "admin", "admin123"))
    assert client.post("/api/v1/units", headers=admin, json={"code": "KG", "name": "千克"}).status_code == 201
    dup = client.post("/api/v1/units", headers=admin, json={"code": "KG", "name": "千克二"})
    assert dup.status_code == 409
    assert dup.json()["code"] == 10409


def test_material_requires_valid_parents(client, seeded):
    admin = _auth(_token(client, "admin", "admin123"))
    cat = client.post("/api/v1/material-categories", headers=admin, json={"code": "X", "name": "X"}).json()["data"]
    resp = client.post(
        "/api/v1/materials",
        headers=admin,
        json={"code": "M9", "name": "无单位", "category_id": cat["id"], "unit_id": 9999},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 10001


def test_viewer_cannot_access_master_data(client, seeded):
    viewer = _auth(_token(client, "viewer", "viewer123"))
    assert client.get("/api/v1/materials", headers=viewer).status_code == 403
    assert client.post("/api/v1/units", headers=viewer, json={"code": "TT", "name": "T"}).status_code == 403
