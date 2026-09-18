"""需求过程生成：季节/周内 + 事件冲击 + Bernoulli–Gamma 四象限。

依据 ``docs/plan`` §5：需求形态按 ADI/CV² 四象限设计；间歇需求用
**Bernoulli–Gamma**（发生概率 p、需求量 Gamma 分布），提前期用**对数正态**。
生成器只产出文件，不写业务表。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .catalog import Catalog
from .config import GeneratorConfig

# 周一..周日相对权重（工作日高、周末低），再归一化到均值 1。
WEEKDAY_RAW = np.array([1.05, 1.10, 1.10, 1.08, 1.12, 0.70, 0.50])
WEEKDAY_RAW = WEEKDAY_RAW / WEEKDAY_RAW.mean()

# 四象限目标基线均值（对数尺度）：平滑/波动需求频繁且量较大；间歇/块状量小。
BASE_MEAN_LOG_MU = np.array([np.log(5.0), np.log(8.0), np.log(1.5), np.log(1.0)])
BASE_MEAN_MIN = np.array([1.5, 2.0, 0.5, 0.4])
BASE_MEAN_MAX = np.array([500.0, 500.0, 200.0, 200.0])


def target_shapes(cfg: GeneratorConfig) -> np.ndarray:
    return np.array([cfg.shape_smooth, cfg.shape_erratic, cfg.shape_intermittent, cfg.shape_lumpy])


def target_occurrence(cfg: GeneratorConfig) -> np.ndarray:
    return np.array([1.0, 1.0, cfg.intermittent_p, cfg.lumpy_p])


def assign_target_class(rng: np.random.Generator, n: int, cfg: GeneratorConfig) -> np.ndarray:
    probs = np.array([cfg.mix_smooth, cfg.mix_erratic, cfg.mix_intermittent, cfg.mix_lumpy], dtype=float)
    probs = probs / probs.sum()
    return rng.choice(4, size=n, p=probs)


def _monthly_factors(rng: np.random.Generator, months: np.ndarray, n_series: int, cfg: GeneratorConfig) -> np.ndarray:
    phase = rng.uniform(0.0, 2.0 * np.pi, size=n_series)
    base = 2.0 * np.pi * (months - 1) / 12.0
    factor = 1.0 + cfg.seasonal_amplitude * np.sin(base[:, None] + phase[None, :])
    factor += 0.5 * cfg.seasonal_amplitude * np.sin(2.0 * base[:, None] + 0.5 * phase[None, :])
    return np.clip(factor, 0.2, None)


def _weekday_factors(dow: np.ndarray, cfg: GeneratorConfig) -> np.ndarray:
    return 1.0 + cfg.weekday_amplitude * (WEEKDAY_RAW[dow] - 1.0)


def _event_multiplier(rng: np.random.Generator, n_days: int, n_series: int, cfg: GeneratorConfig) -> np.ndarray:
    events = np.ones((n_days, n_series), dtype=np.float64)
    if cfg.event_prob <= 0.0 or cfg.event_multiplier <= 1.0:
        return events
    hit = np.nonzero(rng.random(n_series) < cfg.event_prob)[0]
    for j in hit:
        k = int(rng.integers(1, cfg.event_max_per_sku + 1))
        starts = rng.integers(0, max(n_days - cfg.event_days, 1), size=k)
        multipliers = rng.uniform(cfg.event_multiplier * 0.7, cfg.event_multiplier * 1.3, size=k)
        for start, mult in zip(starts, multipliers):
            events[start:start + cfg.event_days, j] *= mult
    return events


def generate_demand(
    cfg: GeneratorConfig,
    catalog: Catalog,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex, np.ndarray]:
    """生成 SKU×仓库 日需求矩阵。

    返回 ``(demand, sku_idx, wh_idx, dates, target_class)``：
    demand 形状 (n_days, n_series)，序列 j 对应 (sku_idx[j], wh_idx[j])；
    target_class 是生成时设定的目标象限（0..3），用于核对生成保真度。
    """
    rng = np.random.default_rng(cfg.seed * 1000003 + 17)
    n_days = cfg.n_days
    dates = pd.date_range(cfg.start_date, periods=n_days, freq="D")
    months = dates.month.to_numpy()
    dow = dates.dayofweek.to_numpy()

    n_materials = catalog.n_materials
    n_wh = catalog.n_warehouses

    target = assign_target_class(rng, n_materials, cfg)
    log_mu = BASE_MEAN_LOG_MU[target]
    base_mean_material = np.clip(
        np.exp(rng.normal(log_mu, cfg.base_mean_log_sigma)),
        BASE_MEAN_MIN[target],
        BASE_MEAN_MAX[target],
    )
    shape = target_shapes(cfg)[target]
    p_occ = target_occurrence(cfg)[target]

    # 仓库间分配：Dirichlet，并保证每个仓库有最小份额。
    if n_wh == 1:
        shares = np.ones((n_materials, 1))
    else:
        shares = rng.dirichlet(np.full(n_wh, 0.6), size=n_materials)
        shares = np.clip(shares, 0.05, None)
        shares = shares / shares.sum(axis=1, keepdims=True)

    sku_idx = np.repeat(np.arange(n_materials), n_wh)
    wh_idx = np.tile(np.arange(n_wh), n_materials)
    series_base = base_mean_material[sku_idx] * shares[sku_idx, wh_idx]
    series_shape = shape[sku_idx]
    series_p = p_occ[sku_idx]
    mean_nonzero = series_base / series_p

    n_series = n_materials * n_wh
    factor = _monthly_factors(rng, months, n_series, cfg)
    factor *= _weekday_factors(dow, cfg)[:, None]
    factor *= _event_multiplier(rng, n_days, n_series, cfg)

    mu = mean_nonzero[None, :] * factor
    occurred = rng.random((n_days, n_series)) < series_p[None, :]
    sizes = rng.gamma(series_shape[None, :], scale=mu / np.maximum(series_shape[None, :], 1e-9))
    demand = np.rint(np.where(occurred, sizes, 0.0)).astype(np.int64)
    np.clip(demand, 0, None, out=demand)
    target_per_series = target[sku_idx]
    return demand, sku_idx, wh_idx, dates, target_per_series


def generate_lead_times(cfg: GeneratorConfig, catalog: Catalog, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """对数正态提前期样本（每个 SKU×仓库每年 lt_samples_per_year 次）。"""
    rng = np.random.default_rng(cfg.seed * 7919 + 5)
    n_samples = max(cfg.years * cfg.lt_samples_per_year, 1)
    order_positions = np.unique(np.linspace(0, len(dates) - 1, n_samples).astype(int))
    rows = []
    for material in catalog.materials.itertuples():
        mean_lt = float(material.lead_time_mean) if float(material.lead_time_mean) > 0 else cfg.lt_mean_min
        log_mu = np.log(mean_lt) - 0.5 * cfg.lt_log_sigma**2
        samples = rng.lognormal(log_mu, cfg.lt_log_sigma, size=order_positions.size)
        for warehouse in catalog.warehouses.itertuples():
            for pos, lead in zip(order_positions, samples):
                rows.append(
                    {
                        "material_id": int(material.material_id),
                        "warehouse_id": int(warehouse.warehouse_id),
                        "order_date": dates[pos].date().isoformat(),
                        "lead_time_days": round(float(lead), 3),
                    }
                )
    return pd.DataFrame(rows, columns=["material_id", "warehouse_id", "order_date", "lead_time_days"])
