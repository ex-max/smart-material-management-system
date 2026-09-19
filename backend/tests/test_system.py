"""M7 系统测试：从"系统外部"视角验证功能主线、统一接口契约与权限边界。

与单元/集成测试的区别：这里用一条跨模块业务主线把
登录 → 主数据 → 请购 → 审批 → 转采购订单 → 到货 → 验收 → 入库 → 结存 串起来，
并单独锁定统一响应契约与 RBAC 边界（功能/接口/权限各至少一条）。
"""

import re
from decimal import Decimal


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["data"]["access_token"]}


def _url(base, item_id, action=None):
    url = base + "/" + str(item_id)
    return url + "/" + action if action else url


# ---------------------------------------------------------------- 功能：跨模块主线
def test_system_replenish_to_inventory_flow(client, seeded, purchase_users, inventory_users, procurement_master, login):
    """功能：请购 → 审批 → 转采购订单 → 到货 → 验收 → 入库 → 结存与对账。"""
    buyer = login("buyer", "buyer123")
    approver = login("approver", "approver123")
    manager = login("imanager", "imanager123")

    # 1) 请购单：建单 → 提交 → 审批 → 转采购订单
    pr = client.post(
        "/api/v1/purchase-requisitions",
        headers=buyer,
        json={
            "title": "系统测试：维修备件",
            "priority": 2,
            "items": [{"material_id": procurement_master["material_id"], "quantity": "10", "purpose": "维修"}],
        },
    ).json()["data"]
    assert pr["status"] == "DRAFT"
    assert re.match(r"^PR-\d{8}-\d{4}$", pr["doc_no"])

    submitted = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "submit"), headers=buyer).json()["data"]
    assert submitted["status"] == "PENDING"

    approved = client.post(_url("/api/v1/purchase-requisitions", pr["id"], "approve"), headers=approver).json()["data"]
    assert approved["status"] == "APPROVED"

    converted = client.post(
        _url("/api/v1/purchase-requisitions", pr["id"], "convert-to-po"),
        headers=buyer,
        json={
            "supplier_id": procurement_master["supplier_id"],
            "items": [{"pr_item_id": pr["items"][0]["id"], "unit_price": "12.5", "tax_rate": "13"}],
        },
    )
    assert converted.status_code == 200, converted.text
    po = converted.json()["data"]
    assert re.match(r"^PO-\d{8}-\d{4}$", po["doc_no"])
    assert po["status"] == "APPROVED"
    assert po["requisition_id"] == pr["id"]

    # 2) 到货单：登记 → 提交 → 验收生成入库单
    delivery = client.post(
        "/api/v1/supplier-deliveries",
        headers=buyer,
        json={
            "po_id": po["id"],
            "delivery_date": "2026-09-19",
            "items": [{"po_item_id": po["items"][0]["id"], "quantity": "10", "inspection_result": "PASS"}],
        },
    ).json()["data"]
    client.post(_url("/api/v1/supplier-deliveries", delivery["id"], "submit"), headers=buyer)
    accepted = client.post(
        _url("/api/v1/supplier-deliveries", delivery["id"], "accept"),
        headers=buyer,
        json={"warehouse_id": procurement_master["warehouse_id"]},
    )
    assert accepted.status_code == 200, accepted.text
    inbound = accepted.json()["data"]
    assert inbound["status"] == "DRAFT"
    assert re.match(r"^IN-\d{8}-\d{4}$", inbound["doc_no"])

    # 3) 入库过账 → 结存 10 且与流水一致
    posted = client.post(_url("/api/v1/inbound-orders", inbound["id"], "post"), headers=manager)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "IN_PROGRESS"

    inventory = client.get("/api/v1/inventory", headers=manager).json()["data"]
    assert inventory["total"] == 1
    assert Decimal(inventory["items"][0]["quantity"]) == Decimal("10")

    txns = client.get("/api/v1/inventory/transactions", headers=manager).json()["data"]
    assert txns["total"] == 1
    assert txns["items"][0]["txn_type"] == "INBOUND"
    assert txns["items"][0]["source_no"] == inbound["doc_no"]

    reconcile = client.get("/api/v1/inventory/reconcile", headers=manager).json()["data"]
    assert reconcile["ok"] is True, reconcile

    # 4) 到货单完成、采购订单进入执行中（部分/全部到货由后端状态机决定）
    delivery_after = client.get(_url("/api/v1/supplier-deliveries", delivery["id"]), headers=buyer).json()["data"]
    assert delivery_after["status"] == "COMPLETED"
    po_after = client.get(_url("/api/v1/purchase-orders", po["id"]), headers=buyer).json()["data"]
    assert Decimal(po_after["items"][0]["received_qty"]) == Decimal("10")


# ---------------------------------------------------------------- 接口：统一响应契约
def test_system_response_envelope_and_openapi(client):
    """接口：统一响应 {code,message,data,trace_id}、trace 透传、OpenAPI 可发现、错误也走同一包装。"""
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert {"code", "message", "data", "trace_id"} <= set(body)
    assert body["code"] == 0
    assert body["trace_id"]
    assert health.headers.get("X-Trace-Id") == body["trace_id"]
    assert health.headers.get("X-Process-Time-Ms")

    spec = client.get("/api/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for p in ("/api/health", "/api/v1/auth/login", "/api/v1/materials", "/api/v1/inventory"):
        assert p in paths, f"OpenAPI 缺少 {p}"
    assert len(paths) >= 30

    missing = client.get("/api/v1/definitely-not-a-route")
    assert missing.status_code == 404
    assert {"code", "message", "data", "trace_id"} <= set(missing.json())
    assert missing.json()["code"] != 0

    invalid = client.post("/api/v1/auth/login", json={})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == 10422


# ---------------------------------------------------------------- 权限：RBAC 边界
def test_system_permission_boundaries(client, seeded):
    """权限：匿名 401；只读账号可读不可写（403）；管理员放行。"""
    anonymous = client.get("/api/v1/users")
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == 10401

    viewer = _login(client, "viewer", "viewer123")
    assert client.get("/api/v1/users", headers=viewer).status_code == 200
    denied = client.post(
        "/api/v1/users",
        headers=viewer,
        json={"username": "should-not-exist", "password": "secret123"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == 10403

    admin = _login(client, "admin", "admin123")
    assert client.get("/api/v1/users", headers=admin).status_code == 200
