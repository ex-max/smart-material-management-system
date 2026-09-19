"""因果特征工程：滞后 / 滑动 / 日历 / 序列静态特征。

协议（forecast-experiment 技能）：**禁止未来信息**。对目标时刻 t 的每个特征，
只允许使用 t 之前的观测；静态序列特征只用训练窗（origin 之前）计算。
因此本模块所有函数都显式接收 origin / 已知历史，未来位置写 NaN 也不会影响
t 行之前的特征值。

样本排布：(目标时刻 t, 序列 j)，t 为主序、j 为次序（与 values.reshape(-1) 一致）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

EPS = 1e-9

DEFAULT_LAGS = (1, 2, 3, 7, 14, 28)
DEFAULT_ROLLS = (7, 14, 28)
DEFAULT_STATS = ("mean", "std", "nonzero")

CALENDAR_NAMES = ("dow_sin", "dow_cos", "month_sin", "month_cos", "is_weekend", "doy_sin", "doy_cos")
STATIC_NAMES = ("stat_log_mean", "stat_cv2", "stat_nonzero_ratio", "stat_adi")


@dataclass(frozen=True)
class FeatureSpec:
    """特征规格（进入 config.json，保证可复现）。"""

    lags: tuple[int, ...] = DEFAULT_LAGS
    rolls: tuple[int, ...] = DEFAULT_ROLLS
    stats: tuple[str, ...] = DEFAULT_STATS
    use_calendar: bool = True
    use_static: bool = True

    @property
    def min_history(self) -> int:
        longest = max((*self.lags, *self.rolls), default=0)
        return int(longest)

    def feature_names(self, n_series: int = 0) -> list[str]:
        names: list[str] = [f"lag_{lag}" for lag in self.lags]
        for window in self.rolls:
            for stat in self.stats:
                names.append(f"roll{window}_{stat}")
        if self.rolls:
            names.append("days_since_nonzero")
        if self.use_calendar:
            names.extend(CALENDAR_NAMES)
        if self.use_static:
            names.extend(STATIC_NAMES)
        return names

    def to_dict(self) -> dict:
        return {
            "lags": list(self.lags),
            "rolls": list(self.rolls),
            "stats": list(self.stats),
            "use_calendar": self.use_calendar,
            "use_static": self.use_static,
        }


def calendar_features(dates: pd.DatetimeIndex) -> np.ndarray:
    index = pd.DatetimeIndex(dates)
    dow = index.dayofweek.to_numpy(dtype=float)
    month = index.month.to_numpy(dtype=float)
    doy = index.dayofyear.to_numpy(dtype=float)
    two_pi = 2.0 * np.pi
    return np.column_stack(
        [
            np.sin(two_pi * dow / 7.0),
            np.cos(two_pi * dow / 7.0),
            np.sin(two_pi * month / 12.0),
            np.cos(two_pi * month / 12.0),
            (dow >= 5).astype(float),
            np.sin(two_pi * doy / 365.25),
            np.cos(two_pi * doy / 365.25),
        ]
    )


def _lag_block(history: np.ndarray, lag: int) -> np.ndarray:
    out = np.full_like(history, np.nan, dtype=float)
    if history.shape[0] > lag:
        out[lag:] = history[:-lag]
    return out


def _roll_mean(history: np.ndarray, window: int) -> np.ndarray:
    n, m = history.shape
    clean = np.nan_to_num(history, nan=0.0)
    csum = np.zeros((n + 1, m), dtype=float)
    np.cumsum(clean, axis=0, out=csum[1:])
    out = np.full((n, m), np.nan, dtype=float)
    if n > window:
        idx = np.arange(window, n)
        out[window:] = (csum[idx] - csum[idx - window]) / float(window)
    return out


def _roll_std(history: np.ndarray, window: int) -> np.ndarray:
    n, m = history.shape
    clean = np.nan_to_num(history, nan=0.0)
    csum = np.zeros((n + 1, m), dtype=float)
    csq = np.zeros((n + 1, m), dtype=float)
    np.cumsum(clean, axis=0, out=csum[1:])
    np.cumsum(clean * clean, axis=0, out=csq[1:])
    out = np.full((n, m), np.nan, dtype=float)
    if n > window:
        idx = np.arange(window, n)
        mean = (csum[idx] - csum[idx - window]) / float(window)
        var = (csq[idx] - csq[idx - window]) / float(window) - mean * mean
        out[window:] = np.sqrt(np.clip(var, 0.0, None))
    return out


def _roll_nonzero(history: np.ndarray, window: int) -> np.ndarray:
    positive = (history > 0).astype(float)
    return _roll_mean(positive, window)


def _days_since_nonzero(history: np.ndarray, cap: int) -> np.ndarray:
    """目标 t 之前最近一次正需求距今天数，截断到 cap；从未发生也记 cap。"""
    n, m = history.shape
    out = np.full((n, m), float(cap), dtype=float)
    last = np.full(m, -1, dtype=int)
    for t in range(n):
        known = last >= 0
        out[t, known] = np.minimum(t - last[known], cap)
        positive = history[t] > 0
        last = np.where(positive, t, last)
    return out


def series_static(history: np.ndarray) -> np.ndarray:
    """序列级静态特征，只用已知历史（形状 (n_series, len(STATIC_NAMES))）。"""
    hist = np.asarray(history, dtype=float)
    if hist.size == 0:
        return np.zeros((hist.shape[1] if hist.ndim == 2 else 0, len(STATIC_NAMES)))
    mean = np.nanmean(hist, axis=0)
    std = np.nanstd(hist, axis=0)
    nonzero_ratio = np.nanmean(hist > 0, axis=0)
    adi = np.where(mean > 0, 1.0 / np.maximum(nonzero_ratio, EPS), float(hist.shape[0]))
    cv2 = (std / np.maximum(mean, EPS)) ** 2
    return np.column_stack([np.log1p(mean), cv2, nonzero_ratio, adi])


def _assemble(
    history: np.ndarray,
    dates: pd.DatetimeIndex,
    spec: FeatureSpec,
    static: np.ndarray,
    rows: np.ndarray,
) -> tuple[np.ndarray, list[str]]:
    """按 rows（目标时刻）拼特征，返回 (X, names)；行序为 t 主序、序列次序。"""
    rows = np.atleast_1d(np.asarray(rows, dtype=int))
    n_series = history.shape[1]
    blocks: list[np.ndarray] = []
    names: list[str] = []

    for lag in spec.lags:
        block = _lag_block(history, lag)[rows]
        blocks.append(block.reshape(-1, 1))
        names.append(f"lag_{lag}")
    for window in spec.rolls:
        stats = {
            "mean": _roll_mean(history, window),
            "std": _roll_std(history, window),
            "nonzero": _roll_nonzero(history, window),
        }
        for stat in spec.stats:
            blocks.append(stats[stat][rows].reshape(-1, 1))
            names.append(f"roll{window}_{stat}")

    n_rows = rows.size
    if spec.rolls:
        blocks.append(_days_since_nonzero(history, spec.min_history)[rows].reshape(-1, 1))
        names.append("days_since_nonzero")
    if spec.use_calendar:
        calendar = calendar_features(pd.DatetimeIndex(dates)[rows])
        blocks.append(np.repeat(calendar, n_series, axis=0))
        names.extend(CALENDAR_NAMES)
    if spec.use_static:
        blocks.append(np.tile(static, (n_rows, 1)))
        names.extend(STATIC_NAMES)

    if blocks:
        return np.column_stack(blocks), names
    return np.zeros((n_rows * n_series, 0)), names


def build_panel_training(
    history: np.ndarray,
    dates: pd.DatetimeIndex,
    origin: int,
    spec: FeatureSpec,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """监督训练集，只用 history[:origin]。

    返回 (X, y, series_index, row_index, static)；
    series_index 标明每个样本属于哪条序列，static 供预测时复用。
    """
    hist = np.asarray(history, dtype=float)[:origin]
    static = series_static(hist)
    start = spec.min_history
    rows = np.arange(start, origin)
    X, _ = _assemble(hist, dates, spec, static, rows)
    y = hist[rows].reshape(-1)
    series_index = np.tile(np.arange(hist.shape[1]), rows.size)
    row_index = np.repeat(rows, hist.shape[1])
    return X, y, series_index, row_index, static


def build_panel_features(
    history: np.ndarray,
    dates: pd.DatetimeIndex,
    spec: FeatureSpec,
    static: np.ndarray,
    rows: np.ndarray,
) -> np.ndarray:
    """预测用特征矩阵；history 中未来位置可以是 NaN 或已写入的预测值。"""
    X, _ = _assemble(np.asarray(history, dtype=float), dates, spec, static, rows)
    return X


def build_row_features(
    history: np.ndarray,
    dates: pd.DatetimeIndex,
    spec: FeatureSpec,
    static: np.ndarray,
    target: int,
) -> np.ndarray:
    """只算单行（目标时刻 target）特征，用于递归多步预测。

    只取 target 之前 min_history 步的窗口，避免每个预测步都重算整条历史。
    """
    history = np.asarray(history, dtype=float)
    n_series = history.shape[1]
    window = spec.min_history
    segment = history[max(0, target - window):target]
    if segment.shape[0] < window:
        pad = np.full((window - segment.shape[0], n_series), np.nan, dtype=float)
        segment = np.vstack([pad, segment])
    arr = np.vstack([segment, np.full((1, n_series), np.nan, dtype=float)])
    local_dates = pd.DatetimeIndex(dates)[: target + 1][-(window + 1):]
    X, _ = _assemble(arr, local_dates, spec, static, np.array([window]))
    return X
