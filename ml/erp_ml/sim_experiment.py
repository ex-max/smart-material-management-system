"""M5 库存决策实验：动态 SS/ROP + 可解释补货建议 + A/B 库存仿真。

用法（在 ml/ 下）：
    .venv/bin/python -m erp_ml.sim_experiment --seeds 1 2 3 --tag m5-simulation

协议（forecast-experiment 技能）：
- 需求生成 seed 1..N 重复；策略 A（固定 SS/ROP）与策略 B（预测驱动动态 SS/ROP）
  在**同一需求实现、同一提前期随机流**下配对仿真。
- 指标按 ADI/CV² 象限分层报告；对每个 (seed, SKU×仓库) 的配对差做
  Wilcoxon 符号秩检验，报 p 值。结论只在显著时写"优于"。
- 服务水平口径固定 CSL（erp_ml.service_level 定稿）。结果落 ml/results/，不进 git。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .artifacts import package_versions, sha256_array
from .baseline import stratified_indices
from .config import BacktestConfig, GeneratorConfig
from .dataset import build_dataset
from .features import FeatureSpec
from .forecast_layer import LayeredForecast, forecast_matrix_for_series, rolling_layered_forecast
from .gbm import DEFAULT_LGB_PARAMS
from .inventory import (
    SimulationConfig,
    dynamic_policies,
    expand_policy_path,
    fixed_policy,
    lead_time_mean_for_material,
    lead_time_pool,
    lead_time_std,
    rolling_sigma_path,
    simulate_series,
)
from .models import model_mapping, recommend_model
from .replenishment import (
    POLICY_COLUMNS,
    SUGGESTION_COLUMNS,
    build_suggestion,
    policy_row,
    rows_to_frame,
)
from .service_level import SERVICE_LEVEL_TYPE

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
os.environ.setdefault("MPLCONFIGDIR", str(RESULTS_DIR / ".mplconfig"))

AB_METRICS = (
    "stockout_rate",
    "stockout_days",
    "fill_rate",
    "cycle_service_level",
    "avg_inventory",
    "turnover_days",
    "holding_cost",
    "orders_placed",
    "ordering_cost",
    "shortage_cost",
    "total_cost",
)
LOWER_IS_BETTER = {
    "stockout_rate",
    "stockout_days",
    "avg_inventory",
    "turnover_days",
    "holding_cost",
    "orders_placed",
    "ordering_cost",
    "shortage_cost",
    "total_cost",
}
STRATEGY_FIXED = "A_FIXED"
STRATEGY_FORECAST = "B_FORECAST"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M5 动态 SS/ROP + 补货建议 + A/B 库存仿真")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 31)))
    parser.add_argument("--skus", type=int, default=800)
    parser.add_argument("--warehouses", type=int, default=1)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--start", type=str, default="2023-01-01")
    parser.add_argument("--max-series", type=int, default=60, help="每 seed 分层抽样序列数")
    parser.add_argument("--horizon", type=int, default=7, help="预测与复核 horizon（天）")
    parser.add_argument("--initial-train", type=int, default=180)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--sigma-window", type=int, default=56)
    parser.add_argument("--service-level", type=float, default=0.95)
    parser.add_argument("--service-level-type", type=str, default=SERVICE_LEVEL_TYPE, choices=[SERVICE_LEVEL_TYPE])
    parser.add_argument("--order-cost", type=float, default=100.0)
    parser.add_argument("--holding-cost-rate", type=float, default=0.20)
    parser.add_argument("--stockout-penalty-rate", type=float, default=0.5)
    parser.add_argument("--min-order-qty", type=float, default=1.0)
    parser.add_argument("--pack-size", type=float, default=1.0)
    parser.add_argument("--tradeoff-levels", type=float, nargs="+", default=[0.80, 0.85, 0.90, 0.95, 0.98, 0.99])
    parser.add_argument("--num-boost-round", type=int, default=300)
    parser.add_argument("--max-suggestions", type=int, default=2000, help="建议表总行数上限（跨 seed）")
    parser.add_argument("--tag", type=str, default="m5-simulation")
    parser.add_argument("--out", type=str, default=str(RESULTS_DIR))
    parser.add_argument("--no-figures", action="store_true")
    return parser


def _git_commit() -> str:
    repo = Path(__file__).resolve().parents[2]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def wilcoxon_p_value(differences: np.ndarray) -> float:
    """Wilcoxon 符号秩检验 p 值；全零/无样本时返回 1.0。"""
    from scipy.stats import wilcoxon

    diffs = np.asarray(differences, dtype=float)
    diffs = diffs[np.isfinite(diffs)]
    if diffs.size == 0 or np.allclose(diffs, 0.0):
        return 1.0
    try:
        return float(wilcoxon(diffs, zero_method="wilcox", alternative="two-sided").pvalue)
    except ValueError:
        return 1.0


def ab_summary(metrics: pd.DataFrame, segments: list[str]) -> pd.DataFrame:
    """分层 A/B 汇总：多种子均值±标准差 + 配对 Wilcoxon p 值。"""
    rows = []
    for segment in segments:
        subset = metrics if segment == "ALL" else metrics[metrics["demand_class"] == segment]
        if subset.empty:
            continue
        per_seed = subset.groupby(["seed", "strategy"])[list(AB_METRICS)].mean()
        pivot = subset.pivot_table(index=["seed", "series_key"], columns="strategy", values=list(AB_METRICS))
        for metric in AB_METRICS:
            if metric not in subset.columns:
                continue
            a_col = pivot[(metric, STRATEGY_FIXED)] if (metric, STRATEGY_FIXED) in pivot.columns else None
            b_col = pivot[(metric, STRATEGY_FORECAST)] if (metric, STRATEGY_FORECAST) in pivot.columns else None
            diffs = (b_col - a_col).dropna().to_numpy() if a_col is not None and b_col is not None else np.array([])
            a_values = per_seed[metric].xs(STRATEGY_FIXED, level="strategy").to_numpy() if STRATEGY_FIXED in per_seed.index.get_level_values("strategy") else np.array([])
            b_values = per_seed[metric].xs(STRATEGY_FORECAST, level="strategy").to_numpy() if STRATEGY_FORECAST in per_seed.index.get_level_values("strategy") else np.array([])
            a_mean = float(np.nanmean(a_values)) if a_values.size else float("nan")
            b_mean = float(np.nanmean(b_values)) if b_values.size else float("nan")
            direction = "lower" if metric in LOWER_IS_BETTER else "higher"
            improvement = (a_mean - b_mean) if direction == "lower" else (b_mean - a_mean)
            p_value = wilcoxon_p_value(diffs)
            rows.append(
                {
                    "segment": segment,
                    "metric": metric,
                    "direction": direction,
                    "A_mean": round(a_mean, 6),
                    "A_std": round(float(np.nanstd(a_values, ddof=1)) if a_values.size > 1 else 0.0, 6),
                    "B_mean": round(b_mean, 6),
                    "B_std": round(float(np.nanstd(b_values, ddof=1)) if b_values.size > 1 else 0.0, 6),
                    "improvement_B_minus_A": round(improvement, 6),
                    "median_diff_B_minus_A": round(float(np.nanmedian(diffs)) if diffs.size else 0.0, 6),
                    "n_pairs": int(diffs.size),
                    "n_seeds": int(subset["seed"].nunique()),
                    "p_value": round(p_value, 6),
                    "significant_0.05": bool(p_value < 0.05),
                }
            )
    return pd.DataFrame(rows)


def _run_seed(
    seed: int,
    base_cfg: GeneratorConfig,
    sim_cfg: SimulationConfig,
    backtest_cfg: BacktestConfig,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, list[dict], list[dict], LayeredForecast, pd.DataFrame, dict, str]:
    cfg = GeneratorConfig.from_dict({**base_cfg.to_dict(), "seed": seed})
    ds = build_dataset(cfg, catalog_source="synthetic")
    selected = stratified_indices(ds.meta, backtest_cfg.max_series, seed)
    meta_rows = ds.meta.loc[selected].reset_index(drop=True)
    if len(selected):
        values = np.column_stack([ds.demand[:, int(index)] for index in selected])
    else:
        values = np.zeros((cfg.n_days, 0))
    demand_classes = [str(c) for c in meta_rows["demand_class"].tolist()]
    prices = ds.catalog.materials.set_index("material_id")["unit_price"].to_dict()
    lt_fallback = float(0.5 * (cfg.lt_mean_min + cfg.lt_mean_max))

    layered = rolling_layered_forecast(
        values,
        ds.dates,
        demand_classes,
        backtest_cfg,
        spec=FeatureSpec(),
        params=dict(DEFAULT_LGB_PARAMS),
        num_boost_round=args.num_boost_round,
    )
    if not layered.origins:
        raise RuntimeError(f"seed={seed} 训练窗不足，无法产生 rolling-origin 预测")

    metric_rows: list[dict] = []
    policy_rows: list[dict] = []
    suggestion_rows: list[dict] = []
    bundle: dict = {"series": [], "seed": seed}
    suggestion_seq = 0

    for j, meta in enumerate(meta_rows.to_dict(orient="records")):
        material_id = int(meta["material_id"])
        unit_price = float(prices.get(material_id, 1.0))
        lead_time_mean = lead_time_mean_for_material(ds.catalog.materials, material_id, lt_fallback)
        sigma_lt = lead_time_std(lead_time_mean, cfg.lt_log_sigma)
        rng = np.random.default_rng(seed * 1_000_003 + material_id * 31 + int(meta["warehouse_id"]))
        lead_times = lead_time_pool(lead_time_mean, cfg.lt_log_sigma, values.shape[0], rng)

        fixed = fixed_policy(
            values[: backtest_cfg.initial_train_days, j], lead_time_mean, cfg.lt_log_sigma, unit_price, sim_cfg
        )
        forecast_series = forecast_matrix_for_series(layered, j)
        sigma_path = rolling_sigma_path(values[:, j], layered.origins, sim_cfg.sigma_window)
        dynamic_list = dynamic_policies(forecast_series, sigma_path, lead_time_mean, cfg.lt_log_sigma, unit_price, sim_cfg)

        rop_a, s_a = expand_policy_path([fixed], [backtest_cfg.initial_train_days], values.shape[0])
        rop_b, s_b = expand_policy_path(dynamic_list, layered.origins, values.shape[0])
        initial_on_hand = float(math.ceil(max(fixed.rop, dynamic_list[0].rop if dynamic_list else fixed.rop)))

        result_a = simulate_series(
            values[:, j], rop_a, s_a, lead_times, backtest_cfg.initial_train_days, initial_on_hand, unit_price, sim_cfg
        )
        result_b = simulate_series(
            values[:, j], rop_b, s_b, lead_times, backtest_cfg.initial_train_days, initial_on_hand, unit_price, sim_cfg
        )

        base = {
            "seed": seed,
            "series_key": meta["series_key"],
            "material_id": material_id,
            "warehouse_id": int(meta["warehouse_id"]),
            "demand_class": meta["demand_class"],
            "abc_class": meta["abc_class"],
        }
        metric_rows.append({**base, "strategy": STRATEGY_FIXED, **result_a.metrics})
        metric_rows.append({**base, "strategy": STRATEGY_FORECAST, **result_b.metrics})
        policy_rows.append(
            policy_row(seed, meta, "FIXED", fixed, sim_cfg.review_period_days, sim_cfg.order_cost,
                       sim_cfg.holding_cost_rate, sim_cfg.min_order_qty, sim_cfg.pack_size)
        )
        policy_rows.append(
            policy_row(seed, meta, "FORECAST", dynamic_list[-1], sim_cfg.review_period_days, sim_cfg.order_cost,
                       sim_cfg.holding_cost_rate, sim_cfg.min_order_qty, sim_cfg.pack_size)
        )

        if len(suggestion_rows) < args.max_suggestions:
            suggestion_seq += 1
            day = ds.dates[-1].date().isoformat()
            suggestion_rows.append(
                build_suggestion(
                    suggestion_no=f"RS-{day}-S{seed}-{suggestion_seq:04d}",
                    seed=seed,
                    meta=meta,
                    model_code=recommend_model(str(meta["demand_class"])),
                    policy=dynamic_list[-1],
                    sigma_lt=sigma_lt,
                    current_qty=result_b.final_on_hand,
                    locked_qty=0.0,
                    in_transit_qty=result_b.final_on_order,
                    backorder_qty=result_b.final_backorder,
                    min_order_qty=sim_cfg.min_order_qty,
                    pack_size=sim_cfg.pack_size,
                )
            )

        bundle["series"].append(
            {
                "meta": meta,
                "unit_price": unit_price,
                "lead_time_mean": lead_time_mean,
                "lead_times": lead_times,
                "values": values[:, j],
                "origins": list(layered.origins),
                "forecast_series": forecast_series,
                "sigma_path": sigma_path,
                "initial_on_hand": initial_on_hand,
                "result_a": result_a,
                "result_b": result_b,
            }
        )

    metrics_df = pd.DataFrame(metric_rows)
    meta_out = meta_rows.copy()
    meta_out.insert(0, "seed", seed)
    return metrics_df, policy_rows, suggestion_rows, layered, meta_out, bundle, sha256_array(ds.demand)


def _cost_service_tradeoff(
    bundle: dict,
    levels: list[float],
    sim_cfg: SimulationConfig,
    log_sigma_lt: float,
) -> pd.DataFrame:
    """固定需求/提前期实现，扫描目标 CSL 得到策略 B 的成本-服务权衡曲线。"""
    series_items = bundle.get("series", [])
    if not series_items:
        return pd.DataFrame(columns=["service_level", "fill_rate", "total_cost", "avg_inventory"])
    rows = []
    for level in levels:
        level_cfg = SimulationConfig(**{**sim_cfg.__dict__, "service_level": float(level)})
        fills, totals, holdings, orderings, invs = [], [], [], [], []
        for item in series_items:
            policies = dynamic_policies(
                item["forecast_series"],
                item["sigma_path"],
                item["lead_time_mean"],
                log_sigma_lt,
                item["unit_price"],
                level_cfg,
            )
            rop_path, s_path = expand_policy_path(policies, item["origins"], len(item["values"]))
            # 每个服务水平下用同一策略自身的 ROP 设定初始库存，避免前沿被初始条件扭曲
            initial = float(math.ceil(policies[0].rop)) if policies else item["initial_on_hand"]
            result = simulate_series(
                item["values"], rop_path, s_path, item["lead_times"],
                item["origins"][0], initial, item["unit_price"], level_cfg,
            )
            fills.append(result.metrics["fill_rate"])
            totals.append(result.metrics["total_cost"])
            holdings.append(result.metrics["holding_cost"])
            orderings.append(result.metrics["ordering_cost"])
            invs.append(result.metrics["avg_inventory"])
        rows.append(
            {
                "service_level": float(level),
                "fill_rate": round(float(np.mean(fills)), 6),
                "total_cost": round(float(np.mean(totals)), 6),
                "holding_cost": round(float(np.mean(holdings)), 6),
                "ordering_cost": round(float(np.mean(orderings)), 6),
                "avg_inventory": round(float(np.mean(invs)), 6),
            }
        )
    return pd.DataFrame(rows)


def _write_figures(
    ab_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    first_bundle: dict,
    figures_dir: Path,
    tradeoff: pd.DataFrame | None,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover - 无 matplotlib 时跳过
        return
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figures_dir.mkdir(parents=True, exist_ok=True)

    series_items = first_bundle.get("series", [])
    smooth = next((s for s in series_items if s["meta"]["demand_class"] == "SMOOTH"), None)
    if smooth is not None:
        fig, ax = plt.subplots(figsize=(10, 4))
        days = smooth["result_a"].days
        ax.plot(days, smooth["result_a"].on_hand, label="策略A 固定", color="#C44E52", lw=1.2)
        ax.plot(days, smooth["result_b"].on_hand, label="策略B 预测驱动", color="#4C72B0", lw=1.2)
        ax.plot(days, smooth["result_a"].rop, label="A ROP", color="#C44E52", ls="--", lw=0.9)
        ax.plot(days, smooth["result_b"].rop, label="B ROP", color="#4C72B0", ls="--", lw=0.9)
        ax.set_title(f"库存轨迹 A/B（{smooth['meta']['series_key']}，{smooth['meta']['demand_class']}）")
        ax.set_xlabel("仿真日序号")
        ax.set_ylabel("库存量")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / "inventory_trajectory.png", dpi=300)
        plt.close(fig)

    overall = ab_df[ab_df["segment"] == "ALL"]
    if not overall.empty:
        chosen = ["total_cost", "holding_cost", "shortage_cost", "avg_inventory", "fill_rate", "stockout_rate"]
        subset = overall[overall["metric"].isin(chosen)]
        fig, axes = plt.subplots(2, 3, figsize=(12, 6))
        for ax, metric in zip(axes.ravel(), chosen):
            row = subset[subset["metric"] == metric]
            if row.empty:
                ax.axis("off")
                continue
            ax.bar(
                ["A 固定", "B 预测"],
                [float(row["A_mean"].iloc[0]), float(row["B_mean"].iloc[0])],
                color=["#C44E52", "#4C72B0"],
            )
            ax.set_title(metric)
            ax.tick_params(labelsize=8)
        fig.suptitle("A/B 库存仿真总体指标（多种子均值）")
        fig.tight_layout()
        fig.savefig(figures_dir / "ab_metrics.png", dpi=300)
        plt.close(fig)

    if tradeoff is not None and not tradeoff.empty:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        ax = axes[0]
        ax.plot(tradeoff["fill_rate"], tradeoff["total_cost"], "o-", color="#4C72B0", label="策略B 预测驱动")
        point_a = metrics_df[metrics_df["strategy"] == STRATEGY_FIXED].agg({"fill_rate": "mean", "total_cost": "mean"})
        ax.scatter([point_a["fill_rate"]], [point_a["total_cost"]], color="#C44E52", marker="*", s=160, label="策略A 固定")
        for _, row in tradeoff.iterrows():
            ax.annotate(f"{row['service_level']:.2f}", (row["fill_rate"], row["total_cost"]), fontsize=7)
        ax.set_xlabel("Fill Rate")
        ax.set_ylabel("总成本（持有+订货+缺货）")
        ax.set_title("总成本-服务水平（策略B 扫描 CSL）")
        ax.legend(fontsize=8)
        ax = axes[1]
        ax.plot(tradeoff["fill_rate"], tradeoff["holding_cost"], "s-", color="#55A868", label="持有成本")
        ax.plot(tradeoff["fill_rate"], tradeoff["ordering_cost"], "^-", color="#8172B2", label="订货成本")
        ax.set_xlabel("Fill Rate")
        ax.set_ylabel("成本")
        ax.set_title("总成本构成（本实例订货成本主导）")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / "cost_service_tradeoff.png", dpi=300)
        plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sim_cfg = SimulationConfig(
        start_day=args.initial_train,
        warmup_days=args.warmup,
        review_period_days=args.step,
        sigma_window=args.sigma_window,
        service_level_type=args.service_level_type,
        service_level=args.service_level,
        order_cost=args.order_cost,
        holding_cost_rate=args.holding_cost_rate,
        stockout_penalty_rate=args.stockout_penalty_rate,
        min_order_qty=args.min_order_qty,
        pack_size=args.pack_size,
    )
    backtest_cfg = BacktestConfig(
        horizons=(args.horizon,),
        initial_train_days=args.initial_train,
        step_days=args.step,
        models=(),
        max_series=args.max_series,
        n_jobs=1,
    )
    base_cfg = GeneratorConfig.from_dict(
        {"skus": args.skus, "warehouses": args.warehouses, "years": args.years, "start_date": args.start}
    )

    all_metrics: list[pd.DataFrame] = []
    all_policies: list[dict] = []
    all_suggestions: list[dict] = []
    segments: pd.DataFrame | None = None
    data_hashes: dict[str, str] = {}
    first_bundle: dict = {}
    for seed in args.seeds:
        metrics_df, policy_rows, suggestion_rows, layered, meta_out, bundle, data_hash = _run_seed(
            seed, base_cfg, sim_cfg, backtest_cfg, args
        )
        all_metrics.append(metrics_df)
        all_policies.extend(policy_rows)
        all_suggestions.extend(suggestion_rows)
        if segments is None:
            segments = meta_out
        data_hashes[str(seed)] = data_hash
        if not first_bundle:
            first_bundle = bundle
        print(f"seed={seed}: {metrics_df['series_key'].nunique()} 序列 × 2 策略仿真完成（origins={len(layered.origins)}）")

    all_suggestions = all_suggestions[: args.max_suggestions]
    metrics_all = pd.concat(all_metrics, ignore_index=True)
    segment_names = ["ALL", *sorted(metrics_all["demand_class"].unique())]
    ab_df = ab_summary(metrics_all, segment_names)

    tradeoff = None
    if not args.no_figures and first_bundle:
        tradeoff = _cost_service_tradeoff(first_bundle, args.tradeoff_levels, sim_cfg, base_cfg.lt_log_sigma)

    run_dir = Path(args.out) / "runs" / f"{datetime.now().strftime('%Y%m%d-%H%M')}_{args.tag}"
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_all.to_csv(run_dir / "policy_metrics.csv", index=False)
    ab_df.to_csv(run_dir / "summary.csv", index=False)
    ab_df.to_csv(run_dir / "ab_summary.csv", index=False)
    rows_to_frame(all_policies, POLICY_COLUMNS).to_csv(run_dir / "policies.csv", index=False)
    rows_to_frame(all_suggestions, SUGGESTION_COLUMNS).to_csv(run_dir / "replenishment_suggestions.csv", index=False)
    if tradeoff is not None and not tradeoff.empty:
        tradeoff.to_csv(run_dir / "cost_service_tradeoff.csv", index=False)
    assert segments is not None
    segments.to_csv(run_dir / "segments.csv", index=False)

    spec = sim_cfg.service_spec()
    config = {
        "tag": args.tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ml_version": __version__,
        "service_level_type": spec.level_type,
        "service_level": {"level_type": spec.level_type, "level": spec.level, "z_value": round(spec.z_value, 4)},
        "service_level_decision": {
            "primary": "CSL（周期服务水平）",
            "fill_rate_role": "仅作为仿真输出指标对比讨论，不作目标口径",
            "formula": "SS = z·sqrt(LT·σD² + D̂²·σLT²), ROP = D̂·LT + SS, z = Φ⁻¹(CSL)",
        },
        "generator": {**base_cfg.to_dict(), "seeds": args.seeds},
        "seeds": args.seeds,
        "backtest": backtest_cfg.to_dict(),
        "simulation": sim_cfg.to_dict(),
        "forecast_model_mapping": model_mapping(),
        "lightgbm": {"params": dict(DEFAULT_LGB_PARAMS), "num_boost_round": args.num_boost_round},
        "tradeoff_levels": args.tradeoff_levels,
        "max_suggestions": args.max_suggestions,
        "catalog_source": "synthetic",
        "data_sha256": data_hashes,
        "code_commit": _git_commit(),
        "python": platform.python_version(),
        "packages": package_versions(),
        "suggestion_count": len(all_suggestions),
    }
    (run_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_figures:
        _write_figures(ab_df, metrics_all, first_bundle, run_dir / "figures", tradeoff)

    latest = Path(args.out) / "latest"
    if latest.is_symlink() or latest.exists():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    os.symlink(os.path.relpath(run_dir, Path(args.out)), latest)
    segments.to_csv(Path(args.out) / "segments.csv", index=False)

    print(f"\n结果目录: {run_dir}")
    print("\n== A/B 总体（多种子均值；improvement 为正表示 B 更优）==")
    overall = ab_df[ab_df["segment"] == "ALL"]
    print(
        overall[["metric", "A_mean", "B_mean", "improvement_B_minus_A", "p_value", "significant_0.05"]]
        .to_string(index=False)
    )
    print("\n== 分象限 total_cost / fill_rate 改善（正=B 更优）==")
    print(
        ab_df[ab_df["metric"].isin(["total_cost", "fill_rate"])]
        .pivot_table(index="segment", columns="metric", values="improvement_B_minus_A")
        .round(4)
        .to_string()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
