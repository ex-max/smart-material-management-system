import re


def _url(base, item_id, action=None):
    url = base + "/" + str(item_id)
    return url + "/" + action if action else url


def _seed_stock(client, buyer, manager, master, qty="10", material_key="material_id", item_extra=None):
    """经采购→到货→入库把库存种进 warehouse_id，返回 (po, inbound)。"""
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


def _qty(client, headers, material_id, warehouse_id):
    rows = client.get(
        "/api/v1/inventory",
        headers=headers,
        params={"material_id": material_id, "warehouse_id": warehouse_id},
    ).json()["data"]["items"]
    return float(rows[0]["quantity"]) if rows else 0.0


def test_outbound_posting_and_complete(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    _seed_stock(client, buyer, manager, procurement_master, qty="10")

    outbound = client.post(
        "/api/v1/outbound-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "dept_name": "维修部",
            "items": [{"material_id": procurement_master["material_id"], "quantity": "4"}],
        },
    )
    assert outbound.status_code == 201, outbound.text
    obj = outbound.json()["data"]
    assert re.match(r"^OUT-\d{8}-0001$", obj["doc_no"])
    assert obj["status"] == "DRAFT"

    posted = client.post(_url("/api/v1/outbound-orders", obj["id"], "post"), headers=manager)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "IN_PROGRESS"
    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 6.0

    txns = client.get("/api/v1/inventory/transactions", headers=manager, params={"source_type": "OUTBOUND"}).json()["data"]
    assert txns["total"] == 1
    assert float(txns["items"][0]["quantity"]) == -4.0
    assert txns["items"][0]["txn_type"] == "OUTBOUND"

    completed = client.post(_url("/api/v1/outbound-orders", obj["id"], "complete"), headers=manager)
    assert completed.json()["data"]["status"] == "COMPLETED"
    assert client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]["ok"] is True


def test_outbound_insufficient_rejected(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    _seed_stock(client, buyer, manager, procurement_master, qty="4")
    obj = client.post(
        "/api/v1/outbound-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "10"}],
        },
    ).json()["data"]
    resp = client.post(_url("/api/v1/outbound-orders", obj["id"], "post"), headers=manager)
    assert resp.status_code == 400
    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 4.0


def test_outbound_reverse_redflushes(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    _seed_stock(client, buyer, manager, procurement_master, qty="10")
    obj = client.post(
        "/api/v1/outbound-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "4"}],
        },
    ).json()["data"]
    client.post(_url("/api/v1/outbound-orders", obj["id"], "post"), headers=manager)

    resp = client.post(_url("/api/v1/outbound-orders", obj["id"], "reverse"), headers=manager, json={"reason": "领错"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "CANCELLED"
    assert resp.json()["data"]["cancel_reason"] == "领错"
    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 10.0
    txns = client.get("/api/v1/inventory/transactions", headers=manager, params={"source_type": "OUTBOUND"}).json()["data"]
    assert {i["txn_type"] for i in txns["items"]} == {"OUTBOUND", "REVERSAL"}
    assert client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]["ok"] is True


def test_transfer_posting_moves_two_warehouses(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    admin = procurement_master["admin"]
    second = client.post("/api/v1/warehouses", headers=admin, json={"code": "WH02", "name": "备用仓"}).json()["data"]
    _seed_stock(client, buyer, manager, procurement_master, qty="10")

    transfer = client.post(
        "/api/v1/transfer-orders",
        headers=manager,
        json={
            "from_warehouse_id": procurement_master["warehouse_id"],
            "to_warehouse_id": second["id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "4"}],
        },
    )
    assert transfer.status_code == 201, transfer.text
    obj = transfer.json()["data"]
    assert re.match(r"^TR-\d{8}-0001$", obj["doc_no"])

    posted = client.post(_url("/api/v1/transfer-orders", obj["id"], "post"), headers=manager)
    assert posted.status_code == 200, posted.text
    body = posted.json()["data"]
    assert body["status"] == "IN_PROGRESS"
    assert body["items"][0]["outbound_item_id"] is not None
    assert body["items"][0]["inbound_item_id"] is not None

    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 6.0
    assert _qty(client, manager, procurement_master["material_id"], second["id"]) == 4.0

    transfer_txns = client.get(
        "/api/v1/inventory/transactions", headers=manager, params={"source_type": "TRANSFER"}
    ).json()["data"]
    assert transfer_txns["total"] == 2
    assert float(sum(float(i["quantity"]) for i in transfer_txns["items"])) == 0.0

    generated_out = client.get("/api/v1/outbound-orders", headers=manager).json()["data"]
    assert generated_out["total"] == 1
    assert generated_out["items"][0]["source_type"] == "TRANSFER"
    assert generated_out["items"][0]["transfer_order_id"] == obj["id"]

    completed = client.post(_url("/api/v1/transfer-orders", obj["id"], "complete"), headers=manager)
    assert completed.json()["data"]["status"] == "COMPLETED"
    assert client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]["ok"] is True


def test_transfer_reverse_restores_both_warehouses(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    admin = procurement_master["admin"]
    second = client.post("/api/v1/warehouses", headers=admin, json={"code": "WH02", "name": "备用仓"}).json()["data"]
    _seed_stock(client, buyer, manager, procurement_master, qty="10")
    obj = client.post(
        "/api/v1/transfer-orders",
        headers=manager,
        json={
            "from_warehouse_id": procurement_master["warehouse_id"],
            "to_warehouse_id": second["id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "4"}],
        },
    ).json()["data"]
    client.post(_url("/api/v1/transfer-orders", obj["id"], "post"), headers=manager)

    resp = client.post(_url("/api/v1/transfer-orders", obj["id"], "reverse"), headers=manager, json={"reason": "调错"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "CANCELLED"
    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 10.0
    assert _qty(client, manager, procurement_master["material_id"], second["id"]) == 0.0
    generated_out = client.get("/api/v1/outbound-orders", headers=manager).json()["data"]["items"][0]
    assert generated_out["status"] == "CANCELLED"
    assert client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]["ok"] is True


def test_stocktake_gain_loss_and_reverse(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    _seed_stock(client, buyer, manager, procurement_master, qty="10")

    stocktake = client.post(
        "/api/v1/stocktake-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["material_id"]}],
        },
    ).json()["data"]
    assert re.match(r"^ST-\d{8}-0001$", stocktake["doc_no"])
    started = client.post(_url("/api/v1/stocktake-orders", stocktake["id"], "start"), headers=manager).json()["data"]
    assert float(started["items"][0]["book_qty"]) == 10.0
    item_id = started["items"][0]["id"]

    counted = client.post(
        _url("/api/v1/stocktake-orders", stocktake["id"], "counts"),
        headers=manager,
        json={"items": [{"stocktake_item_id": item_id, "actual_qty": "12", "reason": "盘盈"}]},
    ).json()["data"]
    assert float(counted["items"][0]["diff_qty"]) == 2.0

    completed = client.post(_url("/api/v1/stocktake-orders", stocktake["id"], "complete"), headers=manager)
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["status"] == "COMPLETED"
    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 12.0
    txns = client.get(
        "/api/v1/inventory/transactions", headers=manager, params={"source_type": "STOCKTAKE"}
    ).json()["data"]
    assert txns["total"] == 1
    assert txns["items"][0]["txn_type"] == "STOCKTAKE_GAIN"
    assert float(txns["items"][0]["quantity"]) == 2.0

    resp = client.post(
        _url("/api/v1/stocktake-orders", stocktake["id"], "reverse"), headers=manager, json={"reason": "盘错"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "CANCELLED"
    assert _qty(client, manager, procurement_master["material_id"], procurement_master["warehouse_id"]) == 10.0
    assert client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]["ok"] is True


def test_stocktake_requires_actual_qty(client, seeded, purchase_users, inventory_users, procurement_master, login):
    manager = login("imanager", "imanager123")
    stocktake = client.post(
        "/api/v1/stocktake-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["material_id"]}],
        },
    ).json()["data"]
    client.post(_url("/api/v1/stocktake-orders", stocktake["id"], "start"), headers=manager)
    resp = client.post(_url("/api/v1/stocktake-orders", stocktake["id"], "complete"), headers=manager)
    assert resp.status_code == 400


def test_batch_material_outbound_requires_batch(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    _seed_stock(
        client,
        buyer,
        manager,
        procurement_master,
        qty="3",
        material_key="batch_material_id",
        item_extra={"batch_no": "B1", "expiry_date": "2027-09-18"},
    )
    obj = client.post(
        "/api/v1/outbound-orders",
        headers=manager,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["batch_material_id"], "quantity": "1"}],
        },
    ).json()["data"]
    resp = client.post(_url("/api/v1/outbound-orders", obj["id"], "post"), headers=manager)
    assert resp.status_code == 400
    assert "批次" in resp.json()["message"]


def test_ops_viewer_can_read_not_write(client, seeded, purchase_users, inventory_users, procurement_master, login):
    viewer = login("iviewer", "iviewer123")
    assert client.get("/api/v1/outbound-orders", headers=viewer).status_code == 200
    assert client.get("/api/v1/transfer-orders", headers=viewer).status_code == 200
    assert client.get("/api/v1/stocktake-orders", headers=viewer).status_code == 200
    resp = client.post(
        "/api/v1/outbound-orders",
        headers=viewer,
        json={
            "warehouse_id": procurement_master["warehouse_id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "1"}],
        },
    )
    assert resp.status_code == 403
