"""LSTM 预测器测试：形状/非负/确定性/无未来泄漏（未安装 torch 时跳过）。"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from erp_ml.lstm import LSTMForecaster  # noqa: E402


def _panel(n_series: int = 2, n_days: int = 90, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.gamma(shape=4.0, scale=2.0, size=n_series)
    noise = rng.normal(0.0, 1.0, size=(n_days, n_series))
    return np.clip(np.round(base + noise), 0.0, None)


def _dates(n_days: int = 90) -> pd.DatetimeIndex:
    return pd.date_range("2023-01-01", periods=n_days, freq="D")


def test_lstm_forecast_shape_and_nonnegative():
    values = _panel()
    forecaster = LSTMForecaster(lookback=14, hidden_size=8, epochs=2, batch_size=64, windows_per_series=20)
    forecaster.fit(values, _dates(), origin=60)
    predictions = forecaster.forecast(values, _dates(), origin=60, horizon=7)
    assert predictions.shape == (7, 2)
    assert np.all(np.isfinite(predictions))
    assert np.all(predictions >= 0)


def test_lstm_is_deterministic():
    values = _panel(seed=1)
    first = LSTMForecaster(lookback=14, hidden_size=8, epochs=2, batch_size=64, windows_per_series=20)
    second = LSTMForecaster(lookback=14, hidden_size=8, epochs=2, batch_size=64, windows_per_series=20)
    p1 = first.fit(values, _dates(), origin=60).forecast(values, _dates(), 60, 5)
    p2 = second.fit(values, _dates(), origin=60).forecast(values, _dates(), 60, 5)
    np.testing.assert_allclose(p1, p2, rtol=0, atol=0)


def test_lstm_uses_only_history():
    """改写 origin 之后的未来真实值，不应改变预测（无未来信息泄漏）。"""
    dates = _dates()
    values = _panel(seed=2)
    forecaster = LSTMForecaster(lookback=14, hidden_size=8, epochs=2, batch_size=64, windows_per_series=20)
    forecaster.fit(values, dates, origin=60)
    baseline = forecaster.forecast(values, dates, 60, 5)

    mutated = values.copy()
    mutated[60:] = mutated[60:] + 1000.0
    after = forecaster.forecast(mutated, dates, 60, 5)
    np.testing.assert_allclose(baseline, after, rtol=0, atol=0)
