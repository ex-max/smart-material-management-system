"""基线预测模型：Naive / 季节 Naive / 移动平均 / ETS。

约定：输入训练序列（一维），输出未来 horizon 步的点预测（长度 horizon）。
ETS 单序列失败时回退季节 Naive，保证回测不被打断。
"""

from __future__ import annotations

import numpy as np


def model_codes() -> tuple[str, ...]:
    return ("naive", "seasonal_naive", "ma7", "ma28", "ets")


def _seasonal_naive(train: np.ndarray, horizon: int, season: int) -> np.ndarray:
    if train.size < season:
        return np.repeat(train[-1], horizon)
    repeats = int(np.ceil(horizon / season))
    return np.tile(train[-season:], repeats)[:horizon]


def forecast(model: str, train: np.ndarray, horizon: int, season: int = 7) -> np.ndarray:
    train = np.asarray(train, dtype=float)
    if train.size == 0:
        raise ValueError("训练序列为空")
    if model == "naive":
        return np.repeat(train[-1], horizon)
    if model == "seasonal_naive":
        return _seasonal_naive(train, horizon, season)
    if model.startswith("ma"):
        window = min(int(model[2:]), train.size)
        return np.repeat(float(train[-window:].mean()), horizon)
    if model == "ets":
        return _ets_forecast(train, horizon, season)
    raise ValueError(f"未知模型: {model}")


def _ets_forecast(train: np.ndarray, horizon: int, season: int) -> np.ndarray:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    try:
        model = ExponentialSmoothing(
            train,
            trend=None,
            seasonal="add",
            seasonal_periods=season,
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True)
        result = np.asarray(fitted.forecast(horizon), dtype=float)
        result = np.clip(result, 0.0, None)
        if result.size == horizon and np.all(np.isfinite(result)):
            return result
    except Exception:
        pass
    return _seasonal_naive(train, horizon, season)
