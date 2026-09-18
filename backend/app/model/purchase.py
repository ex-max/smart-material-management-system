"""采购组 ORM（docs/db-schema.md §4，共 6 张表）。

请购单 purchase_requisition / pr_item、采购订单 purchase_order / po_item、
到货验收单 supplier_delivery / supplier_delivery_item。

状态流转统一走 app.core.state_machine；本模块只描述字段与约束。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.model.base import PK, AuditMixin

_DOC_STATUS_CHECK = "status IN ('DRAFT','PENDING','APPROVED','IN_PROGRESS','COMPLETED','CANCELLED')"


class MaterialSnapshotMixin:
    """单据行上的物资快照（AGENTS 不变量 3：主数据改名不影响历史单据）。"""

    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    material_code: Mapped[str] = mapped_column(String(32), nullable=False)
    material_name: Mapped[str] = mapped_column(String(128), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(128))
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False)


class PurchaseRequisition(Base, AuditMixin):
    __tablename__ = "purchase_requisition"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    dept_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(255))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["PRItem"]] = relationship(
        back_populates="requisition",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PRItem.line_no",
    )

    __table_args__ = (
        Index("uq_purchase_requisition_doc_no", "doc_no", unique=True),
        CheckConstraint(_DOC_STATUS_CHECK, name="ck_purchase_requisition_status"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_purchase_requisition_priority"),
        CheckConstraint("total_amount >= 0", name="ck_purchase_requisition_total_amount"),
        CheckConstraint("status <> 'APPROVED' OR approved_by IS NOT NULL", name="ck_purchase_requisition_approved_by"),
        Index("ix_purchase_requisition_status", "status"),
        Index("ix_purchase_requisition_requester_id", "requester_id"),
        Index("ix_purchase_requisition_expected_date", "expected_date"),
        Index("ix_purchase_requisition_created_at", "created_at"),
    )


class PRItem(Base, AuditMixin, MaterialSnapshotMixin):
    __tablename__ = "pr_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    requisition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_requisition.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(255))
    expected_date: Mapped[date | None] = mapped_column(Date)
    remark: Mapped[str | None] = mapped_column(String(255))

    requisition: Mapped["PurchaseRequisition"] = relationship(back_populates="items")

    __table_args__ = (
        Index("uq_pr_item_requisition_line", "requisition_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_pr_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_pr_item_quantity"),
        Index("ix_pr_item_material_id", "material_id"),
    )


class PurchaseOrder(Base, AuditMixin):
    __tablename__ = "purchase_order"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    requisition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase_requisition.id", ondelete="RESTRICT")
    )
    supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    order_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    buyer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    delivery_address: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(String(64))
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["POItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="POItem.line_no",
    )

    __table_args__ = (
        Index("uq_purchase_order_doc_no", "doc_no", unique=True),
        CheckConstraint(_DOC_STATUS_CHECK, name="ck_purchase_order_status"),
        CheckConstraint("expected_date IS NULL OR expected_date >= order_date", name="ck_purchase_order_expected_date"),
        CheckConstraint("total_amount >= 0", name="ck_purchase_order_total_amount"),
        CheckConstraint("tax_amount >= 0", name="ck_purchase_order_tax_amount"),
        Index("ix_purchase_order_supplier_id", "supplier_id"),
        Index("ix_purchase_order_status", "status"),
        Index("ix_purchase_order_order_date", "order_date"),
        Index("ix_purchase_order_requisition_id", "requisition_id"),
    )


class POItem(Base, AuditMixin, MaterialSnapshotMixin):
    __tablename__ = "po_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    source_pr_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("pr_item.id", ondelete="RESTRICT"))
    remark: Mapped[str | None] = mapped_column(String(255))

    order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    source_pr_item: Mapped["PRItem | None"] = relationship()

    __table_args__ = (
        Index("uq_po_item_po_line", "po_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_po_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_po_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_po_item_unit_price"),
        CheckConstraint("tax_rate BETWEEN 0 AND 100", name="ck_po_item_tax_rate"),
        CheckConstraint("amount >= 0", name="ck_po_item_amount"),
        CheckConstraint("received_qty >= 0 AND received_qty <= quantity", name="ck_po_item_received_qty"),
        Index("ix_po_item_material_id", "material_id"),
        Index("ix_po_item_source_pr_item_id", "source_pr_item_id"),
    )


class SupplierDelivery(Base, AuditMixin):
    __tablename__ = "supplier_delivery"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    received_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    inspected_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["SupplierDeliveryItem"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SupplierDeliveryItem.line_no",
    )

    __table_args__ = (
        Index("uq_supplier_delivery_doc_no", "doc_no", unique=True),
        CheckConstraint(_DOC_STATUS_CHECK, name="ck_supplier_delivery_status"),
        CheckConstraint("total_amount >= 0", name="ck_supplier_delivery_total_amount"),
        CheckConstraint("status <> 'APPROVED' OR inspected_by IS NOT NULL", name="ck_supplier_delivery_inspected_by"),
        Index("ix_supplier_delivery_po_id", "po_id"),
        Index("ix_supplier_delivery_supplier_id", "supplier_id"),
        Index("ix_supplier_delivery_status", "status"),
        Index("ix_supplier_delivery_delivery_date", "delivery_date"),
    )


class SupplierDeliveryItem(Base, AuditMixin, MaterialSnapshotMixin):
    __tablename__ = "supplier_delivery_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    delivery_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier_delivery.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    po_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("po_item.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    accepted_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    rejected_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    batch_no: Mapped[str | None] = mapped_column(String(64))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    inspection_result: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(String(255))

    delivery: Mapped["SupplierDelivery"] = relationship(back_populates="items")
    po_item: Mapped["POItem"] = relationship()

    __table_args__ = (
        Index("uq_supplier_delivery_item_delivery_line", "delivery_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_supplier_delivery_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_supplier_delivery_item_quantity"),
        CheckConstraint("accepted_qty IS NULL OR accepted_qty >= 0", name="ck_supplier_delivery_item_accepted_qty"),
        CheckConstraint("rejected_qty IS NULL OR rejected_qty >= 0", name="ck_supplier_delivery_item_rejected_qty"),
        CheckConstraint(
            "accepted_qty IS NULL OR rejected_qty IS NULL OR accepted_qty + rejected_qty <= quantity",
            name="ck_supplier_delivery_item_inspection_qty",
        ),
        CheckConstraint(
            "inspection_result IS NULL OR inspection_result IN ('PASS','CONCESSION','REJECT')",
            name="ck_supplier_delivery_item_inspection_result",
        ),
        Index("ix_supplier_delivery_item_po_item_id", "po_item_id"),
        Index("ix_supplier_delivery_item_material_id", "material_id"),
        Index("ix_supplier_delivery_item_batch_no", "batch_no"),
    )
