"""M4 分层模型映射的滚动预测：每个 origin 重训 LightGBM，间歇/块状用 Croston。

与 M3/M4 回测口径完全一致（forecast-experiment 技能）：
初始训练窗 ≥180 天、步长 7 天、horizon 7/14/30；只用 origin 之前的观测。
输出按 origin 对齐的预测矩阵，供 M5 的动态 SS/ROP 与库存仿真消费。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .config import BacktestConfig
from .features import FeatureSpec
from .gbm import DEFAULT_LGB_PARAMS, LGBMForecaster
from .models import forecast, recommend_model


@dataclass
class LayeredForecast:
    origins: list[int] = field(default_factory=list)
    horizon: int = 0
    paths: list[np.ndarray] = field(default_factory=list)


def rolling_layered_forecast(
    values: np.ndarray,
    dates: pd.DatetimeIndex,
    demand_classes: list[str],
    cfg: BacktestConfig,
    spec: FeatureSpec | None = None,
    params: dict | None = None,
    num_boost_round: int = 300,
    progress: Callable[[int, int], None] | None = None,
) -> LayeredForecast:
    """按 ADI/CV² 象限映射产出每个 origin 的 (horizon, n_series) 预测矩阵。"""
    matrix = np.asarray(values, dtype=float)
    n_days, n_series = matrix.shape
    max_h = cfg.max_horizon
    origins = list(range(cfg.initial_train_days, n_days - max_h + 1, cfg.step_days))
    if not origins:
        return LayeredForecast(origins=[], horizon=max_h, paths=[])

    feature_spec = spec if spec is not None else FeatureSpec()
    lgb_params = params if params is not None else dict(DEFAULT_LGB_PARAMS)
    uses_lightgbm = any(recommend_model(str(cls)) == "lightgbm" for cls in demand_classes)
    croston_columns = [j for j, cls in enumerate(demand_classes) if recommend_model(str(cls)) != "lightgbm"]

    paths: list[np.ndarray] = []
    total = len(origins)
    for step, origin in enumerate(origins):
        combined = np.empty((max_h, n_series), dtype=float)
        if uses_lightgbm:
            forecaster = LGBMForecaster(spec=feature_spec, params=dict(lgb_params), num_boost_round=num_boost_round)
            forecaster.fit(matrix, dates, origin)
            combined[:] = forecaster.forecast(matrix, dates, origin, max_h)
        for j in croston_columns:
            combined[:, j] = forecast("croston", matrix[:origin, j], max_h, cfg.season_length)
        paths.append(combined)
        if progress is not None:
            progress(step + 1, total)
    return LayeredForecast(origins=origins, horizon=max_h, paths=paths)


def forecast_matrix_for_series(layered: LayeredForecast, series_index: int) -> np.ndarray:
    """取某条序列在全部 origin 的预测，形状 (n_origins, horizon)。"""
    if not layered.paths:
        return np.zeros((0, layered.horizon), dtype=float)
    return np.column_stack([path[:, series_index] for path in layered.paths]).T


def horizon_mean(forecast_series: np.ndarray) -> float:
    values = np.asarray(forecast_series, dtype=float)
    if values.size == 0:
        return 0.0
    mean = float(np.nanmean(values))
    return mean if np.isfinite(mean) else 0.0
