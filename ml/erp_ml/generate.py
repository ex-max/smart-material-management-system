"""模拟数据生成 CLI：``python -m erp_ml.generate``。

只读业务库（可选）、**绝不写业务表**；产物全部落 ``data/``（不进 git）。
"""

from __future__ import annotations

import argparse

from .artifacts import write_demand_artifacts
from .config import GeneratorConfig
from .dataset import build_dataset
from .series import summarize_segments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成物资需求模拟数据（只写 data/，不写业务库）")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--skus", type=int, default=800)
    parser.add_argument("--warehouses", type=int, default=1)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--start", type=str, default="2023-01-01")
    parser.add_argument("--out", type=str, default="data", help="输出根目录；实际写 <out>/seed_<seed>/")
    parser.add_argument("--catalog-source", choices=["auto", "synthetic", "db"], default="auto")
    parser.add_argument("--database-url", type=str, default="postgresql+psycopg://erp:erp@127.0.0.1:5433/erp")
    parser.add_argument("--config", type=str, default=None, help="从 JSON 读取冻结参数（可选）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base = GeneratorConfig.from_json(args.config) if args.config else GeneratorConfig()
    cfg = GeneratorConfig.from_dict(
        {
            **base.to_dict(),
            "seed": args.seed,
            "skus": args.skus,
            "warehouses": args.warehouses,
            "years": args.years,
            "start_date": args.start,
        }
    )
    ds = build_dataset(cfg, catalog_source=args.catalog_source, database_url=args.database_url)
    out = write_demand_artifacts(args.out, ds)

    print(f"生成完成 → {out}")
    print(f"规模: {ds.demand.shape[0]} 天 × {ds.n_series} 序列（{cfg.skus} SKU × {cfg.warehouses} 仓库）")
    print(f"目录来源: {ds.catalog_source}")
    print("需求分层（实测 ADI/CV²）：")
    print(summarize_segments(ds.meta).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
