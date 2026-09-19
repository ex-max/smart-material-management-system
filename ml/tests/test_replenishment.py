"""可解释补货建议与策略参数测试。"""

from erp_ml.inventory import PolicyParams
from erp_ml.replenishment import (
    POLICY_COLUMNS,
    SUGGESTION_COLUMNS,
    build_suggestion,
    policy_code,
    policy_row,
    rows_to_frame,
)

META = {
    "series_key": "1:1",
    "material_id": 1,
    "warehouse_id": 1,
    "demand_class": "SMOOTH",
}


def _policy(rop: float = 100.0, order_up_to: float = 140.0) -> PolicyParams:
    return PolicyParams(
        ss=20.0,
        rop=rop,
        order_up_to=order_up_to,
        eoq=50.0,
        lead_time_mean=8.0,
        sigma_d=5.0,
        forecast_daily=12.0,
        z_value=1.6449,
        service_level_type="CSL",
        service_level=0.95,
    )


def test_suggestion_below_rop_is_explainable():
    row = build_suggestion(
        "RS-2025-01-01-0001", 1, META, "lightgbm", _policy(rop=100.0, order_up_to=140.0),
        sigma_lt=2.9, current_qty=80.0, locked_qty=0.0, in_transit_qty=10.0, backorder_qty=0.0,
    )
    assert row["trigger_type"] == "BELOW_ROP"
    assert row["status"] == "OPEN"
    assert row["available_qty"] == 90.0
    assert row["suggested_qty"] == 50.0
    assert row["service_level_type"] == "CSL"
    assert row["model_code"] == "lightgbm"
    for field in ("available_qty", "rop", "order_up_to", "safety_stock", "daily_demand_hat", "parameter_source", "reason"):
        assert row[field] is not None
    assert "ROP" in row["reason"]
    assert "policy=FORECAST" in row["parameter_source"]
    assert "lightgbm" in row["parameter_source"]


def test_suggestion_above_rop_needs_no_order():
    row = build_suggestion(
        "RS-2025-01-01-0002", 1, META, "croston", _policy(rop=100.0),
        sigma_lt=2.9, current_qty=200.0, locked_qty=0.0, in_transit_qty=0.0, backorder_qty=5.0,
    )
    assert row["available_qty"] == 195.0
    assert row["trigger_type"] == "NONE"
    assert row["suggested_qty"] == 0.0
    assert row["status"] == "CLOSED"
    assert "无需补货" in row["reason"]


def test_policy_row_columns():
    row = policy_row(1, META, "FORECAST", _policy(), 7, 100.0, 0.2, 1.0, 1.0)
    for column in POLICY_COLUMNS:
        assert column in row
    assert row["strategy"] == "FORECAST"
    assert row["service_level_type"] == "CSL"
    assert row["order_up_to"] == 140.0
    assert row["eoq"] == 50.0
    assert policy_code(1, "1:1", "FIXED") == "POL-FIXED-S1-1-1"


def test_rows_to_frame_fills_missing_columns():
    frame = rows_to_frame([{"suggestion_no": "x"}], SUGGESTION_COLUMNS)
    assert list(frame.columns) == SUGGESTION_COLUMNS
    assert frame.loc[0, "current_qty"] is None
