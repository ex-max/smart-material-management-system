"""库存作业组 ORM（docs/db-schema.md §5.3–§5.8）：出库 / 调拨 / 盘点。

余额仍只由 StockLedger 过账；本模块只描述单据与行。
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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.model.base import PK, AuditMixin
from app.model.purchase import MaterialSnapshotMixin

_DOC_STATUS_CHECK = "status IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED')"


class TransferOrder(Base, AuditMixin):
    __tablename__ = "transfer_order"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    from_warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    to_warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    applicant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    transfer_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["TransferItem"]] = relationship(
        back_populates="transfer",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TransferItem.line_no",
    )

    __table_args__ = (
        Index("uq_transfer_order_doc_no", "doc_no", unique=True),
        CheckConstraint(_DOC_STATUS_CHECK, name="ck_transfer_order_status"),
        CheckConstraint("from_warehouse_id <> to_warehouse_id", name="ck_transfer_order_warehouses"),
        Index("ix_transfer_order_from_warehouse_id", "from_warehouse_id"),
        Index("ix_transfer_order_to_warehouse_id", "to_warehouse_id"),
        Index("ix_transfer_order_status", "status"),
    )


class OutboundOrder(Base, AuditMixin):
    __tablename__ = "outbound_order"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="REQUISITION_ISSUE")
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    transfer_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transfer_order.id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    receiver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    dept_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    outbound_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["OutboundItem"]] = relationship(
        back_populates="outbound",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OutboundItem.line_no",
    )

    __table_args__ = (
        Index("uq_outbound_order_doc_no", "doc_no", unique=True),
        CheckConstraint(
            "source_type IN ('REQUISITION_ISSUE','TRANSFER','SCRAP','OTHER')", name="ck_outbound_order_source_type"
        ),
        CheckConstraint(_DOC_STATUS_CHECK, name="ck_outbound_order_status"),
        CheckConstraint("total_amount >= 0", name="ck_outbound_order_total_amount"),
        Index("ix_outbound_order_warehouse_id", "warehouse_id"),
        Index("ix_outbound_order_status", "status"),
        Index("ix_outbound_order_receiver_id", "receiver_id"),
        Index("ix_outbound_order_transfer_order_id", "transfer_order_id"),
    )


class OutboundItem(Base, AuditMixin, MaterialSnapshotMixin):
    __tablename__ = "outbound_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    outbound_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("outbound_order.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory_batch.id", ondelete="RESTRICT"))
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.id", ondelete="RESTRICT"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    outbound: Mapped["OutboundOrder"] = relationship(back_populates="items")

    __table_args__ = (
        Index("uq_outbound_item_outbound_line", "outbound_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_outbound_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_outbound_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_outbound_item_unit_price"),
        CheckConstraint("amount >= 0", name="ck_outbound_item_amount"),
        Index("ix_outbound_item_material_id", "material_id"),
        Index("ix_outbound_item_batch_id", "batch_id"),
    )


class TransferItem(Base, AuditMixin, MaterialSnapshotMixin):
    __tablename__ = "transfer_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transfer_order.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory_batch.id", ondelete="RESTRICT"))
    from_location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.id", ondelete="RESTRICT"))
    to_location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.id", ondelete="RESTRICT"))
    outbound_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("outbound_item.id", ondelete="RESTRICT")
    )
    inbound_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inbound_item.id", ondelete="RESTRICT"))
    remark: Mapped[str | None] = mapped_column(String(255))

    transfer: Mapped["TransferOrder"] = relationship(back_populates="items")

    __table_args__ = (
        Index("uq_transfer_item_transfer_line", "transfer_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_transfer_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_transfer_item_quantity"),
        Index("ix_transfer_item_material_id", "material_id"),
        Index("ix_transfer_item_batch_id", "batch_id"),
    )


class StocktakeOrder(Base, AuditMixin):
    __tablename__ = "stocktake_order"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(16), default="PARTIAL", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["StocktakeItem"]] = relationship(
        back_populates="stocktake",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StocktakeItem.line_no",
    )

    __table_args__ = (
        Index("uq_stocktake_order_doc_no", "doc_no", unique=True),
        CheckConstraint(_DOC_STATUS_CHECK, name="ck_stocktake_order_status"),
        CheckConstraint("scope IN ('FULL','PARTIAL')", name="ck_stocktake_order_scope"),
        Index("ix_stocktake_order_warehouse_id", "warehouse_id"),
        Index("ix_stocktake_order_status", "status"),
    )


class StocktakeItem(Base, AuditMixin):
    __tablename__ = "stocktake_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    stocktake_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocktake_order.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory_batch.id", ondelete="RESTRICT"))
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.id", ondelete="RESTRICT"))
    book_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    actual_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    diff_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(String(255))

    stocktake: Mapped["StocktakeOrder"] = relationship(back_populates="items")

    __table_args__ = (
        Index("uq_stocktake_item_stocktake_line", "stocktake_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_stocktake_item_line_no"),
        CheckConstraint("book_qty >= 0", name="ck_stocktake_item_book_qty"),
        CheckConstraint("actual_qty IS NULL OR actual_qty >= 0", name="ck_stocktake_item_actual_qty"),
        CheckConstraint(
            "diff_qty IS NULL OR actual_qty IS NULL OR diff_qty = actual_qty - book_qty",
            name="ck_stocktake_item_diff_qty",
        ),
        Index("ix_stocktake_item_material_id", "material_id"),
        Index("ix_stocktake_item_batch_id", "batch_id"),
    )
