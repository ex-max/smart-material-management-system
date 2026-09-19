"""M7 余力：LSTM 与 LightGBM 需求预测对比（复用 rolling-origin 协议）。

用法（在 ml/ 下）：
    .venv/bin/python -m erp_ml.lstm_experiment --seeds 1 2 3 --max-series 40 --tag m7-lstm

要点（forecast-experiment 技能）：
- 同一批分层序列、同一 BacktestConfig（初始窗 180 天、步长 7 天、horizon 7/14/30）、
  同一 backtest_global 口径，LightGBM 与 LSTM 各跑一遍；
- 输出 metrics.csv（逐序列×模型）、summary.csv（分层汇总）、
  comparison.csv（总体/分象限配对差值与 Wilcoxon p 值）；
- 所有超参与代码 commit、数据哈希写入 config.json，结果落 ml/results/runs/（不进 git）。
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
from .backtest import backtest_global
from .baseline import _print_tables, _write_figures, stratified_indices, summarize
from .config import BacktestConfig, GeneratorConfig
from .dataset import build_dataset
from .features import FeatureSpec
from .gbm import DEFAULT_LGB_PARAMS, LGBMForecaster
from .lstm import DEFAULT_LSTM_PARAMS, LSTMForecaster

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
os.environ.setdefault("MPLCONFIGDIR", str(RESULTS_DIR / ".mplconfig"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M7 余力：LSTM 与 LightGBM 需求预测对比")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--skus", type=int, default=800)
    parser.add_argument("--warehouses", type=int, default=1)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--start", type=str, default="2023-01-01")
    parser.add_argument("--max-series", type=int, default=40)
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 14, 30])
    parser.add_argument("--initial-train", type=int, default=180)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--num-boost-round", type=int, default=300)
    parser.add_argument("--lookback", type=int, default=DEFAULT_LSTM_PARAMS["lookback"])
    parser.add_argument("--hidden-size", type=int, default=DEFAULT_LSTM_PARAMS["hidden_size"])
    parser.add_argument("--lstm-epochs", type=int, default=DEFAULT_LSTM_PARAMS["epochs"])
    parser.add_argument("--windows-per-series", type=int, default=DEFAULT_LSTM_PARAMS["windows_per_series"])
    parser.add_argument("--lstm-threads", type=int, default=DEFAULT_LSTM_PARAMS["num_threads"])
    parser.add_argument("--tag", type=str, default="m7-lstm")
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


def _wilcoxon_p(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import wilcoxon

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    a, b = a[mask], b[mask]
    if a.size < 5 or np.allclose(a, b):
        return float("nan")
    try:
        return float(wilcoxon(a, b, zero_method="wilcox").pvalue)
    except ValueError:
        return float("nan")


def _paired(sub: pd.DataFrame, value: str):
    pivot = sub.pivot_table(index=["seed", "series_key"], columns="model", values=value, aggfunc="mean")
    if "lightgbm" not in pivot.columns or "lstm" not in pivot.columns:
        return None
    pivot = pivot.dropna(subset=["lightgbm", "lstm"])
    return pivot["lightgbm"].to_numpy(), pivot["lstm"].to_numpy()


def build_comparison(metrics: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon in horizons:
        horizon_df = metrics[metrics["horizon"] == horizon]
        segments = ["ALL"] + sorted(str(x) for x in horizon_df["demand_class"].unique())
        for segment in segments:
            sub = horizon_df if segment == "ALL" else horizon_df[horizon_df["demand_class"] == segment]
            row: dict = {"horizon": int(horizon), "segment": segment}
            for value in ("mase", "mae", "smape"):
                pair = _paired(sub, value)
                if pair is None:
                    continue
                gbm, lstm = pair
                row["n_pairs"] = int(gbm.size)
                row[value + "_lightgbm"] = float(np.mean(gbm))
                row[value + "_lstm"] = float(np.mean(lstm))
                row[value + "_diff_lstm_minus_lgb"] = float(np.mean(lstm - gbm))
                row[value + "_p"] = _wilcoxon_p(gbm, lstm)
            if "mase_diff_lstm_minus_lgb" in row:
                row["better_mase"] = "lstm" if row["mase_diff_lstm_minus_lgb"] < 0 else "lightgbm"
            rows.append(row)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backtest_cfg = BacktestConfig(
        horizons=tuple(args.horizons),
        initial_train_days=args.initial_train,
        step_days=args.step,
        models=(),
        max_series=args.max_series,
        n_jobs=args.lstm_threads,
    )
    base_cfg = GeneratorConfig.from_dict(
        {"skus": args.skus, "warehouses": args.warehouses, "years": args.years, "start_date": args.start}
    )
    lstm_params = {
        **DEFAULT_LSTM_PARAMS,
        "lookback": args.lookback,
        "hidden_size": args.hidden_size,
        "epochs": args.lstm_epochs,
        "windows_per_series": args.windows_per_series,
        "num_threads": args.lstm_threads,
    }

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

        gbm = LGBMForecaster(
            spec=FeatureSpec(), params=dict(DEFAULT_LGB_PARAMS), num_boost_round=args.num_boost_round
        )
        rows_gbm = backtest_global(values, ds.dates, meta_dicts, backtest_cfg, gbm, "lightgbm")
        print("seed=%d: lightgbm 面板回测完成（%d 序列）" % (seed, len(selected)))

        lstm = LSTMForecaster(**lstm_params)
        rows_lstm = backtest_global(values, ds.dates, meta_dicts, backtest_cfg, lstm, "lstm")
        print("seed=%d: lstm 面板回测完成（%d 序列）" % (seed, len(selected)))

        all_metrics.append(pd.DataFrame(rows_gbm + rows_lstm))

    metrics_df = pd.concat(all_metrics, ignore_index=True)
    summary_df = summarize(metrics_df)
    comparison_df = build_comparison(metrics_df, backtest_cfg.horizons)

    run_dir = Path(args.out) / "runs" / (datetime.now().strftime("%Y%m%d-%H%M") + "_" + args.tag)
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(run_dir / "metrics.csv", index=False)
    summary_df.to_csv(run_dir / "summary.csv", index=False)
    comparison_df.to_csv(run_dir / "comparison.csv", index=False)
    assert segments is not None
    segments.to_csv(run_dir / "segments.csv", index=False)

    config = {
        "tag": args.tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ml_version": __version__,
        "generator": {**base_cfg.to_dict(), "seeds": args.seeds},
        "seeds": args.seeds,
        "backtest": backtest_cfg.to_dict(),
        "lightgbm": {"params": dict(DEFAULT_LGB_PARAMS), "num_boost_round": args.num_boost_round},
        "lstm": lstm_params,
        "features": FeatureSpec().to_dict(),
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
    print("结果目录: %s" % run_dir)
    print()
    print("== LSTM vs LightGBM 配对对比（horizon=%d，diff = lstm - lightgbm，负值表示 LSTM 更小）==" % backtest_cfg.horizons[0])
    shown = comparison_df[comparison_df["horizon"] == backtest_cfg.horizons[0]]
    columns = [
        "segment",
        "n_pairs",
        "mase_lightgbm",
        "mase_lstm",
        "mase_diff_lstm_minus_lgb",
        "mase_p",
        "better_mase",
    ]
    print(shown[[c for c in columns if c in shown.columns]].round(4).to_string(index=False))
    _print_tables(summary_df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
