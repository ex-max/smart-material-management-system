from datetime import date, timedelta


def _url(base, item_id, action=None):
    url = base + "/" + str(item_id)
    return url + "/" + action if action else url


def _seed_stock(client, buyer, manager, master, qty="10", material_key="material_id", item_extra=None):
    item = {"material_id": master[material_key], "quantity": qty, "unit_price": "1"}
    if item_extra:
        item.update(item_extra)
    po = client.post(
        "/api/v1/purchase-orders",
        headers=buyer,
        json={"supplier_id": master["supplier_id"], "items": [item]},
    ).json()["data"]
    client.post(_url("/api/v1/purchase-orders", po["id"], "confirm"), headers=buyer)
    delivery_item = {"po_item_id": po["items"][0]["id"], "quantity": qty}
    if item_extra:
        delivery_item.update(item_extra)
    delivery = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={"po_id": po["id"], "delivery_date": "2026-09-18", "items": [delivery_item]},
    ).json()["data"]
    client.post(_url("/api/v1/supplier-deliveries", delivery["id"], "submit"), headers=buyer)
    inbound = client.post(
        _url("/api/v1/supplier-deliveries", delivery["id"], "accept"),
        headers=buyer,
        json={"warehouse_id": master["warehouse_id"]},
    ).json()["data"]
    client.post(_url("/api/v1/inbound-orders", inbound["id"], "post"), headers=manager)
    return po, inbound


def _set_material(client, admin, material_id, **fields):
    return client.put(_url("/api/v1/materials", material_id), headers=admin, json=fields)


def _alert_rows(client, headers, **params):
    return client.get("/api/v1/stock-alerts", headers=headers, params=params).json()["data"]


def test_low_stock_scan_dedup_and_lifecycle(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    admin = procurement_master["admin"]
    _set_material(client, admin, procurement_master["material_id"], safety_stock="5")
    _seed_stock(client, buyer, manager, procurement_master, qty="3")

    first = client.post("/api/v1/stock-alerts/scan", headers=manager).json()["data"]
    assert first["created"] >= 1
    rows = _alert_rows(client, manager, alert_type="LOW_STOCK")
    assert rows["total"] == 1
    assert rows["items"][0]["status"] == "OPEN"
    alert_id = rows["items"][0]["id"]

    second = client.post("/api/v1/stock-alerts/scan", headers=manager).json()["data"]
    assert second["created"] == 0
    assert _alert_rows(client, manager, alert_type="LOW_STOCK")["total"] == 1

    acked = client.post(_url("/api/v1/stock-alerts", alert_id, "ack"), headers=manager).json()["data"]
    assert acked["status"] == "ACKED"
    assert acked["acked_by"] is not None
    assert client.post("/api/v1/stock-alerts/scan", headers=manager).json()["data"]["created"] == 0

    resolved = client.post(_url("/api/v1/stock-alerts", alert_id, "resolve"), headers=manager).json()["data"]
    assert resolved["status"] == "RESOLVED"
    # 关闭后可重新生成
    assert client.post("/api/v1/stock-alerts/scan", headers=manager).json()["data"]["created"] >= 1
    assert _alert_rows(client, manager, alert_type="LOW_STOCK", status="OPEN")["total"] == 1


def test_out_of_stock_alert(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    admin = procurement_master["admin"]
    _set_material(client, admin, procurement_master["material_id"], safety_stock="5")
    _seed_stock(client, buyer, manager, procurement_master, qty="1")
    outbound = client.post(
        "/api/v1/outbound-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "1"}],
        },
    ).json()["data"]
    client.post(_url("/api/v1/outbound-orders", outbound["id"], "post"), headers=manager)

    client.post("/api/v1/stock-alerts/scan", headers=manager)
    rows = _alert_rows(client, manager, alert_type="OUT_OF_STOCK")
    assert rows["total"] == 1
    assert rows["items"][0]["level"] == "CRITICAL"


def test_over_stock_alert(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    admin = procurement_master["admin"]
    _set_material(client, admin, procurement_master["material_id"], max_stock="2")
    _seed_stock(client, buyer, manager, procurement_master, qty="5")
    client.post("/api/v1/stock-alerts/scan", headers=manager)
    rows = _alert_rows(client, manager, alert_type="OVER_STOCK")
    assert rows["total"] == 1
    assert rows["items"][0]["level"] == "INFO"


def test_batch_expiry_alerts(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    near = (date.today() + timedelta(days=10)).isoformat()
    _seed_stock(
        client,
        buyer,
        manager,
        procurement_master,
        qty="3",
        material_key="batch_material_id",
        item_extra={"batch_no": "BNEAR", "expiry_date": near},
    )
    client.post("/api/v1/stock-alerts/scan", headers=manager)
    rows = _alert_rows(client, manager, alert_type="NEAR_EXPIRY")
    assert rows["total"] == 1
    assert rows["items"][0]["batch_id"] is not None


def test_inventory_snapshot_generate_is_idempotent(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    _seed_stock(client, buyer, manager, procurement_master, qty="10")

    first = client.post(
        "/api/v1/inventory-snapshots/generate", headers=manager, params={"snapshot_date": "2026-09-18"}
    ).json()["data"]
    assert first["created"] == 1
    rows = client.get(
        "/api/v1/inventory-snapshots", headers=manager, params={"snapshot_date": "2026-09-18"}
    ).json()["data"]
    assert rows["total"] == 1
    assert float(rows["items"][0]["quantity"]) == 10.0

    second = client.post(
        "/api/v1/inventory-snapshots/generate", headers=manager, params={"snapshot_date": "2026-09-18"}
    ).json()["data"]
    assert second["updated"] == 1
    assert second["created"] == 0
    assert client.get(
        "/api/v1/inventory-snapshots", headers=manager, params={"snapshot_date": "2026-09-18"}
    ).json()["data"]["total"] == 1


def test_material_supplier_price_crud_and_preferred(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    admin = procurement_master["admin"]
    second_supplier = client.post(
        "/api/v1/suppliers", headers=admin, json={"code": "S2", "name": "供应商乙"}
    ).json()["data"]
    material_id = procurement_master["material_id"]

    first = client.post(
        "/api/v1/material-supplier-prices",
        headers=buyer,
        json={
            "material_id": material_id,
            "supplier_id": procurement_master["supplier_id"],
            "unit_price": "9.5",
            "is_preferred": True,
        },
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["data"]["id"]

    second = client.post(
        "/api/v1/material-supplier-prices",
        headers=buyer,
        json={"material_id": material_id, "supplier_id": second_supplier["id"], "unit_price": "8.8", "is_preferred": True},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["data"]["id"]

    # 优先供应商唯一：新设为 preferred 后旧的被取消
    assert client.get(_url("/api/v1/material-supplier-prices", first_id), headers=buyer).json()["data"]["is_preferred"] is False
    assert client.get(_url("/api/v1/material-supplier-prices", second_id), headers=buyer).json()["data"]["is_preferred"] is True

    duplicate = client.post(
        "/api/v1/material-supplier-prices",
        headers=buyer,
        json={"material_id": material_id, "supplier_id": procurement_master["supplier_id"], "unit_price": "1"},
    )
    assert duplicate.status_code == 409

    updated = client.put(
        _url("/api/v1/material-supplier-prices", second_id), headers=buyer, json={"unit_price": "7.7"}
    ).json()["data"]
    assert float(updated["unit_price"]) == 7.7

    assert client.delete(_url("/api/v1/material-supplier-prices", second_id), headers=buyer).status_code == 200
    assert client.get("/api/v1/material-supplier-prices", headers=buyer).json()["data"]["total"] == 1


def test_ledger_permissions(client, seeded, purchase_users, inventory_users, procurement_master, login):
    viewer = login("iviewer", "iviewer123")
    pviewer = login("pviewer", "pviewer123")
    assert client.get("/api/v1/stock-alerts", headers=viewer).status_code == 200
    assert client.post("/api/v1/stock-alerts/scan", headers=viewer).status_code == 403
    assert client.get("/api/v1/material-supplier-prices", headers=pviewer).status_code == 200
    resp = client.post(
        "/api/v1/material-supplier-prices",
        headers=pviewer,
        json={"material_id": procurement_master["material_id"], "supplier_id": procurement_master["supplier_id"], "unit_price": "1"},
    )
    assert resp.status_code == 403
