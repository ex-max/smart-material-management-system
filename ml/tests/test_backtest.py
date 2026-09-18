import numpy as np

from erp_ml.backtest import backtest_series
from erp_ml.config import BacktestConfig

META = {
    "seed": 1,
    "series_key": "1:1",
    "material_id": 1,
    "warehouse_id": 1,
    "demand_class": "SMOOTH",
    "abc_class": "A",
}


def _seasonal_series(n: int = 300) -> np.ndarray:
    t = np.arange(n)
    return 10.0 + 3.0 * np.sin(2.0 * np.pi * t / 7.0) + (t % 5)


def test_backtest_series_rows_and_metrics():
    cfg = BacktestConfig(
        horizons=(7, 14),
        initial_train_days=60,
        step_days=7,
        models=("naive", "ma7", "ets"),
        n_jobs=1,
    )
    rows = backtest_series(_seasonal_series(), cfg, META)
    assert len(rows) == 3 * 2
    for row in rows:
        assert row["n_origins"] > 0
        assert row["series_key"] == "1:1"
        assert row["horizon"] in (7, 14)
        assert np.isfinite(row["mae"]) and np.isfinite(row["rmse"]) and np.isfinite(row["smape"])


def test_backtest_only_uses_past():
    cfg = BacktestConfig(
        horizons=(7,),
        initial_train_days=60,
        step_days=1000,
        models=("naive",),
        n_jobs=1,
    )
    values = np.concatenate([np.full(60, 1.0), np.full(100, 999.0)])
    rows = backtest_series(values, cfg, META)
    assert len(rows) == 1
    assert rows[0]["mae"] == abs(999.0 - 1.0)


def test_backtest_too_short_returns_empty():
    cfg = BacktestConfig(horizons=(30,), initial_train_days=180, step_days=7)
    assert backtest_series(np.zeros(100), cfg, META) == []
