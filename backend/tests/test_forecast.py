"""M6 预测模块测试：批次/结果/需求元数据/模型注册。"""

from datetime import date, timedelta
from decimal import Decimal


def test_forecast_run_ingest_and_finish(client, procurement_master):
    headers = procurement_master["admin"]
    material_id = procurement_master["material_id"]
    warehouse_id = procurement_master["warehouse_id"]

    created = client.post("/api/v1/forecast-runs", headers=headers, json={"horizon_days": 7})
    assert created.status_code == 201, created.text
    run = created.json()["data"]
    assert run["status"] == "RUNNING"
    assert run["run_no"].startswith("FR-")

    items = [
        {
            "material_id": material_id,
            "warehouse_id": warehouse_id,
            "forecast_date": (date.today() + timedelta(days=step)).isoformat(),
            "horizon_step": step,
            "y_hat": "12.5",
            "y_lower": "10",
            "y_upper": "15",
            "model_code": "lightgbm",
            "model_version": "v1",
            "demand_class": "SMOOTH",
        }
        for step in range(1, 4)
    ]
    ingested = client.post(
        "/api/v1/forecast-runs/%d/results" % run["id"], headers=headers, json={"items": items}
    )
    assert ingested.status_code == 200, ingested.text
    assert ingested.json()["data"] == {"inserted": 3, "updated": 0, "series_count": 1}

    # 幂等：同 (run, series, date) 再写入为更新而非新增
    again = client.post(
        "/api/v1/forecast-runs/%d/results" % run["id"], headers=headers, json={"items": items}
    )
    assert again.json()["data"] == {"inserted": 0, "updated": 3, "series_count": 1}

    listed = client.get("/api/v1/forecast-runs/%d/results" % run["id"], headers=headers)
    assert listed.json()["data"]["total"] == 3

    # 区间越界应被拒绝（批次仍在 RUNNING）
    bad = client.post(
        "/api/v1/forecast-runs/%d/results" % run["id"],
        headers=headers,
        json={
            "items": [
                {
                    "material_id": material_id,
                    "warehouse_id": warehouse_id,
                    "forecast_date": date.today().isoformat(),
                    "horizon_step": 1,
                    "y_hat": "5",
                    "y_lower": "10",
                    "y_upper": "15",
                }
            ]
        },
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == 10001

    finished = client.post(
        "/api/v1/forecast-runs/%d/finish" % run["id"], headers=headers, json={"status": "SUCCESS"}
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["status"] == "SUCCESS"
    assert finished.json()["data"]["duration_ms"] is not None

    # 已结束批次不可重复结束
    conflict = client.post(
        "/api/v1/forecast-runs/%d/finish" % run["id"], headers=headers, json={"status": "SUCCESS"}
    )
    assert conflict.status_code == 409


def test_forecast_permission_denied(client, login, seeded):
    viewer = login("viewer", "viewer123")
    denied = client.post("/api/v1/forecast-runs", headers=viewer, json={"horizon_days": 7})
    assert denied.status_code == 403
    denied_list = client.get("/api/v1/forecast-runs", headers=viewer)
    assert denied_list.status_code == 403


def test_demand_series_meta_upsert(client, procurement_master):
    headers = procurement_master["admin"]
    payload = {
        "material_id": procurement_master["material_id"],
        "warehouse_id": procurement_master["warehouse_id"],
        "mean_daily": "10",
        "std_daily": "2",
        "demand_class": "SMOOTH",
        "abc_class": "A",
    }
    first = client.post("/api/v1/demand-series-meta", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["series_key"] == "%d:%d" % (
        procurement_master["material_id"],
        procurement_master["warehouse_id"],
    )

    second = client.post("/api/v1/demand-series-meta", headers=headers, json={**payload, "std_daily": "3"})
    assert Decimal(second.json()["data"]["std_daily"]) == Decimal("3")

    listed = client.get(
        "/api/v1/demand-series-meta",
        headers=headers,
        params={"material_id": procurement_master["material_id"]},
    )
    assert listed.json()["data"]["total"] == 1


def test_model_registry_unique_and_validation(client, procurement_master):
    headers = procurement_master["admin"]
    payload = {
        "model_code": "lightgbm-demand",
        "model_type": "LIGHTGBM",
        "version": "v1",
        "metrics": {"mase": 0.901},
        "is_active": True,
    }
    created = client.post("/api/v1/model-registry", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    duplicate = client.post("/api/v1/model-registry", headers=headers, json=payload)
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/model-registry", headers=headers)
    assert listed.json()["data"]["total"] == 1
    model_id = created.json()["data"]["id"]
    fetched = client.get("/api/v1/model-registry/%d" % model_id, headers=headers)
    assert fetched.json()["data"]["model_code"] == "lightgbm-demand"

    invalid = client.post(
        "/api/v1/model-registry",
        headers=headers,
        json={"model_code": "x", "model_type": "NOT_A_MODEL", "version": "v1"},
    )
    assert invalid.status_code == 422
