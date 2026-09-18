import re
from decimal import Decimal

from app.model.inventory import Inventory


def _po_url(po_id, action=None):
    url = "/api/v1/purchase-orders/" + str(po_id)
    return url + "/" + action if action else url


def _delivery_url(delivery_id, action=None):
    url = "/api/v1/supplier-deliveries/" + str(delivery_id)
    return url + "/" + action if action else url


def _inbound_url(inbound_id, action=None):
    url = "/api/v1/inbound-orders/" + str(inbound_id)
    return url + "/" + action if action else url


def _confirmed_po(client, buyer, supplier_id, material_id, qty, price):
    po = client.post(
        "/api/v1/purchase-orders",
        headers=buyer,
        json={"supplier_id": supplier_id, "items": [{"material_id": material_id, "quantity": qty, "unit_price": price}]},
    ).json()["data"]
    client.post(_po_url(po["id"], "confirm"), headers=buyer)
    return po


def _submitted_delivery(client, buyer, po, qty, **item_extra):
    item = {"po_item_id": po["items"][0]["id"], "quantity": qty}
    item.update(item_extra)
    delivery = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={"po_id": po["id"], "delivery_date": "2026-09-18", "items": [item]},
    ).json()["data"]
    client.post(_delivery_url(delivery["id"], "submit"), headers=buyer)
    return delivery


def _accept(client, buyer, delivery_id, warehouse_id, items=None):
    payload = {"warehouse_id": warehouse_id}
    if items is not None:
        payload["items"] = items
    return client.post(_delivery_url(delivery_id, "accept"), headers=buyer, json=payload)


def test_receiving_posts_inventory_and_updates_po(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "10", "5")
    delivery = _submitted_delivery(client, buyer, po, "4")

    accepted = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"])
    assert accepted.status_code == 200, accepted.text
    inbound = accepted.json()["data"]
    assert inbound["status"] == "DRAFT"
    assert re.match(r"^IN-\d{8}-0001$", inbound["doc_no"])
    assert inbound["delivery_id"] == delivery["id"]
    assert float(inbound["items"][0]["quantity"]) == 4.0
    assert inbound["items"][0]["batch_no"] == "__DEFAULT__"

    posted = client.post(_inbound_url(inbound["id"], "post"), headers=manager)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "IN_PROGRESS"

    inventory = client.get("/api/v1/inventory", headers=manager).json()["data"]
    assert inventory["total"] == 1
    assert float(inventory["items"][0]["quantity"]) == 4.0

    batches = client.get("/api/v1/inventory/batches", headers=manager).json()["data"]
    assert batches["total"] == 1
    assert batches["items"][0]["batch_no"] == "__DEFAULT__"
    assert batches["items"][0]["is_default"] is True
    assert float(batches["items"][0]["quantity"]) == 4.0

    txns = client.get("/api/v1/inventory/transactions", headers=manager).json()["data"]
    assert txns["total"] == 1
    assert float(txns["items"][0]["quantity"]) == 4.0
    assert txns["items"][0]["txn_type"] == "INBOUND"
    assert txns["items"][0]["source_no"] == inbound["doc_no"]
    assert float(txns["items"][0]["balance_after"]) == 4.0

    po_after = client.get(_po_url(po["id"]), headers=buyer).json()["data"]
    assert float(po_after["items"][0]["received_qty"]) == 4.0
    assert po_after["status"] == "IN_PROGRESS"

    delivery_after = client.get(_delivery_url(delivery["id"]), headers=buyer).json()["data"]
    assert delivery_after["status"] == "COMPLETED"
    assert delivery_after["inspected_by"] is not None

    reconcile = client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]
    assert reconcile["ok"] is True, reconcile

    completed = client.post(_inbound_url(inbound["id"], "complete"), headers=manager).json()["data"]
    assert completed["status"] == "COMPLETED"


def test_full_receipt_completes_purchase_order(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "4", "2")
    delivery = _submitted_delivery(client, buyer, po, "4")
    inbound = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"]).json()["data"]
    client.post(_inbound_url(inbound["id"], "post"), headers=manager)
    po_after = client.get(_po_url(po["id"]), headers=buyer).json()["data"]
    assert po_after["status"] == "COMPLETED"
    assert float(po_after["items"][0]["received_qty"]) == 4.0


def test_batch_managed_material_creates_named_batch(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["batch_material_id"], "3", "7")
    delivery = _submitted_delivery(client, buyer, po, "3", batch_no="B2026", expiry_date="2027-09-18")
    accepted = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"]).json()["data"]
    assert accepted["items"][0]["batch_no"] == "B2026"
    client.post(_inbound_url(accepted["id"], "post"), headers=manager)
    batches = client.get("/api/v1/inventory/batches", headers=manager).json()["data"]
    assert batches["total"] == 1
    assert batches["items"][0]["batch_no"] == "B2026"
    assert batches["items"][0]["is_default"] is False
    assert batches["items"][0]["expiry_date"] == "2027-09-18"


def test_partial_inspection_receives_accepted_only(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "10", "3")
    delivery = _submitted_delivery(client, buyer, po, "6")
    delivery_item_id = delivery["items"][0]["id"]
    accepted = _accept(
        client,
        buyer,
        delivery["id"],
        procurement_master["warehouse_id"],
        items=[
            {
                "delivery_item_id": delivery_item_id,
                "accepted_qty": "5",
                "rejected_qty": "1",
                "inspection_result": "CONCESSION",
            }
        ],
    )
    assert accepted.status_code == 200, accepted.text
    inbound = accepted.json()["data"]
    assert float(inbound["items"][0]["quantity"]) == 5.0
    client.post(_inbound_url(inbound["id"], "post"), headers=manager)
    inventory = client.get("/api/v1/inventory", headers=manager).json()["data"]
    assert float(inventory["items"][0]["quantity"]) == 5.0
    po_after = client.get(_po_url(po["id"]), headers=buyer).json()["data"]
    assert float(po_after["items"][0]["received_qty"]) == 5.0


def test_reconcile_detects_inventory_drift(client, seeded, purchase_users, inventory_users, procurement_master, login, db_session):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "4", "2")
    delivery = _submitted_delivery(client, buyer, po, "4")
    inbound = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"]).json()["data"]
    client.post(_inbound_url(inbound["id"], "post"), headers=manager)

    row = db_session.query(Inventory).first()
    row.quantity = row.quantity + Decimal("5")
    db_session.commit()

    reconcile = client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]
    assert reconcile["ok"] is False
    assert reconcile["inventory_vs_batch"]
    assert reconcile["inventory_vs_txn"]


def test_inventory_permissions_and_duplicate_post(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    viewer = login("iviewer", "iviewer123")

    assert client.get("/api/v1/inventory", headers=viewer).status_code == 200

    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "4", "2")
    delivery = _submitted_delivery(client, buyer, po, "4")
    inbound = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"]).json()["data"]

    denied = client.post(_inbound_url(inbound["id"], "post"), headers=viewer)
    assert denied.status_code == 403
    assert denied.json()["code"] == 10403

    assert client.post(_inbound_url(inbound["id"], "post"), headers=manager).status_code == 200
    duplicate = client.post(_inbound_url(inbound["id"], "post"), headers=manager)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 30001


def test_accept_requires_submitted_delivery(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "4", "2")
    delivery = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={
            "po_id": po["id"],
            "delivery_date": "2026-09-18",
            "items": [{"po_item_id": po["items"][0]["id"], "quantity": "4"}],
        },
    ).json()["data"]
    resp = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"])
    assert resp.status_code == 409
    assert resp.json()["code"] == 30001


def test_cancel_draft_inbound_blocks_post(client, seeded, purchase_users, inventory_users, procurement_master, login):
    buyer = login("buyer", "buyer123")
    manager = login("imanager", "imanager123")
    po = _confirmed_po(client, buyer, procurement_master["supplier_id"], procurement_master["material_id"], "4", "2")
    delivery = _submitted_delivery(client, buyer, po, "4")
    inbound = _accept(client, buyer, delivery["id"], procurement_master["warehouse_id"]).json()["data"]
    cancelled = client.post(_inbound_url(inbound["id"], "cancel"), headers=manager, json={"reason": "验错"}).json()["data"]
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancel_reason"] == "验错"
    resp = client.post(_inbound_url(inbound["id"], "post"), headers=manager)
    assert resp.status_code == 409
