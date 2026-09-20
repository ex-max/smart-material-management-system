"""S2 同步脚本纯函数测试：批次幂等 token/marker、模型映射、payload 形状。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from erp_ml.sync_forecast import (
    MODEL_VERSION,
    POLICY_CODE,
    build_demand_meta_payloads,
    build_model_specs,
    build_policy_payload,
    build_result_payloads,
    find_existing_run,
    model_code_for,
    sync_token,
)


def _meta() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "series_key": "1:1",
                "material_id": 1,
                "warehouse_id": 1,
                "obs_days": 10,
                "non_zero_days": 8,
                "adi": 1.25,
                "cv2": 0.2,
                "demand_class": "SMOOTH",
                "abc_class": "A",
                "mean_daily": 5.0,
                "std_daily": 1.2,
                "data_start_date": "2023-01-01",
                "data_end_date": "2023-01-10",
            },
            {
                "series_key": "2:1",
                "material_id": 2,
                "warehouse_id": 1,
                "obs_days": 10,
                "non_zero_days": 3,
                "adi": 3.3333,
                "cv2": 0.5,
                "demand_class": "INTERMITTENT",
                "abc_class": "C",
                "mean_daily": 0.4,
                "std_daily": 0.6,
                "data_start_date": "2023-01-01",
                "data_end_date": "2023-01-10",
            },
        ]
    )


def test_sync_token_stable_and_parameter_sensitive():
    assert sync_token(14, 3, 3, 14, "v1") == sync_token(14, 3, 3, 14, "v1")
    assert sync_token(14, 3, 3, 14, "v1") != sync_token(1, 3, 3, 14, "v1")
    assert sync_token(14, 3, 3, 14, "v1") != sync_token(14, 3, 3, 30, "v1")
    assert sync_token(14, 3, 3, 14, "v1") != sync_token(14, 3, 3, 14, "v2")


def test_find_existing_run_matches_remark_token():
    runs = [
        {"id": 1, "remark": None},
        {"id": 2, "remark": "[SYNC] forecast-business-s14-y3-w3-h14-v1；catalog=db"},
        {"id": 3, "remark": "[SYNC] other-token"},
    ]
    found = find_existing_run(runs, "forecast-business-s14-y3-w3-h14-v1")
    assert found is not None and found["id"] == 2
    assert find_existing_run(runs, "missing") is None


def test_model_code_follows_segment_mapping():
    assert model_code_for("SMOOTH") == "lightgbm_demand"
    assert model_code_for("ERRATIC") == "lightgbm_demand"
    assert model_code_for("INTERMITTENT") == "croston_demand"
    assert model_code_for("LUMPY") == "croston_demand"


def test_build_demand_meta_payloads_cover_series():
    payloads = build_demand_meta_payloads(_meta(), "tok-1")
    assert [p["series_key"] for p in payloads] == ["1:1", "2:1"]
    assert payloads[0]["material_id"] == 1
    assert payloads[0]["warehouse_id"] == 1
    assert payloads[0]["demand_class"] == "SMOOTH"
    assert payloads[0]["abc_class"] == "A"
    assert payloads[0]["data_start_date"] == "2023-01-01"
    assert "tok-1" in payloads[0]["remark"]
    assert payloads[1]["demand_class"] == "INTERMITTENT"


def test_build_result_payloads_shape_and_model_mapping():
    horizon = 3
    predictions = np.array([[1.5, 0.0], [2.5, 0.2], [np.nan, 0.4]])
    dates = pd.date_range("2023-01-11", periods=horizon, freq="D")
    rows = build_result_payloads(_meta(), predictions, dates, horizon, MODEL_VERSION)
    assert len(rows) == 2 * horizon
    # 外层按序列、内层按步长
    assert [r["series_key"] for r in rows[:3]] == ["1:1", "1:1", "1:1"]
    assert [r["horizon_step"] for r in rows[:3]] == [1, 2, 3]
    assert rows[0]["forecast_date"] == "2023-01-11"
    assert rows[0]["model_code"] == "lightgbm_demand"
    assert rows[0]["model_version"] == MODEL_VERSION
    # 第二轮序列用 Croston
    assert rows[3]["series_key"] == "2:1"
    assert rows[3]["model_code"] == "croston_demand"
    # NaN 归零，数值保留 4 位
    assert rows[2]["y_hat"] == 0.0
    assert rows[1]["y_hat"] == 2.5


def test_build_model_specs_and_policy_contract():
    specs = build_model_specs({"calendar": ["dow", "month"]})
    codes = {spec["model_code"] for spec in specs}
    assert codes == {"lightgbm_demand", "croston_demand"}
    for spec in specs:
        assert spec["version"] == MODEL_VERSION
        assert spec["metrics"]["source_run"].startswith("2026")
        assert spec["is_active"] is True
    assert next(s for s in specs if s["model_code"] == "lightgbm_demand")["feature_config"] is not None

    policy = build_policy_payload()
    assert policy["policy_code"] == POLICY_CODE
    assert policy["strategy"] == "FORECAST"
    assert policy["service_level_type"] == "CSL"
    assert 0 < policy["service_level"] < 1
    assert policy["material_id"] is None and policy["warehouse_id"] is None
