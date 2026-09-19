"""特征工程测试：形状正确、严格因果（无未来信息）。"""

import numpy as np
import pandas as pd

from erp_ml.features import (
    FeatureSpec,
    build_panel_features,
    build_panel_training,
    build_row_features,
    series_static,
)


def _panel(n: int = 120, m: int = 3, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).gamma(3.0, 2.0, size=(n, m))


def test_training_shapes_and_ordering():
    spec = FeatureSpec(lags=(1, 7), rolls=(7,), stats=("mean", "std", "nonzero"))
    dates = pd.date_range("2023-01-01", periods=120)
    history = _panel()
    X, y, series_index, row_index, static = build_panel_training(history, dates, origin=60, spec=spec)
    assert X.shape == ((60 - 7) * 3, len(spec.feature_names()))
    assert y.shape[0] == X.shape[0]
    assert series_index.shape[0] == X.shape[0]
    assert int(row_index.max()) == 59
    assert static.shape == (3, 4)


def test_no_future_leakage_in_training():
    spec = FeatureSpec(lags=(1, 2, 7), rolls=(7, 14))
    dates = pd.date_range("2023-01-01", periods=120)
    history = _panel()
    poisoned = history.copy()
    poisoned[60:] = 1e6  # 未来区段全部改写
    X1, y1, *_ = build_panel_training(history, dates, 60, spec)
    X2, y2, *_ = build_panel_training(poisoned, dates, 60, spec)
    assert np.array_equal(X1, X2)
    assert np.array_equal(y1, y2)


def test_no_future_leakage_when_building_features():
    spec = FeatureSpec(lags=(1, 7), rolls=(7,))
    dates = pd.date_range("2023-01-01", periods=120)
    history = _panel()
    static = series_static(history[:60])
    work = history.copy()
    other = history.copy()
    other[63:] = -123.0  # 目标行 60/61/62 之外改写
    first = build_panel_features(work, dates, spec, static, np.array([60, 61, 62]))
    second = build_panel_features(other, dates, spec, static, np.array([60, 61, 62]))
    assert np.array_equal(first, second)


def test_row_features_match_panel_features():
    spec = FeatureSpec(lags=(1, 7), rolls=(7, 14))
    dates = pd.date_range("2023-01-01", periods=120)
    history = _panel()
    static = series_static(history[:60])
    rows = np.array([55, 60, 61, 62])
    panel = build_panel_features(history, dates, spec, static, rows)
    row_wise = np.vstack([build_row_features(history, dates, spec, static, int(t)) for t in rows])
    # 不同窗口长度的浮点累加会有极微差异，语义应一致
    assert np.allclose(panel, row_wise, equal_nan=True, rtol=1e-9, atol=1e-9)


def test_lag_feature_matches_history():
    spec = FeatureSpec(lags=(1, 7), rolls=(), use_calendar=False, use_static=False)
    dates = pd.date_range("2023-01-01", periods=40)
    history = np.arange(40, dtype=float).reshape(-1, 1)
    X, _, _, row_index, _ = build_panel_training(history, dates, origin=20, spec=spec)
    # 目标 t=10 的 lag_1 应为 history[9]
    position = int(np.nonzero(row_index == 10)[0][0])
    assert X[position, 0] == 9.0
    assert X[position, 1] == 3.0
