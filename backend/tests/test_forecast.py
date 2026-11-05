"""M6 预测模块测试：批次/结果/需求元数据/模型注册；P4 预测曲线接口。"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.model.inventory import Inventory, InventoryBatch, InventoryTransaction


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


def _seed_forecast_curve(client, db_session, master, run_start="2026-09-20"):
    """造：一个 SUPERVISOR 批次（含 95% 区间）+ 库存结存/批次 + 出库/盘亏/调拨流水。"""
    material_id = master["material_id"]
    warehouse_id = master["warehouse_id"]
    headers = master["admin"]

    run = client.post(
        "/api/v1/forecast-runs",
        headers=headers,
        json={
            "horizon_days": 3,
            "forecast_start_date": run_start,
            "train_end_date": "2026-09-19",
            "series_count": 1,
        },
    ).json()["data"]
    start = datetime.fromisoformat(run_start).date()
    items = [
        {
            "material_id": material_id,
            "warehouse_id": warehouse_id,
            "forecast_date": (start + timedelta(days=step - 1)).isoformat(),
            "horizon_step": step,
            "y_hat": str(10 + step),
            "y_lower": str(8 + step),
            "y_upper": str(12 + step),
            "model_code": "lightgbm_demand",
            "model_version": "v2-test",
            "demand_class": "SMOOTH",
        }
        for step in range(1, 4)
    ]
    client.post("/api/v1/forecast-runs/%d/results" % run["id"], headers=headers, json={"items": items})
    client.post("/api/v1/forecast-runs/%d/finish" % run["id"], headers=headers, json={"status": "SUCCESS"})

    batch = InventoryBatch(
        material_id=material_id,
        warehouse_id=warehouse_id,
        batch_no="__DEFAULT__",
        is_default=True,
        quantity=Decimal("500"),
        status="NORMAL",
    )
    db_session.add(batch)
    db_session.flush()
    db_session.add(Inventory(material_id=material_id, warehouse_id=warehouse_id, quantity=Decimal("500")))

    def txn(day, qty, txn_type, source_type):
        db_session.add(
            InventoryTransaction(
                material_id=material_id,
                warehouse_id=warehouse_id,
                batch_id=batch.id,
                quantity=Decimal(qty),
                txn_type=txn_type,
                source_type=source_type,
                occurred_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc),
            )
        )

    # 窗口内：出库 -7 + 盘亏 -2 => 2026-09-19 消耗 9；窗口起点日 2026-08-21 出库 -3
    txn(date(2026, 9, 19), "-7", "OUTBOUND", "OUTBOUND")
    txn(date(2026, 9, 19), "-2", "STOCKTAKE_LOSS", "STOCKTAKE")
    txn(date(2026, 8, 21), "-3", "OUTBOUND", "OUTBOUND")
    # 不计入消耗：调拨出、入库、窗口外
    txn(date(2026, 9, 19), "-50", "TRANSFER_OUT", "TRANSFER")
    txn(date(2026, 9, 19), "100", "INBOUND", "INBOUND")
    txn(date(2026, 8, 20), "-100", "OUTBOUND", "OUTBOUND")
    db_session.commit()
    return run, material_id, warehouse_id


def test_forecast_curve_returns_history_and_interval(client, db_session, procurement_master):
    run, material_id, warehouse_id = _seed_forecast_curve(client, db_session, procurement_master)
    headers = procurement_master["admin"]

    resp = client.get(
        "/api/v1/forecast/curves",
        headers=headers,
        params={"material_id": material_id, "warehouse_id": warehouse_id, "history_days": 30},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["run_id"] == run["id"]
    assert data["run_status"] == "SUCCESS"
    assert data["model_code"] == "lightgbm_demand"
    assert data["demand_class"] == "SMOOTH"
    assert data["interval_level"] == 0.95
    assert abs(data["interval_z"] - 1.959964) < 1e-3

    # 未来 3 步预测（含区间），按日期升序
    assert len(data["forecast"]) == 3
    steps = [p["horizon_step"] for p in data["forecast"]]
    assert steps == [1, 2, 3]
    first = data["forecast"][0]
    assert Decimal(first["y_hat"]) == Decimal("11")
    assert Decimal(first["y_lower"]) == Decimal("9")
    assert Decimal(first["y_upper"]) == Decimal("13")
    assert first["date"] == "2026-09-20"

    # 近 30 天历史（2026-08-21 ~ 2026-09-19 逐日补零）
    history = data["history"]
    assert len(history) == 30
    assert history[0]["date"] == "2026-08-21"
    assert history[-1]["date"] == "2026-09-19"
    by_date = {p["date"]: Decimal(p["actual_qty"]) for p in history}
    assert by_date["2026-09-19"] == Decimal("9")  # 出库 7 + 盘亏 2
    assert by_date["2026-08-21"] == Decimal("3")  # 窗口起点日
    assert by_date["2026-09-18"] == Decimal("0")
    # 调拨出/入库/窗口外都不计入
    assert by_date["2026-09-19"] != Decimal("59")


def test_forecast_curve_without_run_returns_empty_forecast(client, db_session, procurement_master):
    headers = procurement_master["admin"]
    resp = client.get(
        "/api/v1/forecast/curves",
        headers=headers,
        params={
            "material_id": procurement_master["batch_material_id"],
            "warehouse_id": procurement_master["warehouse_id"],
            "history_days": 7,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["run_id"] is None and data["run_no"] is None
    assert data["forecast"] == []
    assert len(data["history"]) == 7
    assert all(Decimal(p["actual_qty"]) == Decimal("0") for p in data["history"])


def test_forecast_curve_permissions(client, db_session, procurement_master, login):
    material_id = procurement_master["material_id"]
    warehouse_id = procurement_master["warehouse_id"]
    params = {"material_id": material_id, "warehouse_id": warehouse_id}

    anonymous = client.get("/api/v1/forecast/curves", params=params)
    assert anonymous.status_code == 401

    viewer = login("viewer", "viewer123")
    denied = client.get("/api/v1/forecast/curves", headers=viewer, params=params)
    assert denied.status_code == 403

    admin = procurement_master["admin"]
    allowed = client.get("/api/v1/forecast/curves", headers=admin, params=params)
    assert allowed.status_code == 200
