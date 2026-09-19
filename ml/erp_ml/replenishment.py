"""可解释补货建议与策略参数（M5，对应 db-schema §12.5/§12.6）。

本模块只**生成结果表**（落 ml/results/），字段与未来业务库
`replenishment_policy` / `replenishment_suggestion` 对齐，便于后续后端直接落库；
ML 侧不写任何业务表（AGENTS 不变量 4）。

可解释性（AGENTS 不变量 5）：每条建议给出
当前结存 / 锁定 / 在途 / 欠交 / 可用、ROP、目标库存位置 S、SS、EOQ、预测日均值、
提前期与波动、参数来源（策略、模型、象限、服务水平口径与 z 值）以及自然语言 reason。
"""

from __future__ import annotations

import pandas as pd

from .inventory import PolicyParams, round_order_qty

POLICY_COLUMNS = [
    "seed",
    "series_key",
    "material_id",
    "warehouse_id",
    "demand_class",
    "policy_code",
    "strategy",
    "service_level_type",
    "service_level",
    "z_value",
    "review_period_days",
    "order_cost",
    "holding_cost_rate",
    "min_order_qty",
    "pack_size",
    "lead_time_mean",
    "sigma_d",
    "forecast_daily",
    "safety_stock",
    "rop",
    "order_up_to",
    "eoq",
]

SUGGESTION_COLUMNS = [
    "suggestion_no",
    "seed",
    "series_key",
    "material_id",
    "warehouse_id",
    "demand_class",
    "policy_id",
    "forecast_run_id",
    "trigger_type",
    "status",
    "current_qty",
    "locked_qty",
    "in_transit_qty",
    "backorder_qty",
    "available_qty",
    "daily_demand_hat",
    "lead_time_mean",
    "sigma_d",
    "sigma_lt",
    "safety_stock",
    "rop",
    "order_up_to",
    "eoq",
    "suggested_qty",
    "final_qty",
    "service_level_type",
    "service_level",
    "model_code",
    "parameter_source",
    "reason",
]


def policy_code(seed: int, series_key: str, strategy: str) -> str:
    return f"POL-{strategy}-S{seed}-{series_key}".replace(":", "-")


def policy_row(
    seed: int,
    meta: dict,
    strategy: str,
    policy: PolicyParams,
    review_period_days: int,
    order_cost: float,
    holding_cost_rate: float,
    min_order_qty: float,
    pack_size: float,
) -> dict:
    return {
        "seed": seed,
        "series_key": meta["series_key"],
        "material_id": meta["material_id"],
        "warehouse_id": meta["warehouse_id"],
        "demand_class": meta["demand_class"],
        "policy_code": policy_code(seed, meta["series_key"], strategy),
        "strategy": strategy,
        "service_level_type": policy.service_level_type,
        "service_level": policy.service_level,
        "z_value": round(policy.z_value, 6),
        "review_period_days": review_period_days,
        "order_cost": order_cost,
        "holding_cost_rate": holding_cost_rate,
        "min_order_qty": min_order_qty,
        "pack_size": pack_size,
        "lead_time_mean": round(policy.lead_time_mean, 6),
        "sigma_d": round(policy.sigma_d, 6),
        "forecast_daily": round(policy.forecast_daily, 6),
        "safety_stock": round(policy.ss, 6),
        "rop": round(policy.rop, 6),
        "order_up_to": round(policy.order_up_to, 6),
        "eoq": round(policy.eoq, 6),
    }


def build_suggestion(
    suggestion_no: str,
    seed: int,
    meta: dict,
    model_code: str,
    policy: PolicyParams,
    sigma_lt: float,
    current_qty: float,
    locked_qty: float,
    in_transit_qty: float,
    backorder_qty: float,
    min_order_qty: float = 1.0,
    pack_size: float = 1.0,
) -> dict:
    available = current_qty + in_transit_qty - locked_qty - backorder_qty
    below = available <= policy.rop
    raw_qty = max(policy.order_up_to - available, 0.0)
    suggested = round_order_qty(raw_qty, min_order_qty, pack_size) if below and raw_qty > 0.0 else 0.0
    trigger_type = "BELOW_ROP" if below and suggested > 0.0 else "NONE"
    parameter_source = (
        f"policy=FORECAST;model={model_code};demand_class={meta['demand_class']};"
        f"service_level_type={policy.service_level_type};service_level={policy.service_level:.2f};"
        f"z={policy.z_value:.4f};lead_time_mean={policy.lead_time_mean:.2f};"
        f"sigma_lt={sigma_lt:.3f};sigma_d={policy.sigma_d:.3f}"
    )
    reason = (
        f"预测驱动：D̂={policy.forecast_daily:.3f}/日，LT={policy.lead_time_mean:.2f} 天，"
        f"σD={policy.sigma_d:.3f}，σLT={sigma_lt:.3f}；"
        f"SS=z·√(LT·σD²+D̂²·σLT²)={policy.ss:.3f}，ROP=D̂·LT+SS={policy.rop:.3f}，"
        f"S=ROP+D̂·复核周期={policy.order_up_to:.3f}；"
        f"可用=结存 {current_qty:.3f}+在途 {in_transit_qty:.3f}−锁定 {locked_qty:.3f}−欠交 {backorder_qty:.3f}"
        f"={available:.3f}"
    )
    if suggested > 0.0:
        reason += f" ≤ ROP={policy.rop:.3f} → 建议订货把库存位置抬到 S，数量={suggested:.3f}（已按起订量/包装取整）"
    else:
        reason += f" > ROP={policy.rop:.3f}，库存充足，无需补货"
    return {
        "suggestion_no": suggestion_no,
        "seed": seed,
        "series_key": meta["series_key"],
        "material_id": meta["material_id"],
        "warehouse_id": meta["warehouse_id"],
        "demand_class": meta["demand_class"],
        "policy_id": policy_code(seed, meta["series_key"], "FORECAST"),
        "forecast_run_id": None,
        "trigger_type": trigger_type,
        "status": "OPEN" if suggested > 0.0 else "CLOSED",
        "current_qty": round(current_qty, 6),
        "locked_qty": round(locked_qty, 6),
        "in_transit_qty": round(in_transit_qty, 6),
        "backorder_qty": round(backorder_qty, 6),
        "available_qty": round(available, 6),
        "daily_demand_hat": round(policy.forecast_daily, 6),
        "lead_time_mean": round(policy.lead_time_mean, 6),
        "sigma_d": round(policy.sigma_d, 6),
        "sigma_lt": round(sigma_lt, 6),
        "safety_stock": round(policy.ss, 6),
        "rop": round(policy.rop, 6),
        "order_up_to": round(policy.order_up_to, 6),
        "eoq": round(policy.eoq, 6),
        "suggested_qty": round(suggested, 6),
        "final_qty": None,
        "service_level_type": policy.service_level_type,
        "service_level": policy.service_level,
        "model_code": model_code,
        "parameter_source": parameter_source,
        "reason": reason,
    }


def rows_to_frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]
