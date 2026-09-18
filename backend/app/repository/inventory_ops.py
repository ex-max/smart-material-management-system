"""出库 / 调拨 / 盘点 数据访问。"""

from sqlalchemy import select

from app.model.inventory_ops import (
    OutboundItem,
    OutboundOrder,
    StocktakeItem,
    StocktakeOrder,
    TransferItem,
    TransferOrder,
)
from app.repository.purchase import DocRepo


class OutboundOrderRepo(DocRepo):
    model = OutboundOrder
    doc_prefix = "OUT"

    def find_by_transfer(self, transfer_id: int) -> OutboundOrder | None:
        stmt = select(OutboundOrder).where(
            OutboundOrder.transfer_order_id == transfer_id, OutboundOrder.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()


class OutboundItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_outbound(self, outbound_id: int) -> list[OutboundItem]:
        stmt = select(OutboundItem).where(OutboundItem.outbound_id == outbound_id).order_by(OutboundItem.line_no)
        return list(self.db.execute(stmt).scalars().all())


class TransferOrderRepo(DocRepo):
    model = TransferOrder
    doc_prefix = "TR"


class TransferItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_transfer(self, transfer_id: int) -> list[TransferItem]:
        stmt = select(TransferItem).where(TransferItem.transfer_id == transfer_id).order_by(TransferItem.line_no)
        return list(self.db.execute(stmt).scalars().all())


class StocktakeOrderRepo(DocRepo):
    model = StocktakeOrder
    doc_prefix = "ST"


class StocktakeItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_stocktake(self, stocktake_id: int) -> list[StocktakeItem]:
        stmt = (
            select(StocktakeItem)
            .where(StocktakeItem.stocktake_id == stocktake_id)
            .order_by(StocktakeItem.line_no)
        )
        return list(self.db.execute(stmt).scalars().all())
