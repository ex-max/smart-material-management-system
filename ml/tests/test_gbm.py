"""LightGBM 面板全局模型与全局回测测试。"""

import numpy as np
import pandas as pd

from erp_ml.backtest import backtest_global
from erp_ml.config import BacktestConfig
from erp_ml.features import FeatureSpec
from erp_ml.gbm import DEFAULT_LGB_PARAMS, LGBMForecaster

META = [
    {
        "seed": 1,
        "series_key": "1:1",
        "material_id": 1,
        "warehouse_id": 1,
        "demand_class": "SMOOTH",
        "abc_class": "A",
    },
    {
        "seed": 1,
        "series_key": "2:1",
        "material_id": 2,
        "warehouse_id": 1,
        "demand_class": "ERRATIC",
        "abc_class": "B",
    },
]


def _spec() -> FeatureSpec:
    return FeatureSpec(lags=(1, 7), rolls=(7,), stats=("mean",))


def _fast_params() -> dict:
    return {**DEFAULT_LGB_PARAMS, "num_threads": 1}


def test_global_backtest_produces_per_series_rows():
    rng = np.random.default_rng(0)
    values = rng.gamma(3.0, 2.0, size=(120, 2))
    dates = pd.date_range("2023-01-01", periods=120)
    cfg = BacktestConfig(horizons=(7,), initial_train_days=60, step_days=30, models=(), n_jobs=1)
    forecaster = LGBMForecaster(spec=_spec(), params=_fast_params(), num_boost_round=20)
    rows = backtest_global([values[:, 0], values[:, 1]], dates, META, cfg, forecaster, "lightgbm")
    assert len(rows) == 2
    for row in rows:
        assert row["model"] == "lightgbm"
        assert row["n_origins"] > 0
        assert np.isfinite(row["mae"]) and np.isfinite(row["rmse"]) and np.isfinite(row["smape"])


def test_forecast_ignores_future_actuals():
    rng = np.random.default_rng(1)
    history = rng.gamma(3.0, 2.0, size=(90, 1))
    dates = pd.date_range("2023-01-01", periods=90)
    forecaster = LGBMForecaster(spec=_spec(), params=_fast_params(), num_boost_round=10).fit(
        history, dates, 60
    )
    poisoned_a = history.copy()
    poisoned_a[60:] = 1e9
    poisoned_b = history.copy()
    poisoned_b[60:] = -5.0
    first = forecaster.forecast(poisoned_a, dates, 60, 7)
    second = forecaster.forecast(poisoned_b, dates, 60, 7)
    assert np.array_equal(first, second)
    assert np.all(first >= 0)


def test_lightgbm_is_deterministic():
    rng = np.random.default_rng(2)
    values = rng.gamma(3.0, 2.0, size=(80, 2))
    dates = pd.date_range("2023-01-01", periods=80)
    cfg = BacktestConfig(horizons=(7,), initial_train_days=40, step_days=30, models=(), n_jobs=1)
    row_a = backtest_global(
        [values[:, 0], values[:, 1]], dates, META, cfg,
        LGBMForecaster(spec=_spec(), params=_fast_params(), num_boost_round=15), "lightgbm",
    )
    row_b = backtest_global(
        [values[:, 0], values[:, 1]], dates, META, cfg,
        LGBMForecaster(spec=_spec(), params=_fast_params(), num_boost_round=15), "lightgbm",
    )
    assert np.allclose([r["smape"] for r in row_a], [r["smape"] for r in row_b])
