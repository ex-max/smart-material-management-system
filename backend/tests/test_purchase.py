import re


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["data"]["access_token"]}


def _url(base, item_id, action=None):
    url = base + "/" + str(item_id)
    return url + "/" + action if action else url


def test_requisition_flow_to_purchase_order(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    approver = _login(client, "approver", "approver123")

    created = client.post(
        "/api/v1/purchase-requisitions",
        headers=buyer,
        json={
            "title": "维修备件",
            "priority": 2,
            "items": [{"material_id": procurement_master["material_id"], "quantity": "10", "purpose": "维修"}],
        },
    )
    assert created.status_code == 201, created.text
    pr = created.json()["data"]
    assert pr["status"] == "DRAFT"
    assert re.match(r"^PR-\d{8}-0001$", pr["doc_no"])
    assert pr["items"][0]["material_code"] == "M1"
    assert pr["items"][0]["unit_name"] == "个"
    pr_item_id = pr["items"][0]["id"]

    submitted = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "submit"), headers=buyer)
    assert submitted.json()["data"]["status"] == "PENDING"

    denied = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "approve"), headers=buyer)
    assert denied.status_code == 403
    assert denied.json()["code"] == 10403

    again = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "submit"), headers=buyer)
    assert again.status_code == 409
    assert again.json()["code"] == 30001

    approved = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "approve"), headers=approver).json()["data"]
    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] is not None

    converted = client.post(
        _url("/api/v1/purchase-requisitions", pr["id"], "convert-to-po"),
        headers=buyer,
        json={
            "supplier_id": procurement_master["supplier_id"],
            "items": [{"pr_item_id": pr_item_id, "unit_price": "12.5", "tax_rate": "13"}],
        },
    )
    assert converted.status_code == 200, converted.text
    po = converted.json()["data"]
    assert re.match(r"^PO-\d{8}-0001$", po["doc_no"])
    assert po["status"] == "APPROVED"
    assert po["requisition_id"] == pr["id"]
    assert po["items"][0]["source_pr_item_id"] == pr_item_id
    assert float(po["items"][0]["amount"]) == 125.0
    assert float(po["total_amount"]) == 125.0
    assert float(po["tax_amount"]) == 16.25

    refreshed = client.get(_url("/api/v1/purchase-requisitions", pr["id"]), headers=buyer).json()["data"]
    assert refreshed["status"] == "IN_PROGRESS"


def test_cannot_edit_after_submit(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    pr = client.post(
        "/api/v1/purchase-requisitions",
        headers=buyer,
        json={"items": [{"material_id": procurement_master["material_id"], "quantity": "1"}]},
    ).json()["data"]
    client.post(_url("/api/v1/purchase-requisitions", pr["id"], "submit"), headers=buyer)
    resp = client.put(_url("/api/v1/purchase-requisitions", pr["id"]), headers=buyer, json={"title": "改不动"})
    assert resp.status_code == 409
    assert resp.json()["code"] == 30002


def test_doc_no_is_sequential_per_day(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    body = {
        "supplier_id": procurement_master["supplier_id"],
        "items": [{"material_id": procurement_master["material_id"], "quantity": "1", "unit_price": "1"}],
    }
    first = client.post("/api/v1/purchase-orders", headers=buyer, json=body).json()["data"]
    second = client.post("/api/v1/purchase-orders", headers=buyer, json=body).json()["data"]
    assert first["doc_no"].endswith("-0001")
    assert second["doc_no"].endswith("-0002")
    assert first["status"] == "DRAFT"


def test_delivery_registration_and_over_delivery_rejected(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    po = client.post(
        "/api/v1/purchase-orders",
        headers=buyer,
        json={
            "supplier_id": procurement_master["supplier_id"],
            "items": [{"material_id": procurement_master["material_id"], "quantity": "5", "unit_price": "3"}],
        },
    ).json()["data"]
    confirmed = client.post(_url("/api/v1/purchase-orders", po["id"], "confirm"), headers=buyer).json()["data"]
    assert confirmed["status"] == "APPROVED"
    po_item_id = po["items"][0]["id"]

    delivery = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={
            "po_id": po["id"],
            "delivery_date": "2026-09-18",
            "items": [{"po_item_id": po_item_id, "quantity": "3", "inspection_result": "PASS"}],
        },
    )
    assert delivery.status_code == 201, delivery.text
    data = delivery.json()["data"]
    assert data["status"] == "DRAFT"
    assert data["supplier_id"] == po["supplier_id"]
    assert data["items"][0]["material_code"] == "M1"
    assert float(data["total_amount"]) == 9.0

    over = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={
            "po_id": po["id"],
            "delivery_date": "2026-09-19",
            "items": [{"po_item_id": po_item_id, "quantity": "3"}],
        },
    )
    assert over.status_code == 400

    submitted = client.post(_url("/api/v1/supplier-deliveries", data["id"], "submit"), headers=buyer)
    assert submitted.json()["data"]["status"] == "PENDING"


def test_batch_managed_material_requires_batch_no(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    po = client.post(
        "/api/v1/purchase-orders",
        headers=buyer,
        json={
            "supplier_id": procurement_master["supplier_id"],
            "items": [{"material_id": procurement_master["batch_material_id"], "quantity": "2", "unit_price": "5"}],
        },
    ).json()["data"]
    client.post(_url("/api/v1/purchase-orders", po["id"], "confirm"), headers=buyer)
    po_item_id = po["items"][0]["id"]

    missing = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={"po_id": po["id"], "delivery_date": "2026-09-18", "items": [{"po_item_id": po_item_id, "quantity": "2"}]},
    )
    assert missing.status_code == 400
    ok_resp = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={
            "po_id": po["id"],
            "delivery_date": "2026-09-18",
            "items": [{"po_item_id": po_item_id, "quantity": "2", "batch_no": "B2026", "expiry_date": "2027-09-18"}],
        },
    )
    assert ok_resp.status_code == 201


def test_purchase_viewer_can_read_not_write(client, seeded, purchase_users, procurement_master):
    viewer = _login(client, "pviewer", "pviewer123")
    assert client.get("/api/v1/purchase-requisitions", headers=viewer).status_code == 200
    resp = client.post(
        "/api/v1/purchase-requisitions",
        headers=viewer,
        json={"items": [{"material_id": procurement_master["material_id"], "quantity": "1"}]},
    )
    assert resp.status_code == 403


def test_invalid_material_and_supplier_rejected(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    bad_pr = client.post(
        "/api/v1/purchase-requisitions",
        headers=buyer,
        json={"items": [{"material_id": 999999, "quantity": "1"}]},
    )
    assert bad_pr.status_code == 400
    bad_po = client.post(
        "/api/v1/purchase-orders",
        headers=buyer,
        json={"supplier_id": 999999, "items": [{"material_id": procurement_master["material_id"], "quantity": "1"}]},
    )
    assert bad_po.status_code == 400


def test_cancel_requisition_then_cannot_submit(client, seeded, purchase_users, procurement_master):
    buyer = _login(client, "buyer", "buyer123")
    pr = client.post(
        "/api/v1/purchase-requisitions",
        headers=buyer,
        json={"items": [{"material_id": procurement_master["material_id"], "quantity": "1"}]},
    ).json()["data"]
    cancelled = client.post(
        _url("/api/v1/purchase-requisitions", pr["id"], "cancel"), headers=buyer, json={"reason": "不需要了"}
    ).json()["data"]
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancel_reason"] == "不需要了"
    resp = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "submit"), headers=buyer)
    assert resp.status_code == 409
    assert resp.json()["code"] == 30001
