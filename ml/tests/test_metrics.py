import numpy as np

from erp_ml.metrics import mae, mase_denominator, mase_from_error, rmse, smape


def test_mae_rmse():
    y = np.array([1.0, 2.0, 3.0])
    y_hat = np.array([1.0, 2.0, 5.0])
    assert mae(y, y_hat) == 2.0 / 3.0
    assert np.isclose(rmse(y, y_hat), np.sqrt(4.0 / 3.0))


def test_smape_zero_guard():
    assert smape([0.0], [0.0]) == 0.0
    assert 0.0 < smape([1.0], [0.0]) <= 200.0


def test_mase_denominator_and_error():
    y = np.arange(1, 15, dtype=float)
    denominator = mase_denominator(y, 7)
    assert denominator == 7.0
    assert mase_from_error(3.5, denominator) == 0.5
    assert np.isnan(mase_from_error(1.0, float("nan")))


def test_mase_short_series():
    assert np.isnan(mase_denominator([1.0, 2.0, 3.0], 7))
