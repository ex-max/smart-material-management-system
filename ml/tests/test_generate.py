import json

import numpy as np
import pandas as pd

from erp_ml.artifacts import sha256_array, write_demand_artifacts
from erp_ml.config import GeneratorConfig
from erp_ml.dataset import build_dataset

VALID_CLASSES = {"SMOOTH", "ERRATIC", "INTERMITTENT", "LUMPY"}


def test_generation_is_deterministic():
    cfg = GeneratorConfig(seed=7, skus=20, warehouses=1, years=1)
    first = build_dataset(cfg)
    second = build_dataset(cfg)
    assert np.array_equal(first.demand, second.demand)
    assert sha256_array(first.demand) == sha256_array(second.demand)


def test_shapes_and_constraints():
    cfg = GeneratorConfig(seed=1, skus=20, warehouses=2, years=1)
    ds = build_dataset(cfg)
    assert ds.demand.shape == (365, 40)
    assert (ds.demand >= 0).all()
    assert set(ds.meta["warehouse_id"].unique()) == {1, 2}
    assert set(ds.meta["demand_class"]).issubset(VALID_CLASSES)
    assert set(ds.meta["target_class"]).issubset(VALID_CLASSES)
    assert ds.meta["abc_class"].isin(["A", "B", "C"]).all()


def test_write_artifacts(tmp_path):
    cfg = GeneratorConfig(seed=3, skus=12, warehouses=1, years=1)
    ds = build_dataset(cfg)
    out = write_demand_artifacts(tmp_path, ds)
    for name in (
        "demand_daily.parquet",
        "lead_times.parquet",
        "catalog_materials.csv",
        "catalog_warehouses.csv",
        "demand_meta.csv",
        "data_version.json",
    ):
        assert (out / name).exists(), name
    version = json.loads((out / "data_version.json").read_text(encoding="utf-8"))
    assert version["n_series"] == 12
    assert version["demand_sha256"] == sha256_array(ds.demand)
    frame = pd.read_parquet(out / "demand_daily.parquet")
    assert len(frame) == 365 * 12
    assert set(frame.columns) == {"date", "material_id", "warehouse_id", "demand_qty"}
