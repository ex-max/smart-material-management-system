"""A/B 分层汇总与 Wilcoxon 检验测试。"""

import numpy as np
import pandas as pd
import pytest

from erp_ml.sim_experiment import AB_METRICS, ab_summary, wilcoxon_p_value


def test_wilcoxon_all_zero_returns_one():
    assert wilcoxon_p_value(np.zeros(10)) == 1.0
    assert wilcoxon_p_value(np.array([])) == 1.0


def test_wilcoxon_detects_consistent_shift():
    diffs = np.full(20, -1.0)
    assert wilcoxon_p_value(diffs) < 0.05


def _row(seed, series, strategy, offset):
    row = {
        "seed": seed,
        "series_key": series,
        "material_id": int(series.split(":")[0]),
        "warehouse_id": 1,
        "demand_class": "SMOOTH",
        "abc_class": "A",
        "strategy": strategy,
    }
    for metric in AB_METRICS:
        row[metric] = 1.0
    # B 的 total_cost 比 A 低 10（越小越好），fill_rate 比 A 高 0.05（越大越好）
    row["total_cost"] = offset - (10.0 if strategy == "B_FORECAST" else 0.0)
    row["holding_cost"] = offset
    row["fill_rate"] = 0.90 + (0.05 if strategy == "B_FORECAST" else 0.0)
    return row


def test_ab_summary_improvement_and_direction():
    rows = []
    for seed in (1, 2, 3):
        for j in (1, 2):
            rows.append(_row(seed, f"{j}:1", "A_FIXED", 100.0 + j))
            rows.append(_row(seed, f"{j}:1", "B_FORECAST", 100.0 + j))
    frame = pd.DataFrame(rows)
    summary = ab_summary(frame, ["ALL", "SMOOTH"])

    overall_cost = summary[(summary["segment"] == "ALL") & (summary["metric"] == "total_cost")].iloc[0]
    assert overall_cost["direction"] == "lower"
    assert overall_cost["improvement_B_minus_A"] == pytest.approx(10.0)
    assert overall_cost["n_pairs"] == 6
    assert overall_cost["n_seeds"] == 3

    overall_fill = summary[(summary["segment"] == "ALL") & (summary["metric"] == "fill_rate")].iloc[0]
    assert overall_fill["direction"] == "higher"
    assert overall_fill["improvement_B_minus_A"] == pytest.approx(0.05)

    # 分象限同样有 SMOOTH 行
    assert not summary[(summary["segment"] == "SMOOTH") & (summary["metric"] == "total_cost")].empty
    assert set(summary["segment"].unique()) == {"ALL", "SMOOTH"}
