"""P4 预测区间测试：z 分位、经验残差 σ、区间边界与矩阵形状。"""

from __future__ import annotations

import numpy as np

from erp_ml.intervals import (
    INTERVAL_LEVEL,
    interval_bounds_matrix,
    prediction_bounds,
    residual_std,
    z_score,
)


def test_z_score_known_values():
    assert abs(z_score(0.95) - 1.959964) < 1e-4
    assert abs(z_score(0.80) - 1.281552) < 1e-4
    assert abs(z_score(INTERVAL_LEVEL) - 1.959964) < 1e-4


def test_z_score_rejects_invalid_level():
    for bad in (0.0, 1.0, 1.5, -0.2):
        try:
            z_score(bad)
        except ValueError:
            continue
        raise AssertionError("非法置信水平应报错：" + str(bad))


def test_residual_std_ignores_non_finite_and_small_samples():
    assert residual_std([]) == 0.0
    assert residual_std([5.0]) == 0.0
    assert residual_std([1.0, np.nan, 3.0, np.inf]) > 0.0


def test_prediction_bounds_clip_and_order():
    lower, upper = prediction_bounds(5.0, 2.0)  # z=1.959964 -> ±3.9199
    assert abs(lower - 1.08) < 1e-3
    assert abs(upper - 8.92) < 1e-3
    assert 0.0 <= lower <= 5.0 <= upper

    # 下限截断 0（需求非负）
    lower, upper = prediction_bounds(0.5, 1.0)
    assert lower == 0.0
    assert upper >= 0.5

    # σ=0 -> 退化点区间
    assert prediction_bounds(2.0, 0.0) == (2.0, 2.0)


def test_interval_bounds_matrix_shapes_and_constraints():
    pred = np.array([[1.0, 0.0], [2.0, 3.0]])
    sig = np.array([0.5, 1.0])
    lower, upper = interval_bounds_matrix(pred, sig)
    assert lower.shape == pred.shape and upper.shape == pred.shape
    assert np.all(lower >= 0.0)
    assert np.all(lower <= pred)
    assert np.all(upper >= pred)
