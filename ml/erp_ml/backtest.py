"""expanding-window rolling-origin 回测。

协议（forecast-experiment 技能）：初始训练窗 ≥180 天、步长 7 天、horizon 7/14/30；
**禁止**随机切分与未来信息。每个 origin 只用 ``values[:origin]`` 训练。
"""

from __future__ import annotations

import time
from collections import defaultdict

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from .config import BacktestConfig
from .metrics import mase_denominator, mase_from_error, smape
from .models import forecast


def backtest_series(values: np.ndarray, cfg: BacktestConfig, meta: dict) -> list[dict]:
    values = np.asarray(values, dtype=float)
    n = values.size
    max_h = cfg.max_horizon
    if n < cfg.initial_train_days + max_h:
        return []

    accumulator: dict[tuple[str, int], dict[str, list[float]]] = defaultdict(
        lambda: {"abs_err": [], "sq_err": [], "smape": [], "mase": []}
    )
    model_seconds: dict[str, float] = defaultdict(float)
    n_origins = 0

    for origin in range(cfg.initial_train_days, n - max_h + 1, cfg.step_days):
        n_origins += 1
        train = values[:origin]
        denominator = mase_denominator(train, cfg.season_length)
        forecasts: dict[str, np.ndarray] = {}
        for model in cfg.models:
            started = time.perf_counter()
            forecasts[model] = forecast(model, train, max_h, cfg.season_length)
            model_seconds[model] += time.perf_counter() - started
        for horizon in cfg.horizons:
            actual = float(values[origin + horizon - 1])
            for model, prediction in forecasts.items():
                predicted = float(prediction[horizon - 1])
                error = actual - predicted
                bucket = accumulator[(model, int(horizon))]
                bucket["abs_err"].append(abs(error))
                bucket["sq_err"].append(error * error)
                bucket["smape"].append(smape([actual], [predicted]))
                bucket["mase"].append(mase_from_error(error, denominator))

    rows = []
    for (model, horizon), bucket in accumulator.items():
        abs_err = np.asarray(bucket["abs_err"], dtype=float)
        sq_err = np.asarray(bucket["sq_err"], dtype=float)
        mase_values = np.asarray(bucket["mase"], dtype=float)
        rows.append(
            {
                **meta,
                "model": model,
                "horizon": int(horizon),
                "n_origins": int(abs_err.size),
                "mae": float(abs_err.mean()),
                "rmse": float(np.sqrt(sq_err.mean())),
                "smape": float(np.mean(bucket["smape"])),
                "mase": float(np.nanmean(mase_values)) if np.isfinite(mase_values).any() else float("nan"),
                "seconds": float(model_seconds[model]),
            }
        )
    return rows


def run_backtest(
    values_list: list[np.ndarray],
    meta_list: list[dict],
    cfg: BacktestConfig,
    n_jobs: int | None = None,
) -> pd.DataFrame:
    jobs = cfg.n_jobs if n_jobs is None else n_jobs
    chunks = Parallel(n_jobs=jobs, prefer="processes")(
        delayed(backtest_series)(values, cfg, meta) for values, meta in zip(values_list, meta_list)
    )
    rows = [row for chunk in chunks for row in chunk]
    return pd.DataFrame(rows)


def backtest_global(
    values_list: list[np.ndarray],
    dates: pd.DatetimeIndex,
    meta_list: list[dict],
    cfg: BacktestConfig,
    forecaster,
    model_name: str,
) -> list[dict]:
    """面板级全局模型（如 LightGBM）的 rolling-origin 回测。

    与 backtest_series 同一 origin/horizon 口径，输出逐序列同一张指标表。
    forecaster 需实现 fit(history, dates, origin) 与
    forecast(history, dates, origin, horizon)（形状 horizon x n_series）。
    """
    values = np.column_stack([np.asarray(v, dtype=float) for v in values_list])
    n, n_series = values.shape
    max_h = cfg.max_horizon
    if n < cfg.initial_train_days + max_h:
        return []

    accumulator: dict[int, dict[int, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: {"abs_err": [], "sq_err": [], "smape": [], "mase": []})
    )
    n_origins = 0
    total_seconds = 0.0
    for origin in range(cfg.initial_train_days, n - max_h + 1, cfg.step_days):
        n_origins += 1
        started = time.perf_counter()
        forecaster.fit(values, dates, origin)
        predictions = forecaster.forecast(values, dates, origin, max_h)
        total_seconds += time.perf_counter() - started
        for j in range(n_series):
            denominator = mase_denominator(values[:origin, j], cfg.season_length)
            for horizon in cfg.horizons:
                actual = float(values[origin + horizon - 1, j])
                predicted = float(predictions[horizon - 1, j])
                error = actual - predicted
                bucket = accumulator[int(horizon)][j]
                bucket["abs_err"].append(abs(error))
                bucket["sq_err"].append(error * error)
                bucket["smape"].append(smape([actual], [predicted]))
                bucket["mase"].append(mase_from_error(error, denominator))

    seconds_per_series = total_seconds / max(n_series, 1)
    rows = []
    for j, meta in enumerate(meta_list):
        for horizon in cfg.horizons:
            bucket = accumulator[int(horizon)][j]
            abs_err = np.asarray(bucket["abs_err"], dtype=float)
            sq_err = np.asarray(bucket["sq_err"], dtype=float)
            mase_values = np.asarray(bucket["mase"], dtype=float)
            rows.append(
                {
                    **meta,
                    "model": model_name,
                    "horizon": int(horizon),
                    "n_origins": int(abs_err.size),
                    "mae": float(abs_err.mean()),
                    "rmse": float(np.sqrt(sq_err.mean())),
                    "smape": float(np.mean(bucket["smape"])),
                    "mase": (
                        float(np.nanmean(mase_values)) if np.isfinite(mase_values).any() else float("nan")
                    ),
                    "seconds": float(seconds_per_series),
                }
            )
    return rows
