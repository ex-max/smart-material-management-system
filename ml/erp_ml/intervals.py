"""预测区间：经验残差法（LightGBM 面板残差 / Croston 重放残差）。

口径（与 forecast-experiment 技能一致，方法写进 CHANGELOG/progress）：
- 对每条序列，用**训练窗内**的 in-sample 残差（实际 − 拟合）标准差 σ 估计噪声尺度；
- 区间 = 点预测 ± z·σ（正态近似），下限截断 0（需求非负）；
- 95% 区间 z=1.959964（本批落库 y_lower/y_upper 的档位）；
- 80% 区间 z=1.281552（仅作方法说明，forecast_result 只有一对区间列，不落库）。

严格性：残差只用训练窗（origin 之前）的观测计算，不使用未来信息。
局限：区间宽度在 horizon 内恒定（iid 残差近似），未随步长扩张——已记入 progress 已知坑。
"""

from __future__ import annotations

from statistics import NormalDist

import numpy as np

# 落库档位：95%（forecast_result 只有 y_lower/y_upper 一对列）
INTERVAL_LEVEL = 0.95
# 方法说明档位：80%（不落库，仅文档/论文口径）
INTERVAL_LEVEL_80 = 0.80


def z_score(level: float) -> float:
    """双侧置信水平 level 对应的标准正态分位数（如 0.95 -> 1.959964）。"""
    level = float(level)
    if not 0.0 < level < 1.0:
        raise ValueError("置信水平必须在 (0, 1) 内：" + str(level))
    return float(NormalDist().inv_cdf(0.5 + level / 2.0))


def residual_std(residuals) -> float:
    """残差样本标准差（忽略非有限值）；空/单点返回 0。"""
    arr = np.asarray(residuals, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size <= 1:
        return 0.0
    return float(np.std(arr, ddof=1))


def prediction_bounds(y_hat: float, sigma: float, level: float = INTERVAL_LEVEL) -> tuple[float, float]:
    """单点区间：返回 (lower, upper)，均截断到 >= 0，且保证 lower <= y_hat <= upper。"""
    y = max(float(y_hat), 0.0)
    s = max(float(sigma), 0.0)
    z = z_score(level)
    lower = max(min(y - z * s, y), 0.0)
    upper = max(y + z * s, y)
    return lower, upper


def interval_bounds_matrix(
    predictions: np.ndarray,
    sigmas: np.ndarray,
    level: float = INTERVAL_LEVEL,
) -> tuple[np.ndarray, np.ndarray]:
    """(horizon, n_series) 预测矩阵 -> (lower, upper) 同形状矩阵。"""
    pred = np.asarray(predictions, dtype=float)
    sig = np.asarray(sigmas, dtype=float).reshape(1, -1)
    z = z_score(level)
    lower = np.clip(pred - z * sig, 0.0, None)
    upper = np.clip(pred + z * sig, 0.0, None)
    return lower, upper
