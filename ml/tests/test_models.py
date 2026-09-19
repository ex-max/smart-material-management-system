"""模型测试：Croston / TSB / ARIMA 与 ADI/CV² 分层映射。"""

import numpy as np

from erp_ml.models import (
    comparison_model,
    extended_model_codes,
    forecast,
    model_mapping,
    recommend_model,
)


def test_croston_flat_intermittent():
    train = np.zeros(100)
    train[::5] = 4.0  # 每 5 天出现一次，需求量恒定
    out = forecast("croston", train, 7)
    assert out.shape == (7,)
    assert np.all(out > 0)
    assert np.allclose(out, out[0])


def test_croston_all_zero_returns_zeros():
    out = forecast("croston", np.zeros(30), 5)
    assert np.all(out == 0)


def test_tsb_probability_shrinks_demand():
    train = np.zeros(100)
    train[::10] = 10.0
    out = forecast("tsb", train, 4)
    assert out.shape == (4,)
    assert np.all(out >= 0)
    assert np.allclose(out, out[0])


def test_arima_finite_and_non_negative():
    t = np.arange(150, dtype=float)
    train = 20.0 + 5.0 * np.sin(2.0 * np.pi * t / 7.0)
    out = forecast("arima", train, 7)
    assert out.shape == (7,)
    assert np.all(np.isfinite(out))
    assert np.all(out >= 0)


def test_segment_model_mapping():
    assert recommend_model("SMOOTH") == "lightgbm"
    assert recommend_model("ERRATIC") == "lightgbm"
    assert recommend_model("INTERMITTENT") == "croston"
    assert recommend_model("LUMPY") == "croston"
    assert comparison_model("SMOOTH") == "arima"
    assert comparison_model("LUMPY") == "tsb"
    assert model_mapping()["ERRATIC"] == {"primary": "lightgbm", "comparison": "arima"}
    # LightGBM 是面板级模型，不在单序列代码列表里
    assert "lightgbm" not in extended_model_codes()
