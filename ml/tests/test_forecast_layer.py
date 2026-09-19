"""分层滚动预测输出结构测试（不触发 LightGBM）。"""

import numpy as np

from erp_ml.forecast_layer import LayeredForecast, forecast_matrix_for_series, horizon_mean


def test_forecast_matrix_for_series():
    paths = [
        np.array([[1.0, 10.0], [2.0, 20.0]]),
        np.array([[3.0, 30.0], [4.0, 40.0]]),
    ]
    layered = LayeredForecast(origins=[10, 17], horizon=2, paths=paths)
    matrix = forecast_matrix_for_series(layered, 0)
    assert matrix.shape == (2, 2)
    assert np.array_equal(matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_horizon_mean_handles_empty():
    assert horizon_mean(np.array([])) == 0.0
    assert horizon_mean(np.array([2.0, 4.0])) == 3.0


def test_empty_layered_forecast():
    layered = LayeredForecast(origins=[], horizon=7, paths=[])
    assert forecast_matrix_for_series(layered, 0).shape == (0, 7)
