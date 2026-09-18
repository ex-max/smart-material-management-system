"""M3 基线预测实验：Naive / 季节 Naive / MA / ETS 的 rolling-origin 回测。

用法（在 ml/ 下）：
    .venv/bin/python -m erp_ml.baseline --seeds 1 2 3 --tag m3-baseline

结果落 ``ml/results/runs/<YYYYMMDD-HHMM>_<tag>/``，并更新 ``latest`` 软链。
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

import numpy as np
import pandas as pd

from . import __version__
from .artifacts import package_versions, sha256_array
from .backtest import run_backtest
from .config import BacktestConfig, GeneratorConfig
from .dataset import build_dataset
from .models import model_codes
from .series import summarize_segments

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
# matplotlib 缓存放到项目内（沙箱/CI 下 ~/.config 可能不可写）
os.environ.setdefault("MPLCONFIGDIR", str(RESULTS_DIR / ".mplconfig"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M3 基线预测滚动回测")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--skus", type=int, default=800)
    parser.add_argument("--warehouses", type=int, default=1)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--start", type=str, default="2023-01-01")
    parser.add_argument("--max-series", type=int, default=200, help="每个 seed 分层抽样的序列上限")
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 14, 30])
    parser.add_argument("--initial-train", type=int, default=180)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--models", type=str, nargs="+", default=list(model_codes()))
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--tag", type=str, default="m3-baseline")
    parser.add_argument("--out", type=str, default=str(RESULTS_DIR))
    parser.add_argument("--no-figures", action="store_true")
    return parser


def stratified_indices(meta: pd.DataFrame, max_series: int, seed: int) -> np.ndarray:
    """按需求象限分层抽样，避免被某一大类主导。"""
    if len(meta) <= max_series:
        return meta.index.to_numpy()
    rng = np.random.default_rng(seed * 31 + 7)
    classes = sorted(meta["demand_class"].unique())
    per_class = max(max_series // len(classes), 1)
    picked: list[int] = []
    for demand_class in classes:
        group = meta.index[meta["demand_class"] == demand_class].to_numpy()
        size = min(per_class, group.size)
        picked.extend(rng.choice(group, size=size, replace=False).tolist())
    if len(picked) < max_series:
        remaining = np.setdiff1d(meta.index.to_numpy(), np.asarray(picked))
        extra = min(max_series - len(picked), remaining.size)
        if extra > 0:
            picked.extend(rng.choice(remaining, size=extra, replace=False).tolist())
    return np.asarray(sorted(picked))


def summarize(metrics: pd.DataFrame) -> pd.DataFrame:
    keys = ["seed", "horizon", "model"]
    grouped = metrics.groupby(keys + ["demand_class"], as_index=False).agg(
        n_series=("series_key", "count"),
        mae=("mae", "mean"),
        rmse=("rmse", "mean"),
        smape=("smape", "mean"),
        mase=("mase", "mean"),
        seconds=("seconds", "sum"),
    )
    overall = metrics.groupby(keys, as_index=False).agg(
        n_series=("series_key", "count"),
        mae=("mae", "mean"),
        rmse=("rmse", "mean"),
        smape=("smape", "mean"),
        mase=("mase", "mean"),
        seconds=("seconds", "sum"),
    )
    overall["demand_class"] = "ALL"
    per_seed = pd.concat([grouped, overall[grouped.columns]], ignore_index=True)
    summary = per_seed.groupby(["horizon", "model", "demand_class"], as_index=False).agg(
        n_series=("n_series", "max"),
        n_seeds=("seed", "nunique"),
        smape_mean=("smape", "mean"),
        smape_std=("smape", "std"),
        mase_mean=("mase", "mean"),
        mase_std=("mase", "std"),
        mae_mean=("mae", "mean"),
        rmse_mean=("rmse", "mean"),
        seconds_mean=("seconds", "mean"),
    )
    summary = summary.rename(columns={"demand_class": "segment"})
    summary["smape_std"] = summary["smape_std"].fillna(0.0)
    summary["mase_std"] = summary["mase_std"].fillna(0.0)
    return summary.sort_values(["horizon", "segment", "model"]).reset_index(drop=True)


def _git_commit() -> str:
    repo = Path(__file__).resolve().parents[2]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def _write_figures(summary: pd.DataFrame, segments: pd.DataFrame, figures_dir: Path, horizon: int) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover - 无 matplotlib 时跳过图
        return
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figures_dir.mkdir(parents=True, exist_ok=True)

    counts = summarize_segments(segments)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts["demand_class"], counts["series_count"], color="#4C72B0")
    ax.set_title("需求象限分布（ADI/CV²）")
    ax.set_xlabel("需求象限")
    ax.set_ylabel("序列数")
    for x, value in enumerate(counts["series_count"]):
        ax.text(x, value, str(int(value)), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "segment_distribution.png", dpi=300)
    plt.close(fig)

    subset = summary[(summary["horizon"] == horizon) & (summary["segment"] != "ALL")]
    if subset.empty:
        return
    pivot = subset.pivot_table(index="segment", columns="model", values="smape_mean")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pivot.plot(kind="bar", ax=ax)
    ax.set_title(f"各象限 sMAPE（horizon={horizon} 天）")
    ax.set_xlabel("需求象限")
    ax.set_ylabel("sMAPE (%)")
    ax.legend(title="模型", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / f"model_smape_by_segment_h{horizon}.png", dpi=300)
    plt.close(fig)


def _print_tables(summary: pd.DataFrame) -> None:
    first_horizon = int(summary["horizon"].min())
    overall = summary[(summary["horizon"] == first_horizon) & (summary["segment"] == "ALL")]
    print(f"\n== 总体（horizon={first_horizon} 天，多种子均值±标准差）==")
    print(
        overall[["model", "smape_mean", "smape_std", "mase_mean", "mase_std", "seconds_mean"]].to_string(
            index=False
        )
    )
    by_segment = summary[summary["horizon"] == first_horizon].pivot_table(
        index="model", columns="segment", values="smape_mean"
    )
    print(f"\n== 分象限 sMAPE（horizon={first_horizon} 天，%）==")
    print(by_segment.round(2).to_string())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backtest_cfg = BacktestConfig(
        horizons=tuple(args.horizons),
        initial_train_days=args.initial_train,
        step_days=args.step,
        models=tuple(args.models),
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
        metrics = run_backtest(values, meta_dicts, backtest_cfg)
        all_metrics.append(metrics)
        print(f"seed={seed}: {len(selected)} 序列 × {len(backtest_cfg.models)} 模型回测完成")

    metrics_df = pd.concat(all_metrics, ignore_index=True)
    summary_df = summarize(metrics_df)

    run_dir = Path(args.out) / "runs" / f"{datetime.now().strftime('%Y%m%d-%H%M')}_{args.tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    metrics_df.to_csv(run_dir / "metrics.csv", index=False)
    summary_df.to_csv(run_dir / "summary.csv", index=False)
    assert segments is not None
    segments.to_csv(run_dir / "segments.csv", index=False)

    config = {
        "tag": args.tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ml_version": __version__,
        "generator": {**base_cfg.to_dict(), "seeds": args.seeds},
        "seeds": args.seeds,
        "backtest": backtest_cfg.to_dict(),
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

    print(f"\n结果目录: {run_dir}")
    _print_tables(summary_df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
