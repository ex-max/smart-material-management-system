"""采购组数据访问。

通用能力（分页/软删过滤/单号生成）放在 DocRepo，具体单据只是不同 model + 前缀。
仓库层不写业务判断，只做查询与新增。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.model.purchase import (
    POItem,
    PRItem,
    PurchaseOrder,
    PurchaseRequisition,
    SupplierDelivery,
    SupplierDeliveryItem,
)


class DocRepo:
    model = None
    doc_prefix = ""

    def __init__(self, db) -> None:
        self.db = db

    def get(self, obj_id: int):
        return self.db.get(self.model, obj_id)

    def get_active(self, obj_id: int):
        obj = self.db.get(self.model, obj_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def list(self, offset: int, limit: int, status: str | None = None, keyword: str | None = None):
        stmt = select(self.model).where(self.model.deleted_at.is_(None))
        if status:
            stmt = stmt.where(self.model.status == status)
        if keyword:
            stmt = stmt.where(self.model.doc_no.like("%" + keyword + "%"))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(self.model.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def next_doc_no(self, day: date | None = None) -> str:
        """按 前缀-YYYYMMDD-#### 取当天最大流水 +1；唯一索引兜底并发。"""
        day = day or date.today()
        prefix = "%s-%s-" % (self.doc_prefix, day.strftime("%Y%m%d"))
        col = self.model.doc_no
        latest = self.db.execute(select(func.max(col)).where(col.like(prefix + "%"))).scalar_one_or_none()
        seq = 1
        if latest:
            tail = latest.rsplit("-", 1)[-1]
            if tail.isdigit():
                seq = int(tail) + 1
        return "%s%04d" % (prefix, seq)


class PurchaseRequisitionRepo(DocRepo):
    model = PurchaseRequisition
    doc_prefix = "PR"


class PRItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_requisition(self, requisition_id: int) -> list[PRItem]:
        stmt = select(PRItem).where(PRItem.requisition_id == requisition_id).order_by(PRItem.line_no)
        return list(self.db.execute(stmt).scalars().all())


class PurchaseOrderRepo(DocRepo):
    model = PurchaseOrder
    doc_prefix = "PO"

    def count_by_requisition(self, requisition_id: int) -> int:
        stmt = select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.requisition_id == requisition_id,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.status != "CANCELLED",
        )
        return int(self.db.execute(stmt).scalar_one())


class POItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_po(self, po_id: int) -> list[POItem]:
        stmt = select(POItem).where(POItem.po_id == po_id).order_by(POItem.line_no)
        return list(self.db.execute(stmt).scalars().all())


class SupplierDeliveryRepo(DocRepo):
    model = SupplierDelivery
    doc_prefix = "RCV"


class SupplierDeliveryItemRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_by_delivery(self, delivery_id: int) -> list[SupplierDeliveryItem]:
        stmt = (
            select(SupplierDeliveryItem)
            .where(SupplierDeliveryItem.delivery_id == delivery_id)
            .order_by(SupplierDeliveryItem.line_no)
        )
        return list(self.db.execute(stmt).scalars().all())

    def delivered_qty(self, po_item_id: int, exclude_delivery_id: int | None = None) -> Decimal:
        """某采购行累计已登记到货量（不含作废单，可排除当前单）。"""
        stmt = (
            select(func.coalesce(func.sum(SupplierDeliveryItem.quantity), 0))
            .join(SupplierDelivery, SupplierDelivery.id == SupplierDeliveryItem.delivery_id)
            .where(
                SupplierDeliveryItem.po_item_id == po_item_id,
                SupplierDelivery.deleted_at.is_(None),
                SupplierDelivery.status != "CANCELLED",
            )
        )
        if exclude_delivery_id is not None:
            stmt = stmt.where(SupplierDeliveryItem.delivery_id != exclude_delivery_id)
        return Decimal(self.db.execute(stmt).scalar_one())
