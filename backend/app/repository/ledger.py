"""台账与统计数据访问：库存预警 / 每日快照 / 供货价。"""

from datetime import date

from sqlalchemy import func, select

from app.model.ledger import InventorySnapshotDaily, MaterialSupplierPrice, StockAlert


class StockAlertRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, alert_id: int):
        obj = self.db.get(StockAlert, alert_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list(
        self,
        offset: int,
        limit: int,
        status: str | None = None,
        alert_type: str | None = None,
        material_id: int | None = None,
    ):
        stmt = select(StockAlert).where(StockAlert.deleted_at.is_(None))
        if status:
            stmt = stmt.where(StockAlert.status == status)
        if alert_type:
            stmt = stmt.where(StockAlert.alert_type == alert_type)
        if material_id is not None:
            stmt = stmt.where(StockAlert.material_id == material_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(StockAlert.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def open_keys(self) -> set[tuple[int, int, int, str]]:
        stmt = select(
            StockAlert.material_id, StockAlert.warehouse_id, StockAlert.batch_id, StockAlert.alert_type
        ).where(StockAlert.deleted_at.is_(None), StockAlert.status.in_(("OPEN", "ACKED")))
        return {(m, w or 0, b or 0, t) for m, w, b, t in self.db.execute(stmt).all()}


class InventorySnapshotRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def get(self, snapshot_date: date, material_id: int, warehouse_id: int):
        stmt = select(InventorySnapshotDaily).where(
            InventorySnapshotDaily.snapshot_date == snapshot_date,
            InventorySnapshotDaily.material_id == material_id,
            InventorySnapshotDaily.warehouse_id == warehouse_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, offset: int, limit: int, snapshot_date: date | None = None, material_id: int | None = None):
        stmt = select(InventorySnapshotDaily)
        if snapshot_date is not None:
            stmt = stmt.where(InventorySnapshotDaily.snapshot_date == snapshot_date)
        if material_id is not None:
            stmt = stmt.where(InventorySnapshotDaily.material_id == material_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = (
            self.db.execute(
                stmt.order_by(
                    InventorySnapshotDaily.snapshot_date.desc(),
                    InventorySnapshotDaily.material_id,
                    InventorySnapshotDaily.warehouse_id,
                )
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)


class MaterialSupplierPriceRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, price_id: int):
        obj = self.db.get(MaterialSupplierPrice, price_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def find_pair(self, material_id: int, supplier_id: int, exclude_id: int | None = None):
        stmt = select(MaterialSupplierPrice).where(
            MaterialSupplierPrice.material_id == material_id,
            MaterialSupplierPrice.supplier_id == supplier_id,
            MaterialSupplierPrice.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(MaterialSupplierPrice.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_preferred(self, material_id: int, exclude_id: int | None = None):
        stmt = select(MaterialSupplierPrice).where(
            MaterialSupplierPrice.material_id == material_id,
            MaterialSupplierPrice.is_preferred.is_(True),
            MaterialSupplierPrice.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(MaterialSupplierPrice.id != exclude_id)
        return list(self.db.execute(stmt).scalars().all())

    def list(self, offset: int, limit: int, material_id: int | None = None, supplier_id: int | None = None):
        stmt = select(MaterialSupplierPrice).where(MaterialSupplierPrice.deleted_at.is_(None))
        if material_id is not None:
            stmt = stmt.where(MaterialSupplierPrice.material_id == material_id)
        if supplier_id is not None:
            stmt = stmt.where(MaterialSupplierPrice.supplier_id == supplier_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(MaterialSupplierPrice.id).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)
