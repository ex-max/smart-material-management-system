"""M4 预测实验：特征工程 + LightGBM，按 ADI/CV² 象限做模型映射。

用法（在 ml/ 下）：
    .venv/bin/python -m erp_ml.experiment --seeds 1 2 3 --tag m4-forecast

模型：
- 本地单序列：naive / seasonal_naive / ma7 / ma28 / ets / arima / croston / tsb
- 面板全局：lightgbm（滞后/滑动/日历特征，erp_ml.gbm）
映射：平滑/波动 -> lightgbm（对比 arima）；间歇/块状 -> croston（对比 tsb）。

结果落 ml/results/runs/<YYYYMMDD-HHMM>_<tag>/，并更新 latest 软链。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import __version__
from .artifacts import package_versions, sha256_array
from .backtest import backtest_global, run_backtest
from .baseline import _print_tables, _write_figures, stratified_indices, summarize
from .config import BacktestConfig, GeneratorConfig
from .dataset import build_dataset
from .features import FeatureSpec
from .gbm import DEFAULT_LGB_PARAMS, LGBMForecaster
from .models import model_mapping

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
os.environ.setdefault("MPLCONFIGDIR", str(RESULTS_DIR / ".mplconfig"))

# 默认不含 ets：ETS 单序列很慢（每 seed 约 20+ 分钟），M3 基线已在其 runs/ 下；需要时用 --local-models 显式加回。
LOCAL_MODEL_CODES = ("naive", "seasonal_naive", "ma7", "ma28", "arima", "croston", "tsb")
GLOBAL_MODEL_CODES = ("lightgbm",)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M4 特征工程 + LightGBM 预测实验")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--skus", type=int, default=800)
    parser.add_argument("--warehouses", type=int, default=1)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--start", type=str, default="2023-01-01")
    parser.add_argument("--max-series", type=int, default=100)
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 14, 30])
    parser.add_argument("--initial-train", type=int, default=180)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--local-models", type=str, nargs="+", default=list(LOCAL_MODEL_CODES))
    parser.add_argument("--global-models", type=str, nargs="+", default=list(GLOBAL_MODEL_CODES))
    parser.add_argument("--num-boost-round", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--tag", type=str, default="m4-forecast")
    parser.add_argument("--out", type=str, default=str(RESULTS_DIR))
    parser.add_argument("--no-figures", action="store_true")
    return parser


def segment_mapping_table(summary: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """每个象限在目标 horizon 的最优模型，以及分层映射是否命中。"""
    subset = summary[(summary["horizon"] == horizon) & (summary["segment"] != "ALL")]
    rows = []
    mapping = model_mapping()
    for segment, group in subset.groupby("segment"):
        ordered = group.sort_values("smape_mean")
        best = ordered.iloc[0]
        primary = mapping.get(str(segment), {}).get("primary", "")
        comparison = mapping.get(str(segment), {}).get("comparison", "")
        primary_row = group[group["model"] == primary]
        comparison_row = group[group["model"] == comparison]
        rows.append(
            {
                "segment": segment,
                "recommended_model": primary,
                "comparison_model": comparison,
                "best_model": best["model"],
                "recommended_smape": (
                    float(primary_row["smape_mean"].iloc[0]) if not primary_row.empty else float("nan")
                ),
                "comparison_smape": (
                    float(comparison_row["smape_mean"].iloc[0]) if not comparison_row.empty else float("nan")
                ),
                "best_smape": float(best["smape_mean"]),
                "n_models": int(group["model"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("segment").reset_index(drop=True)


def _git_commit() -> str:
    repo = Path(__file__).resolve().parents[2]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    feature_spec = FeatureSpec()
    backtest_cfg = BacktestConfig(
        horizons=tuple(args.horizons),
        initial_train_days=args.initial_train,
        step_days=args.step,
        models=tuple(args.local_models),
        max_series=args.max_series,
        n_jobs=args.jobs,
    )
    base_cfg = GeneratorConfig.from_dict(
        {"skus": args.skus, "warehouses": args.warehouses, "years": args.years, "start_date": args.start}
    )

    all_metrics: list[pd.DataFrame] = []
    segments: pd.DataFrame | None = None
    data_hashes: dict[str, str] = {}
    for seed in args.seeds:
        cfg = GeneratorConfig.from_dict({**base_cfg.to_dict(), "seed": seed})
        ds = build_dataset(cfg, catalog_source="synthetic")
        data_hashes[str(seed)] = sha256_array(ds.demand)
        if segments is None:
            segments = ds.meta.copy()

        selected = stratified_indices(ds.meta, backtest_cfg.max_series, seed)
        meta_rows = ds.meta.loc[selected].reset_index(drop=True)
        values = [ds.demand[:, int(index)] for index in selected]
        meta_dicts = [
            {
                "seed": seed,
                "series_key": row.series_key,
                "material_id": int(row.material_id),
                "warehouse_id": int(row.warehouse_id),
                "demand_class": row.demand_class,
                "abc_class": row.abc_class,
            }
            for row in meta_rows.itertuples()
        ]

        frames: list[pd.DataFrame] = []
        if backtest_cfg.models:
            frames.append(run_backtest(values, meta_dicts, backtest_cfg))
            print(f"seed={seed}: {len(selected)} 序列 x {len(backtest_cfg.models)} 本地模型回测完成")
        for global_model in args.global_models:
            if global_model != "lightgbm":
                raise ValueError(f"未知全局模型: {global_model}")
            forecaster = LGBMForecaster(
                spec=feature_spec,
                params=dict(DEFAULT_LGB_PARAMS),
                num_boost_round=args.num_boost_round,
            )
            rows = backtest_global(values, ds.dates, meta_dicts, backtest_cfg, forecaster, "lightgbm")
            frames.append(pd.DataFrame(rows))
            print(f"seed={seed}: lightgbm 面板回测完成（{len(selected)} 序列）")
        all_metrics.append(pd.concat(frames, ignore_index=True))

    metrics_df = pd.concat(all_metrics, ignore_index=True)
    summary_df = summarize(metrics_df)
    mapping_df = segment_mapping_table(summary_df, backtest_cfg.horizons[0])

    run_dir = Path(args.out) / "runs" / f"{datetime.now().strftime('%Y%m%d-%H%M')}_{args.tag}"
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(run_dir / "metrics.csv", index=False)
    summary_df.to_csv(run_dir / "summary.csv", index=False)
    mapping_df.to_csv(run_dir / "model_mapping.csv", index=False)
    assert segments is not None
    segments.to_csv(run_dir / "segments.csv", index=False)

    config = {
        "tag": args.tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ml_version": __version__,
        "generator": {**base_cfg.to_dict(), "seeds": args.seeds},
        "seeds": args.seeds,
        "backtest": backtest_cfg.to_dict(),
        "features": feature_spec.to_dict(),
        "lightgbm": {
            "params": dict(DEFAULT_LGB_PARAMS),
            "num_boost_round": args.num_boost_round,
            "num_features": len(feature_spec.feature_names()),
            "feature_names": feature_spec.feature_names(),
        },
        "model_mapping": model_mapping(),
        "catalog_source": "synthetic",
        "data_sha256": data_hashes,
        "code_commit": _git_commit(),
        "python": platform.python_version(),
        "packages": package_versions(),
    }
    (run_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_figures:
        _write_figures(summary_df, segments, run_dir / "figures", backtest_cfg.horizons[0])

    latest = Path(args.out) / "latest"
    if latest.is_symlink() or latest.exists():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    os.symlink(os.path.relpath(run_dir, Path(args.out)), latest)
    segments.to_csv(Path(args.out) / "segments.csv", index=False)

    print()
    print(f"结果目录: {run_dir}")
    print()
    print("== 分层模型映射（horizon=%d，sMAPE %% ）==" % backtest_cfg.horizons[0])
    print(mapping_df.round(3).to_string(index=False))
    _print_tables(summary_df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
