"""动态安全库存 / 再订货点（SS/ROP）与日度库存仿真（M5）。

公式（方案 §7.1，服务水平口径见 erp_ml.service_level）：

- 提前期内需求：`D_LT = D̂_day · LT`
- 安全库存：`SS = z · sqrt(LT · σD² + D̂² · σLT²)`
- 再订货点：`ROP = D_LT + SS = D̂_day · LT + SS`
- 目标库存位置（最小-最大法）：`S = ROP + D̂_day · review_period`
- EOQ 作为参考量：`Q* = sqrt(2 · D_year · S_order / H)`（间歇件 EOQ 常远大于需求，故仅报告不用作下单量）
- 触发：`库存持有量 + 在途 − 欠交 <= ROP` 时，下单把库存位置抬到 `S`（数量按起订量与包装倍数取整）

仿真约定：
- 日度离散事件、**允许缺货回补（backorder）**：未满足需求记欠交，下一批到货先补欠交。
- Fill Rate = 1 − 累计欠交量 / 总需求；CSL = 评估窗口内"订货周期无缺货"的比例。
- 订单提前期从对数正态分布抽样；A/B 两个策略使用**同一随机流**（按订单序号取同一池），
  需求实现也完全相同，保证配对可比。
- 评估窗口丢弃前 `warmup_days` 天；**CSL 只统计评估窗口内开启的订货周期**，
  避免预热期缺货污染。

本模块纯计算，不触碰业务库、不写任何业务表（AGENTS 不变量 4）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .config import GeneratorConfig
from .service_level import SERVICE_LEVEL_TYPE, ServiceLevelSpec

EPS = 1e-9


@dataclass(frozen=True)
class SimulationConfig:
    """库存仿真与成本参数（全部进入 config.json）。"""

    start_day: int = 180
    warmup_days: int = 30
    review_period_days: int = 7
    sigma_window: int = 56
    service_level_type: str = SERVICE_LEVEL_TYPE
    service_level: float = 0.95
    order_cost: float = 100.0
    holding_cost_rate: float = 0.20
    stockout_penalty_rate: float = 0.5
    min_order_qty: float = 1.0
    pack_size: float = 1.0

    def service_spec(self) -> ServiceLevelSpec:
        return ServiceLevelSpec(self.service_level_type, self.service_level)

    def to_dict(self) -> dict:
        data = dict(self.__dict__)
        data.update(self.service_spec().to_dict())
        return data


@dataclass(frozen=True)
class PolicyParams:
    """某一时点的补货策略参数（可解释来源之一）。"""

    ss: float
    rop: float
    order_up_to: float
    eoq: float
    lead_time_mean: float
    sigma_d: float
    forecast_daily: float
    z_value: float
    service_level_type: str = SERVICE_LEVEL_TYPE
    service_level: float = 0.95

    def to_dict(self) -> dict:
        return {
            "safety_stock": round(self.ss, 6),
            "rop": round(self.rop, 6),
            "order_up_to": round(self.order_up_to, 6),
            "eoq": round(self.eoq, 6),
            "lead_time_mean": round(self.lead_time_mean, 6),
            "sigma_d": round(self.sigma_d, 6),
            "forecast_daily": round(self.forecast_daily, 6),
            "z_value": round(self.z_value, 6),
            "service_level_type": self.service_level_type,
            "service_level": float(self.service_level),
        }


def lead_time_std(lead_time_mean: float, log_sigma: float) -> float:
    """对数正态提前期的标准差：σLT = LT · sqrt(exp(σ_log²) − 1)。"""
    mean = max(float(lead_time_mean), EPS)
    return float(mean * math.sqrt(math.exp(log_sigma**2) - 1.0))


def safety_stock(
    forecast_daily: float,
    sigma_d: float,
    lead_time_mean: float,
    sigma_lt: float,
    z_value: float,
) -> float:
    """SS = z · sqrt(LT·σD² + D̂²·σLT²)。"""
    variance = lead_time_mean * max(sigma_d, 0.0) ** 2 + max(forecast_daily, 0.0) ** 2 * max(sigma_lt, 0.0) ** 2
    return float(max(z_value, 0.0) * math.sqrt(max(variance, 0.0)))


def reorder_point(forecast_daily: float, lead_time_mean: float, ss: float) -> float:
    """ROP = D̂ · LT + SS。"""
    return float(max(forecast_daily, 0.0) * max(lead_time_mean, 0.0) + max(ss, 0.0))


def eoq(annual_demand: float, order_cost: float, unit_holding_cost: float) -> float:
    """经济订货批量 Q* = sqrt(2·D_year·S/H)；H<=0 时退化为半年需求。"""
    demand = max(float(annual_demand), 0.0)
    if demand <= 0.0:
        return 0.0
    if unit_holding_cost <= EPS or order_cost <= 0.0:
        return float(demand / 2.0)
    return float(math.sqrt(2.0 * demand * order_cost / unit_holding_cost))


def round_order_qty(quantity: float, min_order_qty: float = 1.0, pack_size: float = 1.0) -> float:
    """按起订量下限 + 包装倍数向上取整。"""
    pack = max(float(pack_size), EPS)
    q = max(float(quantity), max(float(min_order_qty), 0.0))
    return float(math.ceil(q / pack - 1e-9) * pack)


def make_policy(
    forecast_daily: float,
    sigma_d: float,
    lead_time_mean: float,
    sigma_lt: float,
    service: ServiceLevelSpec,
    unit_price: float,
    cfg: SimulationConfig,
) -> PolicyParams:
    ss = safety_stock(forecast_daily, sigma_d, lead_time_mean, sigma_lt, service.z_value)
    rop = reorder_point(forecast_daily, lead_time_mean, ss)
    order_up_to = rop + max(forecast_daily, 0.0) * max(cfg.review_period_days, 0)
    annual_demand = max(forecast_daily, 0.0) * 365.0
    unit_holding = max(float(unit_price), 0.0) * max(cfg.holding_cost_rate, 0.0)
    eoq_value = eoq(annual_demand, cfg.order_cost, unit_holding)
    return PolicyParams(
        ss=ss,
        rop=rop,
        order_up_to=order_up_to,
        eoq=eoq_value,
        lead_time_mean=lead_time_mean,
        sigma_d=sigma_d,
        forecast_daily=forecast_daily,
        z_value=service.z_value,
        service_level_type=service.level_type,
        service_level=service.level,
    )


def fixed_policy(
    history_demand: np.ndarray,
    lead_time_mean: float,
    log_sigma_lt: float,
    unit_price: float,
    cfg: SimulationConfig,
) -> PolicyParams:
    """策略 A（对照）：用历史窗口均值/标准差一次性设定的固定 SS/ROP/S。"""
    history = np.asarray(history_demand, dtype=float)
    mean_daily = float(history.mean()) if history.size else 0.0
    sigma_d = float(history.std(ddof=0)) if history.size else 0.0
    sigma_lt = lead_time_std(lead_time_mean, log_sigma_lt)
    return make_policy(mean_daily, sigma_d, lead_time_mean, sigma_lt, cfg.service_spec(), unit_price, cfg)


def dynamic_policies(
    forecast_matrix: np.ndarray,
    sigma_d_at_origin: np.ndarray,
    lead_time_mean: float,
    log_sigma_lt: float,
    unit_price: float,
    cfg: SimulationConfig,
) -> list[PolicyParams]:
    """策略 B（本文）：每个 origin 用分层预测日均值与滚动波动重算 SS/ROP/S。

    forecast_matrix 形状 (n_origins, horizon)，取整段预测均值作为 D̂_day。
    """
    forecast = np.asarray(forecast_matrix, dtype=float)
    sigmas = np.asarray(sigma_d_at_origin, dtype=float)
    sigma_lt = lead_time_std(lead_time_mean, log_sigma_lt)
    service = cfg.service_spec()
    policies: list[PolicyParams] = []
    for i in range(forecast.shape[0]):
        daily = float(np.nanmean(forecast[i])) if forecast.shape[1] else 0.0
        if not np.isfinite(daily):
            daily = 0.0
        sigma = float(sigmas[i]) if i < sigmas.size and np.isfinite(sigmas[i]) else 0.0
        policies.append(make_policy(daily, sigma, lead_time_mean, sigma_lt, service, unit_price, cfg))
    return policies


def expand_policy_path(
    policies: list[PolicyParams],
    origins: list[int],
    n_days: int,
) -> tuple[np.ndarray, np.ndarray]:
    """把逐 origin 策略展开成逐日 (rop, order_up_to) 路径（origin 间沿用上一期）。"""
    rop_path = np.full(n_days, policies[0].rop if policies else 0.0, dtype=float)
    s_path = np.full(n_days, policies[0].order_up_to if policies else 0.0, dtype=float)
    for i, origin in enumerate(origins):
        start = max(origin, 0)
        end = origins[i + 1] if i + 1 < len(origins) else n_days
        end = min(max(end, start), n_days)
        rop_path[start:end] = policies[i].rop
        s_path[start:end] = policies[i].order_up_to
    return rop_path, s_path


def lead_time_pool(
    lead_time_mean: float,
    log_sigma_lt: float,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """预抽一批对数正态提前期，A/B 按订单序号共用（保证配对公平）。"""
    mean = max(float(lead_time_mean), EPS)
    log_mu = math.log(mean) - 0.5 * log_sigma_lt**2
    return rng.lognormal(log_mu, log_sigma_lt, size=int(max(size, 1)))


def rolling_sigma_path(demand: np.ndarray, origins: list[int], window: int) -> np.ndarray:
    """每个 origin 用其之前 window 天（不含 origin）的需求标准差，严格因果。"""
    values = np.asarray(demand, dtype=float)
    out = np.zeros(len(origins), dtype=float)
    for i, origin in enumerate(origins):
        start = max(0, origin - int(window))
        segment = values[start:origin]
        out[i] = float(segment.std(ddof=0)) if segment.size else 0.0
    return out


@dataclass
class SimResult:
    metrics: dict = field(default_factory=dict)
    on_hand: np.ndarray = field(default_factory=lambda: np.zeros(0))
    rop: np.ndarray = field(default_factory=lambda: np.zeros(0))
    days: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    final_on_hand: float = 0.0
    final_on_order: float = 0.0
    final_backorder: float = 0.0
    final_rop: float = 0.0
    orders_placed: int = 0


def simulate_series(
    demand: np.ndarray,
    rop_path: np.ndarray,
    s_path: np.ndarray,
    lead_times: np.ndarray,
    start_day: int,
    initial_on_hand: float,
    unit_price: float,
    cfg: SimulationConfig,
) -> SimResult:
    """单条 SKU×仓库 序列的日度库存仿真（(s,S) 最小-最大 + backorder）。"""
    values = np.asarray(demand, dtype=float)
    rops = np.asarray(rop_path, dtype=float)
    targets = np.asarray(s_path, dtype=float)
    n_days = values.size
    start = int(max(start_day, 0))
    eval_start = min(start + int(max(cfg.warmup_days, 0)), n_days)

    on_hand = float(initial_on_hand)
    backorder = 0.0
    open_orders: list[tuple[int, float]] = []
    order_index = 0
    orders_placed = 0
    orders_placed_eval = 0

    inventory_area = 0.0
    eval_days = 0
    eval_demand = 0.0
    backordered_qty = 0.0
    stockout_days = 0
    total_cycles = 0
    failed_cycles = 0
    cycle_open = False
    cycle_failed = False

    trace_on_hand: list[float] = []
    trace_rop: list[float] = []
    trace_days: list[int] = []

    for t in range(start, n_days):
        # 1) 到货（到达日 <= t）
        if open_orders:
            remaining: list[tuple[int, float]] = []
            for arrival, qty in open_orders:
                if arrival <= t:
                    on_hand += qty
                else:
                    remaining.append((arrival, qty))
            open_orders = remaining
        # 2) 先补欠交
        if backorder > 0.0 and on_hand > 0.0:
            filled = min(on_hand, backorder)
            on_hand -= filled
            backorder -= filled
        # 3) 复核库存位置并按 (s,S) 下单
        on_order = sum(qty for _, qty in open_orders)
        position = on_hand + on_order - backorder
        rop_t = rops[t] if t < rops.size else 0.0
        target_t = targets[t] if t < targets.size else 0.0
        in_eval = t >= eval_start
        if position <= rop_t and target_t > position + EPS:
            qty = round_order_qty(target_t - position, cfg.min_order_qty, cfg.pack_size)
            if qty > 0.0:
                if in_eval:
                    if cycle_open:
                        total_cycles += 1
                        if cycle_failed:
                            failed_cycles += 1
                    cycle_open = True
                    cycle_failed = False
                else:
                    cycle_open = False
                    cycle_failed = False
                lead = float(lead_times[order_index % lead_times.size]) if lead_times.size else 1.0
                order_index += 1
                arrival = t + max(1, int(round(lead)))
                open_orders.append((arrival, qty))
                orders_placed += 1
                if in_eval:
                    orders_placed_eval += 1
        # 4) 满足当日需求（不足记欠交）
        d = float(values[t])
        if d > 0.0:
            if on_hand >= d:
                on_hand -= d
            else:
                unmet = d - on_hand
                on_hand = 0.0
                backorder += unmet
                if in_eval:
                    backordered_qty += unmet
                    stockout_days += 1
                    if cycle_open:
                        cycle_failed = True
        if in_eval:
            inventory_area += on_hand
            eval_days += 1
            eval_demand += d
            trace_on_hand.append(on_hand)
            trace_rop.append(rop_t)
            trace_days.append(t)

    if cycle_open:
        total_cycles += 1
        if cycle_failed:
            failed_cycles += 1

    avg_inventory = inventory_area / eval_days if eval_days else 0.0
    avg_daily_demand = eval_demand / eval_days if eval_days else 0.0
    fill_rate = 1.0 - (backordered_qty / eval_demand) if eval_demand > 0.0 else 1.0
    csl = 1.0 - (failed_cycles / total_cycles) if total_cycles else 1.0
    holding_cost = inventory_area * max(unit_price, 0.0) * max(cfg.holding_cost_rate, 0.0) / 365.0
    ordering_cost = orders_placed_eval * max(cfg.order_cost, 0.0)
    shortage_cost = backordered_qty * max(unit_price, 0.0) * max(cfg.stockout_penalty_rate, 0.0)
    metrics = {
        "eval_days": eval_days,
        "demand_total": round(eval_demand, 4),
        "stockout_days": stockout_days,
        "stockout_rate": round(stockout_days / eval_days, 6) if eval_days else 0.0,
        "fill_rate": round(fill_rate, 6),
        "cycle_service_level": round(csl, 6),
        "backorder_qty": round(backordered_qty, 4),
        "avg_inventory": round(avg_inventory, 6),
        "turnover_days": round(avg_inventory / avg_daily_demand, 4) if avg_daily_demand > 0.0 else 0.0,
        "holding_cost": round(holding_cost, 4),
        "orders_placed": orders_placed_eval,
        "ordering_cost": round(ordering_cost, 4),
        "shortage_cost": round(shortage_cost, 4),
        "total_cost": round(holding_cost + ordering_cost + shortage_cost, 4),
    }
    return SimResult(
        metrics=metrics,
        on_hand=np.asarray(trace_on_hand, dtype=float),
        rop=np.asarray(trace_rop, dtype=float),
        days=np.asarray(trace_days, dtype=int),
        final_on_hand=float(on_hand),
        final_on_order=float(sum(qty for _, qty in open_orders)),
        final_backorder=float(backorder),
        final_rop=float(rops[n_days - 1]) if n_days and n_days - 1 < rops.size else 0.0,
        orders_placed=int(orders_placed),
    )


def lead_time_mean_for_material(materials, material_id: int, fallback: float) -> float:
    row = materials.loc[materials["material_id"] == material_id, "lead_time_mean"]
    if row.empty:
        return float(fallback)
    value = float(row.iloc[0])
    return value if value > 0.0 else float(fallback)


def generator_lead_time_fallback(cfg: GeneratorConfig) -> float:
    return float(0.5 * (cfg.lt_mean_min + cfg.lt_mean_max))
