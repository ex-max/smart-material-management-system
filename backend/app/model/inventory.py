"""库存与入库 ORM（docs/db-schema.md §5.1/§5.2/§5.9、§11.1/§11.2）。

- inventory：物资×仓库 汇总结存
- inventory_batch：物资×仓库×批次 结存（非批次物资用 __DEFAULT__ 默认批次）
- inventory_transaction：库存流水（唯一真值源；只 INSERT）
- inbound_order / inbound_item：入库单头/行

余额只能由过账服务在同事务内写流水 + 更新结存，禁止任何代码直接改结存。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.model.base import PK, AuditMixin, utcnow
from app.model.purchase import MaterialSnapshotMixin

BATCH_DEFAULT_NO = "__DEFAULT__"

_BATCH_STATUS_CHECK = "status IN ('NORMAL','NEAR_EXPIRY','EXPIRED','FROZEN')"
_TXN_TYPE_CHECK = (
    "txn_type IN ('INBOUND','OUTBOUND','TRANSFER_IN','TRANSFER_OUT',"
    "'STOCKTAKE_GAIN','STOCKTAKE_LOSS','REVERSAL')"
)
_SOURCE_TYPE_CHECK = "source_type IN ('INBOUND','OUTBOUND','TRANSFER','STOCKTAKE','MANUAL')"


class Inventory(Base, AuditMixin):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    locked_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_txn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_inventory_material_warehouse",
            "material_id",
            "warehouse_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity"),
        CheckConstraint("locked_qty >= 0", name="ck_inventory_locked_qty"),
        CheckConstraint("quantity >= locked_qty", name="ck_inventory_available"),
        Index("ix_inventory_warehouse_id", "warehouse_id"),
        Index("ix_inventory_material_warehouse", "material_id", "warehouse_id"),
    )


class InventoryBatch(Base, AuditMixin):
    __tablename__ = "inventory_batch"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    inbound_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    locked_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="NORMAL", nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_inventory_batch_grain",
            "material_id",
            "warehouse_id",
            "batch_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_inventory_batch_default",
            "material_id",
            "warehouse_id",
            unique=True,
            postgresql_where=text("is_default AND deleted_at IS NULL"),
        ),
        CheckConstraint("quantity >= 0", name="ck_inventory_batch_quantity"),
        CheckConstraint("locked_qty >= 0", name="ck_inventory_batch_locked_qty"),
        CheckConstraint("quantity >= locked_qty", name="ck_inventory_batch_available"),
        CheckConstraint(_BATCH_STATUS_CHECK, name="ck_inventory_batch_status"),
        Index("ix_inventory_batch_warehouse_id", "warehouse_id"),
        Index("ix_inventory_batch_expiry_date", "expiry_date"),
        Index("ix_inventory_batch_material_warehouse", "material_id", "warehouse_id"),
        Index("ix_inventory_batch_status", "status"),
    )


class InventoryTransaction(Base):
    """库存流水：追加写；只 INSERT，禁止 UPDATE/DELETE（红冲用 REVERSAL 反向流水）。"""

    __tablename__ = "inventory_transaction"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    idem_key: Mapped[str | None] = mapped_column(String(64))
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_batch.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    txn_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    source_no: Mapped[str | None] = mapped_column(String(32))
    source_line_id: Mapped[int | None] = mapped_column(BigInteger)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_inventory_transaction_idem_key",
            "idem_key",
            unique=True,
            postgresql_where=text("idem_key IS NOT NULL"),
        ),
        CheckConstraint("quantity <> 0", name="ck_inventory_transaction_quantity"),
        CheckConstraint(_TXN_TYPE_CHECK, name="ck_inventory_transaction_txn_type"),
        CheckConstraint(_SOURCE_TYPE_CHECK, name="ck_inventory_transaction_source_type"),
        Index(
            "ix_inventory_transaction_material_warehouse_occurred",
            "material_id",
            "warehouse_id",
            "occurred_at",
        ),
        Index("ix_inventory_transaction_batch_id", "batch_id"),
        Index("ix_inventory_transaction_source", "source_type", "source_id"),
        Index("ix_inventory_transaction_txn_type", "txn_type"),
        Index("ix_inventory_transaction_occurred_at", "occurred_at"),
    )


class InboundOrder(Base, AuditMixin):
    __tablename__ = "inbound_order"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    doc_no: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="PURCHASE")
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    delivery_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("supplier_delivery.id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)
    inbound_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["InboundItem"]] = relationship(
        back_populates="inbound",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InboundItem.line_no",
    )

    __table_args__ = (
        Index("uq_inbound_order_doc_no", "doc_no", unique=True),
        CheckConstraint("source_type IN ('PURCHASE','TRANSFER','RETURN','OTHER')", name="ck_inbound_order_source_type"),
        CheckConstraint(
            "status IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED')", name="ck_inbound_order_status"
        ),
        CheckConstraint("total_amount >= 0", name="ck_inbound_order_total_amount"),
        CheckConstraint(
            "source_type <> 'PURCHASE' OR delivery_id IS NOT NULL", name="ck_inbound_order_purchase_delivery"
        ),
        Index("ix_inbound_order_warehouse_id", "warehouse_id"),
        Index("ix_inbound_order_status", "status"),
        Index("ix_inbound_order_delivery_id", "delivery_id"),
        Index("ix_inbound_order_source", "source_type", "source_id"),
    )


class InboundItem(Base, AuditMixin, MaterialSnapshotMixin):
    __tablename__ = "inbound_item"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    inbound_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inbound_order.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory_batch.id", ondelete="RESTRICT"))
    batch_no: Mapped[str | None] = mapped_column(String(64))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.id", ondelete="RESTRICT"))
    po_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("po_item.id", ondelete="RESTRICT"))
    remark: Mapped[str | None] = mapped_column(String(255))

    inbound: Mapped["InboundOrder"] = relationship(back_populates="items")

    __table_args__ = (
        Index("uq_inbound_item_inbound_line", "inbound_id", "line_no", unique=True),
        CheckConstraint("line_no > 0", name="ck_inbound_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_inbound_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_inbound_item_unit_price"),
        CheckConstraint("amount >= 0", name="ck_inbound_item_amount"),
        CheckConstraint("batch_id IS NULL OR batch_no IS NOT NULL", name="ck_inbound_item_batch"),
        Index("ix_inbound_item_material_id", "material_id"),
        Index("ix_inbound_item_batch_id", "batch_id"),
        Index("ix_inbound_item_po_item_id", "po_item_id"),
        Index("ix_inbound_item_location_id", "location_id"),
    )
