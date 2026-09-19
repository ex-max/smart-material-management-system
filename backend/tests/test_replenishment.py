"""M6 补货决策测试：策略 CRUD、建议生成/确认/转请购单、权限。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.model.inventory import Inventory


def _headers(procurement_master):
    return procurement_master["admin"]


def _ingest_forecast(client, headers, material_id, warehouse_id, run_id, y_hat="10"):
    items = [
        {
            "material_id": material_id,
            "warehouse_id": warehouse_id,
            "forecast_date": (date.today() + timedelta(days=step)).isoformat(),
            "horizon_step": step,
            "y_hat": y_hat,
            "model_code": "lightgbm",
        }
        for step in range(1, 8)
    ]
    resp = client.post("/api/v1/forecast-runs/%d/results" % run_id, headers=headers, json={"items": items})
    assert resp.status_code == 200, resp.text


@pytest.fixture()
def decision_env(client, db_session, procurement_master):
    """零库存 + 预测 + 策略，供生成建议类用例复用。"""
    headers = _headers(procurement_master)
    material_id = procurement_master["material_id"]
    second_material_id = procurement_master["batch_material_id"]
    warehouse_id = procurement_master["warehouse_id"]

    for mid in (material_id, second_material_id):
        meta = client.post(
            "/api/v1/demand-series-meta",
            headers=headers,
            json={
                "material_id": mid,
                "warehouse_id": warehouse_id,
                "mean_daily": "10",
                "std_daily": "2",
                "demand_class": "SMOOTH",
            },
        )
        assert meta.status_code == 200, meta.text

    run = client.post("/api/v1/forecast-runs", headers=headers, json={"horizon_days": 7}).json()["data"]
    for mid in (material_id, second_material_id):
        _ingest_forecast(client, headers, mid, warehouse_id, run["id"])
    client.post("/api/v1/forecast-runs/%d/finish" % run["id"], headers=headers, json={"status": "SUCCESS"})

    db_session.add_all(
        [
            Inventory(material_id=material_id, warehouse_id=warehouse_id, quantity=Decimal("0"), locked_qty=Decimal("0")),
            Inventory(
                material_id=second_material_id, warehouse_id=warehouse_id, quantity=Decimal("0"), locked_qty=Decimal("0")
            ),
        ]
    )
    db_session.commit()

    policy = client.post(
        "/api/v1/replenishment-policies",
        headers=headers,
        json={
            "policy_code": "POL-M1",
            "policy_name": "主料预测驱动",
            "material_id": material_id,
            "warehouse_id": warehouse_id,
            "strategy": "FORECAST",
            "service_level_type": "CSL",
            "service_level": "0.95",
            "review_period_days": 7,
            "order_cost": "100",
            "holding_cost_rate": "0.2",
            "min_order_qty": "10",
            "pack_size": "5",
            "lead_time_days": "5",
        },
    ).json()["data"]
    client.post(
        "/api/v1/replenishment-policies",
        headers=headers,
        json={
            "policy_code": "POL-M2-GLOBAL",
            "material_id": second_material_id,
            "strategy": "MIN_MAX",
            "service_level_type": "CSL",
            "service_level": "0.95",
            "review_period_days": 7,
            "min_order_qty": "1",
            "pack_size": "1",
            "lead_time_days": "5",
        },
    )
    return {
        "headers": headers,
        "material_id": material_id,
        "second_material_id": second_material_id,
        "warehouse_id": warehouse_id,
        "run_id": run["id"],
        "policy_id": policy["id"],
    }


def _generate(client, env):
    resp = client.post("/api/v1/replenishment-suggestions/generate", headers=env["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _suggestion_for(client, env, material_id):
    listed = client.get(
        "/api/v1/replenishment-suggestions",
        headers=env["headers"],
        params={"material_id": material_id},
    ).json()["data"]
    assert listed["total"] == 1, listed
    return listed["items"][0]


def test_policy_crud_and_unique(client, decision_env):
    headers = decision_env["headers"]
    duplicate = client.post(
        "/api/v1/replenishment-policies",
        headers=headers,
        json={"policy_code": "POL-M1", "strategy": "FORECAST"},
    )
    assert duplicate.status_code == 409

    fetched = client.get("/api/v1/replenishment-policies/%d" % decision_env["policy_id"], headers=headers)
    assert fetched.json()["data"]["strategy"] == "FORECAST"

    updated = client.put(
        "/api/v1/replenishment-policies/%d" % decision_env["policy_id"],
        headers=headers,
        json={"min_order_qty": "20"},
    )
    assert updated.status_code == 200
    assert Decimal(updated.json()["data"]["min_order_qty"]) == Decimal("20")

    # 服务水平必须存小数口径（0<x<1）
    invalid = client.post(
        "/api/v1/replenishment-policies",
        headers=headers,
        json={"policy_code": "POL-BAD", "strategy": "FORECAST", "service_level": "95"},
    )
    assert invalid.status_code == 422

    deleted = client.delete("/api/v1/replenishment-policies/%d" % decision_env["policy_id"], headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/v1/replenishment-policies/%d" % decision_env["policy_id"], headers=headers).status_code == 404


def test_generate_is_explainable(client, decision_env):
    result = _generate(client, decision_env)
    assert result["created"] == 2
    assert result["skipped_no_policy"] == 0

    suggestion = _suggestion_for(client, decision_env, decision_env["material_id"])
    assert suggestion["status"] == "OPEN"
    assert suggestion["trigger_type"] == "BELOW_ROP"
    assert suggestion["policy_id"] == decision_env["policy_id"]
    assert suggestion["forecast_run_id"] == decision_env["run_id"]
    assert Decimal(suggestion["available_qty"]) == Decimal("0.0000")
    # qty = S - IP = (ROP + 10*7) - 0，按 pack=5 向上取整
    assert Decimal(suggestion["suggested_qty"]) == Decimal("130.0000")
    assert float(suggestion["safety_stock"]) == pytest.approx(7.356, abs=0.01)
    assert float(suggestion["rop"]) == pytest.approx(57.356, abs=0.01)
    assert "ROP" in suggestion["reason"]
    assert "policy=POL-M1" in suggestion["reason"]
    assert "forecast_run=%d" % decision_env["run_id"] in suggestion["reason"]

    detail = client.get(
        "/api/v1/replenishment-suggestions/%d" % suggestion["id"], headers=decision_env["headers"]
    )
    assert detail.status_code == 200


def test_generate_updates_instead_of_duplicating(client, decision_env):
    first = _generate(client, decision_env)
    assert first["created"] == 2
    second = _generate(client, decision_env)
    assert second["created"] == 0
    assert second["updated"] == 2

    listed = client.get(
        "/api/v1/replenishment-suggestions",
        headers=decision_env["headers"],
        params={"material_id": decision_env["material_id"]},
    ).json()["data"]
    assert listed["total"] == 1


def test_not_triggered_closes_open_suggestion(client, db_session, decision_env):
    _generate(client, decision_env)
    inventory = (
        db_session.query(Inventory)
        .filter_by(material_id=decision_env["material_id"], warehouse_id=decision_env["warehouse_id"])
        .one()
    )
    inventory.quantity = Decimal("1000")
    db_session.commit()

    result = _generate(client, decision_env)
    assert result["closed"] >= 1

    suggestion = _suggestion_for(client, decision_env, decision_env["material_id"])
    assert suggestion["status"] == "CLOSED"


def test_confirm_then_convert_to_requisition(client, decision_env):
    _generate(client, decision_env)
    suggestion = _suggestion_for(client, decision_env, decision_env["material_id"])

    early = client.post(
        "/api/v1/replenishment-suggestions/%d/convert" % suggestion["id"], headers=decision_env["headers"]
    )
    assert early.status_code == 409

    confirmed = client.post(
        "/api/v1/replenishment-suggestions/%d/confirm" % suggestion["id"],
        headers=decision_env["headers"],
        json={"final_qty": "120"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "SUGGESTED"
    assert Decimal(confirmed.json()["data"]["final_qty"]) == Decimal("120.0000")

    converted = client.post(
        "/api/v1/replenishment-suggestions/%d/convert" % suggestion["id"], headers=decision_env["headers"]
    )
    assert converted.status_code == 200, converted.text
    body = converted.json()["data"]
    assert body["suggestion"]["status"] == "CONVERTED"
    assert body["suggestion"]["converted_pr_id"] == body["pr"]["id"]
    assert body["suggestion"]["converted_at"] is not None
    assert body["pr"]["status"] == "DRAFT"
    assert body["pr"]["doc_no"].startswith("PR-")
    assert Decimal(body["pr"]["items"][0]["quantity"]) == Decimal("120.0000")
    assert "由补货建议" in body["pr"]["reason"]

    requisitions = client.get("/api/v1/purchase-requisitions", headers=decision_env["headers"]).json()["data"]
    assert requisitions["total"] == 1
    assert requisitions["items"][0]["doc_no"] == body["pr"]["doc_no"]


def test_batch_convert(client, decision_env):
    _generate(client, decision_env)
    listed = client.get(
        "/api/v1/replenishment-suggestions", headers=decision_env["headers"], params={"status": "OPEN"}
    ).json()["data"]
    ids = [item["id"] for item in listed["items"]]
    assert len(ids) == 2
    for suggestion_id in ids:
        confirmed = client.post(
            "/api/v1/replenishment-suggestions/%d/confirm" % suggestion_id, headers=decision_env["headers"], json={}
        )
        assert confirmed.status_code == 200, confirmed.text

    converted = client.post(
        "/api/v1/replenishment-suggestions/convert-batch",
        headers=decision_env["headers"],
        json={"suggestion_ids": ids},
    )
    assert converted.status_code == 200, converted.text
    assert len(converted.json()["data"]) == 2
    requisitions = client.get("/api/v1/purchase-requisitions", headers=decision_env["headers"]).json()["data"]
    assert requisitions["total"] == 2


def test_permissions(client, login, replenishment_users):
    rviewer = login("rviewer", "rviewer123")
    rmanager = login("rmanager", "rmanager123")
    rconverter = login("rconverter", "rconverter123")

    assert client.get("/api/v1/replenishment-suggestions", headers=rviewer).status_code == 200
    assert client.post("/api/v1/replenishment-suggestions/generate", headers=rviewer).status_code == 403
    assert (
        client.post(
            "/api/v1/replenishment-policies", headers=rviewer, json={"policy_code": "P1", "strategy": "FORECAST"}
        ).status_code
        == 403
    )
    # manager 有 view/manage 但无 convert
    assert (
        client.post("/api/v1/replenishment-suggestions/1/convert", headers=rmanager).status_code == 403
    )
    # converter 有 convert，仅因对象不存在而 404（说明鉴权已通过）
    assert (
        client.post("/api/v1/replenishment-suggestions/1/convert", headers=rconverter).status_code == 404
    )
