"""预测模型：Naive / 季节 Naive / 移动平均 / ETS / ARIMA / Croston / TSB。

约定：输入训练序列（一维），输出未来 horizon 步的点预测（长度 horizon）。
任一单序列模型失败时回退季节 Naive，保证回测不被打断。

分层映射（forecast-experiment 技能）：
平滑/波动 -> LightGBM（对比 ARIMA）；间歇/块状 -> Croston（对比 TSB）。
LightGBM 为面板级全局模型，见 erp_ml.gbm，不在此单序列接口内。
"""

from __future__ import annotations

import warnings

import numpy as np

# ADI/CV² 象限 -> 主用模型 / 对比模型（论文「模型映射」小节）
SEGMENT_MODEL_MAP = {
    "SMOOTH": "lightgbm",
    "ERRATIC": "lightgbm",
    "INTERMITTENT": "croston",
    "LUMPY": "croston",
}
SEGMENT_COMPARISON_MAP = {
    "SMOOTH": "arima",
    "ERRATIC": "arima",
    "INTERMITTENT": "tsb",
    "LUMPY": "tsb",
}


def model_codes() -> tuple[str, ...]:
    return ("naive", "seasonal_naive", "ma7", "ma28", "ets")


def extended_model_codes() -> tuple[str, ...]:
    return ("naive", "seasonal_naive", "ma7", "ma28", "ets", "arima", "croston", "tsb")


def recommend_model(demand_class: str) -> str:
    """按 ADI/CV² 象限给出主用模型。"""
    return SEGMENT_MODEL_MAP.get(demand_class, "lightgbm")


def comparison_model(demand_class: str) -> str:
    return SEGMENT_COMPARISON_MAP.get(demand_class, "arima")


def model_mapping() -> dict[str, dict[str, str]]:
    return {
        segment: {"primary": SEGMENT_MODEL_MAP[segment], "comparison": SEGMENT_COMPARISON_MAP[segment]}
        for segment in SEGMENT_MODEL_MAP
    }


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
    if model == "arima":
        return _arima_forecast(train, horizon, season)
    if model == "croston":
        return _croston_forecast(train, horizon)
    if model == "tsb":
        return _tsb_forecast(train, horizon)
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


def _arima_forecast(train: np.ndarray, horizon: int, season: int) -> np.ndarray:
    """ARIMA(0,1,1)，Hannan–Rissanen 快速估计；失败回退季节 Naive。

    差分后的 MA(1) 与指数平滑族同源，作为平滑/波动象限的经典对比模型；
    Hannan–Rissanen 避免每个 origin 做非线性 MLE 优化（回测算力考虑）。
    """
    from statsmodels.tsa.arima.model import ARIMA

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = ARIMA(train, order=(0, 1, 1)).fit(method="hannan_rissanen")
        result = np.asarray(fitted.forecast(horizon), dtype=float)
        result = np.clip(result, 0.0, None)
        if result.size == horizon and np.all(np.isfinite(result)):
            return result
    except Exception:
        pass
    return _seasonal_naive(train, horizon, season)


def _croston_forecast(train: np.ndarray, horizon: int, alpha: float = 0.1, beta: float = 0.1) -> np.ndarray:
    """Croston 方法：对非零需求量和需求间隔分别做 SES，预测 = 量/间隔。

    只在需求发生时更新（经典 Croston）。全零序列返回 0。
    """
    train = np.asarray(train, dtype=float)
    z_hat: float | None = None
    q_hat: float | None = None
    last_nonzero: int | None = None
    for t, value in enumerate(train):
        if value <= 0:
            continue
        interval = float(t - last_nonzero) if last_nonzero is not None else 1.0
        if z_hat is None:
            z_hat = float(value)
            q_hat = interval
        else:
            z_hat = z_hat + alpha * (float(value) - z_hat)
            assert q_hat is not None
            q_hat = q_hat + beta * (interval - q_hat)
        last_nonzero = t
    if z_hat is None or q_hat is None or q_hat <= 0:
        return np.zeros(horizon)
    return np.repeat(z_hat / q_hat, horizon)


def _tsb_forecast(train: np.ndarray, horizon: int, alpha: float = 0.2, beta: float = 0.2) -> np.ndarray:
    """Teunter–Syntetos–Babai：每期更新发生概率，需求量只在发生时更新。"""
    train = np.asarray(train, dtype=float)
    z_hat: float | None = None
    p_hat = 0.0
    for value in train:
        occurred = value > 0
        if occurred:
            if z_hat is None:
                z_hat = float(value)
            else:
                z_hat = z_hat + alpha * (float(value) - z_hat)
        p_hat = p_hat + beta * ((1.0 if occurred else 0.0) - p_hat)
    if z_hat is None or p_hat <= 0:
        return np.zeros(horizon)
    return np.repeat(p_hat * z_hat, horizon)
