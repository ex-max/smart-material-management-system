"""预测精度指标：MAE / RMSE / sMAPE / MASE。

协议（forecast-experiment 技能）：零值多的序列禁用 MAPE，统一用 sMAPE；
MASE 以**季节 Naive**（m=7）的样本内 MAE 为分母。
"""

from __future__ import annotations

import numpy as np

EPS = 1e-9


def mae(y: np.ndarray, y_hat: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    y_hat = np.asarray(y_hat, dtype=float)
    return float(np.mean(np.abs(y - y_hat)))


def rmse(y: np.ndarray, y_hat: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    y_hat = np.asarray(y_hat, dtype=float)
    diff = y - y_hat
    return float(np.sqrt(np.mean(diff * diff)))


def smape(y: np.ndarray, y_hat: np.ndarray) -> float:
    """对称 MAPE（%）。分母为 0 时该项记 0，避免零值序列爆炸。"""
    y = np.asarray(y, dtype=float)
    y_hat = np.asarray(y_hat, dtype=float)
    denom = np.abs(y) + np.abs(y_hat)
    diff = np.abs(y - y_hat)
    term = np.zeros_like(diff)
    np.divide(2.0 * diff, denom, out=term, where=denom >= EPS)
    return float(100.0 * np.mean(term))


def mase_denominator(y_train: np.ndarray, season: int = 7) -> float:
    """季节 Naive 的样本内平均绝对误差；不足一个季节时返回 nan。"""
    y = np.asarray(y_train, dtype=float)
    if y.size <= season:
        return float("nan")
    return float(np.mean(np.abs(y[season:] - y[:-season])))


def mase_from_error(error: float, denominator: float) -> float:
    if denominator is None or not np.isfinite(denominator) or denominator < EPS:
        return float("nan")
    return float(abs(error) / denominator)
