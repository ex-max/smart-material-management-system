"""落盘：生成数据写 ``data/seed_<n>/``，实验结果写 ``ml/results/``（均不进 git）。"""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .dataset import DemandDataset
from .demand import generate_lead_times

TRACKED_PACKAGES = (
    "numpy",
    "pandas",
    "scipy",
    "statsmodels",
    "lightgbm",
    "pyarrow",
    "matplotlib",
    "joblib",
    "psycopg",
)


def sha256_array(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.shape).encode())
    digest.update(str(contiguous.dtype).encode())
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in TRACKED_PACKAGES:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = "missing"
    return versions


def summarize_mix(series: pd.Series) -> dict[str, int]:
    return {str(key): int(value) for key, value in series.value_counts().to_dict().items()}


def to_long_dataframe(ds: DemandDataset) -> pd.DataFrame:
    n_days, n_series = ds.demand.shape
    material_ids = ds.catalog.materials["material_id"].to_numpy()[ds.sku_idx]
    warehouse_ids = ds.catalog.warehouses["warehouse_id"].to_numpy()[ds.wh_idx]
    return pd.DataFrame(
        {
            "date": np.tile(ds.dates.to_numpy(), n_series),
            "material_id": np.repeat(material_ids, n_days),
            "warehouse_id": np.repeat(warehouse_ids, n_days),
            "demand_qty": ds.demand.T.reshape(-1),
        }
    )


def write_demand_artifacts(out_root: str | Path, ds: DemandDataset) -> Path:
    out = Path(out_root) / f"seed_{ds.cfg.seed}"
    out.mkdir(parents=True, exist_ok=True)

    ds.catalog.materials.to_csv(out / "catalog_materials.csv", index=False)
    ds.catalog.warehouses.to_csv(out / "catalog_warehouses.csv", index=False)
    ds.meta.to_csv(out / "demand_meta.csv", index=False)

    long_df = to_long_dataframe(ds)
    long_df.to_parquet(out / "demand_daily.parquet", index=False)
    generate_lead_times(ds.cfg, ds.catalog, ds.dates).to_parquet(out / "lead_times.parquet", index=False)

    version: dict[str, Any] = {
        "generator": ds.cfg.to_dict(),
        "catalog_source": ds.catalog_source,
        "n_days": int(ds.demand.shape[0]),
        "n_series": int(ds.demand.shape[1]),
        "n_demand_rows": int(long_df.shape[0]),
        "demand_sha256": sha256_array(ds.demand),
        "class_mix": summarize_mix(ds.meta["demand_class"]),
        "abc_mix": summarize_mix(ds.meta["abc_class"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "packages": package_versions(),
    }
    (out / "data_version.json").write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
