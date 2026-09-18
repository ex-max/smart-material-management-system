"""需求序列元数据与 ADI/CV²（Syntetos–Boylan）分层。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .catalog import Catalog
from .config import DEMAND_CLASSES

ADI_THRESHOLD = 1.32
CV2_THRESHOLD = 0.49


def adi_cv2(values: np.ndarray) -> tuple[float, float, int]:
    """返回 (ADI, CV², 非零天数)。

    ADI = 观测天数 / 非零天数；CV² = 非零需求量的变异系数平方。
    """
    values = np.asarray(values, dtype=float)
    n = values.size
    nonzero = values[values > 0]
    k = nonzero.size
    if k == 0:
        return float(n), 0.0, 0
    adi = n / k
    mean = float(nonzero.mean())
    cv2 = 0.0 if mean <= 0 else float((nonzero.std(ddof=0) / mean) ** 2)
    return float(adi), cv2, int(k)


def classify(adi: float, cv2: float) -> str:
    """Syntetos–Boylan 四象限。"""
    if adi < ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
        return "SMOOTH"
    if adi >= ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
        return "INTERMITTENT"
    if adi < ADI_THRESHOLD:
        return "ERRATIC"
    return "LUMPY"


def build_demand_meta(
    demand: np.ndarray,
    sku_idx: np.ndarray,
    wh_idx: np.ndarray,
    dates: pd.DatetimeIndex,
    catalog: Catalog,
    target_per_series: np.ndarray | None = None,
) -> pd.DataFrame:
    material_ids = catalog.materials["material_id"].to_numpy()
    warehouse_ids = catalog.warehouses["warehouse_id"].to_numpy()
    start = dates[0].date().isoformat()
    end = dates[-1].date().isoformat()
    rows = []
    for j in range(demand.shape[1]):
        values = demand[:, j].astype(float)
        adi, cv2, nonzero = adi_cv2(values)
        rows.append(
            {
                "series_key": f"{int(material_ids[sku_idx[j]])}:{int(warehouse_ids[wh_idx[j]])}",
                "material_id": int(material_ids[sku_idx[j]]),
                "warehouse_id": int(warehouse_ids[wh_idx[j]]),
                "obs_days": int(values.size),
                "non_zero_days": nonzero,
                "adi": round(adi, 4),
                "cv2": round(cv2, 4),
                "demand_class": classify(adi, cv2),
                "target_class": (
                    DEMAND_CLASSES[int(target_per_series[j])] if target_per_series is not None else None
                ),
                "mean_daily": round(float(values.mean()), 4),
                "std_daily": round(float(values.std(ddof=0)), 4),
                "total_demand": int(values.sum()),
                "data_start_date": start,
                "data_end_date": end,
            }
        )
    return pd.DataFrame(rows)


def assign_abc(meta: pd.DataFrame, materials: pd.DataFrame) -> pd.DataFrame:
    """按年消耗金额（需求量×单价）帕累托分档 A≤80% / B≤95% / C 其余。"""
    meta = meta.copy()
    price = materials.set_index("material_id")["unit_price"]
    meta["annual_value"] = meta["material_id"].map(price).astype(float) * meta["total_demand"].astype(float)
    material_value = meta.groupby("material_id")["annual_value"].sum().sort_values(ascending=False)
    total = float(material_value.sum())
    if total <= 0.0:
        meta["abc_class"] = "C"
        return meta
    cumulative = material_value.cumsum() / total
    abc = pd.Series("C", index=material_value.index, dtype="object")
    abc[cumulative <= 0.80] = "A"
    abc[(cumulative > 0.80) & (cumulative <= 0.95)] = "B"
    meta["abc_class"] = meta["material_id"].map(abc).fillna("C")
    return meta


def summarize_segments(meta: pd.DataFrame) -> pd.DataFrame:
    """按需求象限汇总序列数与占比（论文分层饼图/表用）。"""
    counts = meta["demand_class"].value_counts()
    total = int(counts.sum())
    out = pd.DataFrame({"demand_class": counts.index, "series_count": counts.to_numpy()})
    out["share"] = (out["series_count"] / total).round(4) if total else 0.0
    return out.reset_index(drop=True)
