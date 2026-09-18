"""把「生成 + 分层」组装成一个数据集对象，供 generate 与 baseline 复用。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .catalog import Catalog, load_catalog
from .config import GeneratorConfig
from .demand import generate_demand
from .series import assign_abc, build_demand_meta


@dataclass
class DemandDataset:
    cfg: GeneratorConfig
    catalog: Catalog
    demand: np.ndarray
    sku_idx: np.ndarray
    wh_idx: np.ndarray
    dates: pd.DatetimeIndex
    meta: pd.DataFrame
    catalog_source: str
    target_class: np.ndarray

    @property
    def n_series(self) -> int:
        return int(self.demand.shape[1])


def build_dataset(
    cfg: GeneratorConfig,
    catalog: Catalog | None = None,
    catalog_source: str = "synthetic",
    database_url: str | None = None,
) -> DemandDataset:
    if catalog is None:
        catalog = load_catalog(cfg, source=catalog_source, database_url=database_url)
    demand, sku_idx, wh_idx, dates, target_class = generate_demand(cfg, catalog)
    meta = build_demand_meta(demand, sku_idx, wh_idx, dates, catalog, target_class)
    meta = assign_abc(meta, catalog.materials)
    return DemandDataset(
        cfg=cfg,
        catalog=catalog,
        demand=demand,
        sku_idx=sku_idx,
        wh_idx=wh_idx,
        dates=dates,
        meta=meta,
        catalog_source=catalog_source,
        target_class=target_class,
    )
