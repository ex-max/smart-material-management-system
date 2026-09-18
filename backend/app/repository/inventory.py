"""库存与入库数据访问，以及库存对账查询。"""

from sqlalchemy import func, select

from app.model.inventory import InboundItem, InboundOrder, Inventory, InventoryBatch, InventoryTransaction
from app.repository.purchase import DocRepo


class InventoryRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_grain(self, material_id: int, warehouse_id: int, for_update: bool = False):
        stmt = select(Inventory).where(
            Inventory.material_id == material_id,
            Inventory.warehouse_id == warehouse_id,
            Inventory.deleted_at.is_(None),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list(self, offset: int, limit: int, material_id: int | None = None, warehouse_id: int | None = None):
        stmt = select(Inventory).where(Inventory.deleted_at.is_(None))
        if material_id is not None:
            stmt = stmt.where(Inventory.material_id == material_id)
        if warehouse_id is not None:
            stmt = stmt.where(Inventory.warehouse_id == warehouse_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(Inventory.material_id, Inventory.warehouse_id).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)


class InventoryBatchRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_grain(self, material_id: int, warehouse_id: int, batch_no: str, for_update: bool = False):
        stmt = select(InventoryBatch).where(
            InventoryBatch.material_id == material_id,
            InventoryBatch.warehouse_id == warehouse_id,
            InventoryBatch.batch_no == batch_no,
            InventoryBatch.deleted_at.is_(None),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list(self, offset: int, limit: int, material_id: int | None = None, warehouse_id: int | None = None):
        stmt = select(InventoryBatch).where(InventoryBatch.deleted_at.is_(None))
        if material_id is not None:
            stmt = stmt.where(InventoryBatch.material_id == material_id)
        if warehouse_id is not None:
            stmt = stmt.where(InventoryBatch.warehouse_id == warehouse_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = (
            self.db.execute(
                stmt.order_by(InventoryBatch.material_id, InventoryBatch.warehouse_id, InventoryBatch.batch_no)
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)


class InventoryTransactionRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list(
        self,
        offset: int,
        limit: int,
        material_id: int | None = None,
        warehouse_id: int | None = None,
        source_type: str | None = None,
    ):
        stmt = select(InventoryTransaction)
        if material_id is not None:
            stmt = stmt.where(InventoryTransaction.material_id == material_id)
        if warehouse_id is not None:
            stmt = stmt.where(InventoryTransaction.warehouse_id == warehouse_id)
        if source_type is not None:
            stmt = stmt.where(InventoryTransaction.source_type == source_type)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(InventoryTransaction.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def sum_by_material_warehouse(self) -> dict[tuple[int, int], object]:
        stmt = select(
            InventoryTransaction.material_id,
            InventoryTransaction.warehouse_id,
            func.sum(InventoryTransaction.quantity),
        ).group_by(InventoryTransaction.material_id, InventoryTransaction.warehouse_id)
        return {(m, w): s for m, w, s in self.db.execute(stmt).all()}


class InventoryBatchSumRepo:
    """批次汇总（对账用）。"""

    def __init__(self, db) -> None:
        self.db = db

    def sum_by_material_warehouse(self) -> dict[tuple[int, int], object]:
        stmt = (
            select(InventoryBatch.material_id, InventoryBatch.warehouse_id, func.sum(InventoryBatch.quantity))
            .where(InventoryBatch.deleted_at.is_(None))
            .group_by(InventoryBatch.material_id, InventoryBatch.warehouse_id)
        )
        return {(m, w): s for m, w, s in self.db.execute(stmt).all()}

    def sum_by_batch(self) -> dict[int, object]:
        stmt = select(InventoryTransaction.batch_id, func.sum(InventoryTransaction.quantity)).group_by(
            InventoryTransaction.batch_id
        )
        return {b: s for b, s in self.db.execute(stmt).all()}


class InboundOrderRepo(DocRepo):
    model = InboundOrder
    doc_prefix = "IN"


class InboundItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_inbound(self, inbound_id: int) -> list[InboundItem]:
        stmt = select(InboundItem).where(InboundItem.inbound_id == inbound_id).order_by(InboundItem.line_no)
        return list(self.db.execute(stmt).scalars().all())
