"""主数据目录：默认合成；可选**只读**业务库 material/warehouse 主数据。

注意：``load_catalog_from_db`` 只执行 SELECT，绝不写业务表（AGENTS 不变量 4）。
业务库为空或不可达时由 ``load_catalog(source="auto")`` 回退到合成目录。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import GeneratorConfig

CATEGORIES = ("五金", "电气", "劳保", "化工", "备件", "工具", "仪表", "管阀")
UNITS = ("PCS", "KG", "M", "BOX", "SET")


@dataclass
class Catalog:
    materials: pd.DataFrame
    warehouses: pd.DataFrame

    @property
    def n_materials(self) -> int:
        return len(self.materials)

    @property
    def n_warehouses(self) -> int:
        return len(self.warehouses)


def build_synthetic_catalog(cfg: GeneratorConfig) -> Catalog:
    """构造合成主数据（与业务库表字段对齐，但不写库）。"""
    rng = np.random.default_rng(cfg.seed)
    n = cfg.skus
    material_ids = np.arange(1, n + 1, dtype=np.int64)
    materials = pd.DataFrame(
        {
            "material_id": material_ids,
            "code": [f"M{i:06d}" for i in material_ids],
            "name": [f"物资{i:04d}" for i in material_ids],
            "category": rng.choice(CATEGORIES, size=n),
            "unit": rng.choice(UNITS, size=n, p=[0.55, 0.15, 0.10, 0.10, 0.10]),
            "unit_price": np.round(np.exp(rng.normal(cfg.price_log_mu, cfg.price_log_sigma, size=n)), 2),
            "lead_time_mean": np.round(rng.uniform(cfg.lt_mean_min, cfg.lt_mean_max, size=n), 2),
            "is_batch_managed": rng.random(n) < cfg.batch_managed_ratio,
            "source": "synthetic",
        }
    )
    warehouses = pd.DataFrame(
        {
            "warehouse_id": np.arange(1, cfg.warehouses + 1, dtype=np.int64),
            "code": [f"WH{i:02d}" for i in range(1, cfg.warehouses + 1)],
            "name": [f"中心仓库{i}" for i in range(1, cfg.warehouses + 1)],
            "source": "synthetic",
        }
    )
    return Catalog(materials=materials, warehouses=warehouses)


def normalize_pg_dsn(database_url: str) -> str:
    """把 SQLAlchemy 风格 URL 转成 psycopg 可用 DSN（只读连接用）。"""
    dsn = database_url.strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if dsn.startswith(prefix):
            return "postgresql://" + dsn[len(prefix):]
    return dsn


def load_catalog_from_db(database_url: str) -> Catalog | None:
    """只读业务库主数据；无数据 / 无驱动 / 连接失败均返回 None。"""
    try:
        import psycopg
    except ImportError:  # pragma: no cover - 依赖缺失时静默回退
        return None
    try:
        with psycopg.connect(normalize_pg_dsn(database_url), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.code, m.name, COALESCE(c.name, '未分类') AS category, "
                    "COALESCE(u.code, 'PCS') AS unit, "
                    "COALESCE((SELECT p.unit_price FROM material_supplier_price p "
                    "          WHERE p.material_id = m.id AND p.is_preferred "
                    "          AND p.deleted_at IS NULL LIMIT 1), 1.0) AS unit_price, "
                    "COALESCE(m.lead_time_days, 0) AS lead_time_mean, "
                    "COALESCE(m.is_batch_managed, false) AS is_batch_managed "
                    "FROM material m "
                    "LEFT JOIN material_category c ON c.id = m.category_id "
                    "LEFT JOIN unit u ON u.id = m.unit_id "
                    "WHERE m.deleted_at IS NULL ORDER BY m.id"
                )
                material_rows = cur.fetchall()
                cur.execute("SELECT id, code, name FROM warehouse WHERE deleted_at IS NULL ORDER BY id")
                warehouse_rows = cur.fetchall()
    except Exception:  # pragma: no cover - 真库不可达时不阻断生成
        return None
    if not material_rows or not warehouse_rows:
        return None
    materials = pd.DataFrame(
        material_rows,
        columns=[
            "material_id",
            "code",
            "name",
            "category",
            "unit",
            "unit_price",
            "lead_time_mean",
            "is_batch_managed",
        ],
    )
    materials["source"] = "business_db"
    warehouses = pd.DataFrame(warehouse_rows, columns=["warehouse_id", "code", "name"])
    warehouses["source"] = "business_db"
    return Catalog(materials=materials, warehouses=warehouses)


def load_catalog(
    cfg: GeneratorConfig,
    source: str = "auto",
    database_url: str | None = None,
) -> Catalog:
    """按 source 选择目录：synthetic 强制合成，db 强制业务库，auto 优先业务库。"""
    if source == "synthetic":
        return build_synthetic_catalog(cfg)
    db_catalog = load_catalog_from_db(database_url) if database_url else None
    if source == "db":
        if db_catalog is None:
            raise RuntimeError("业务库无主数据或不可连接，无法使用 catalog-source=db")
        return db_catalog
    if source == "auto":
        return db_catalog if db_catalog is not None else build_synthetic_catalog(cfg)
    raise ValueError(f"未知 catalog source: {source}")
