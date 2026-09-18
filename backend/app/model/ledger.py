"""台账与统计组 ORM（docs/db-schema.md §11.3–§11.5）：库存预警 / 每日结存快照 / 供货价。"""

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
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.model.base import PK, AuditMixin, utcnow

_ALERT_TYPE_CHECK = (
    "alert_type IN ('LOW_STOCK','OUT_OF_STOCK','OVER_STOCK','NEAR_EXPIRY','EXPIRED','SLOW_MOVING')"
)
_ALERT_LEVEL_CHECK = "level IN ('INFO','WARN','CRITICAL')"
_ALERT_STATUS_CHECK = "status IN ('OPEN','ACKED','RESOLVED','IGNORED')"
_ALERT_OPEN_WHERE = "status IN ('OPEN','ACKED') AND deleted_at IS NULL"


class StockAlert(Base, AuditMixin):
    __tablename__ = "stock_alert"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"))
    batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory_batch.id", ondelete="RESTRICT"))
    alert_type: Mapped[str] = mapped_column(String(16), nullable=False)
    level: Mapped[str] = mapped_column(String(8), default="WARN", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    message: Mapped[str | None] = mapped_column(String(255))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_stock_alert_open",
            text("material_id"),
            text("COALESCE(warehouse_id, 0)"),
            text("COALESCE(batch_id, 0)"),
            "alert_type",
            unique=True,
            postgresql_where=text(_ALERT_OPEN_WHERE),
            sqlite_where=text(_ALERT_OPEN_WHERE),
        ),
        CheckConstraint(_ALERT_TYPE_CHECK, name="ck_stock_alert_type"),
        CheckConstraint(_ALERT_LEVEL_CHECK, name="ck_stock_alert_level"),
        CheckConstraint(_ALERT_STATUS_CHECK, name="ck_stock_alert_status"),
        Index("ix_stock_alert_material_status", "material_id", "status"),
        Index("ix_stock_alert_type_status", "alert_type", "status"),
        Index("ix_stock_alert_triggered_at", "triggered_at"),
    )


class InventorySnapshotDaily(Base):
    """每日结存快照（物资×仓库×日）；可重算 upsert，供预测聚合。只写不软删。"""

    __tablename__ = "inventory_snapshot_daily"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    locked_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    in_transit_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index(
            "uq_inventory_snapshot_daily",
            "snapshot_date",
            "material_id",
            "warehouse_id",
            unique=True,
        ),
        Index("ix_isd_snapshot_date", "snapshot_date"),
        Index("ix_isd_material_date", "material_id", "snapshot_date"),
    )


class MaterialSupplierPrice(Base, AuditMixin):
    __tablename__ = "material_supplier_price"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    min_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lead_time_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_msp_material_supplier",
            "material_id",
            "supplier_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_msp_preferred",
            "material_id",
            unique=True,
            postgresql_where=text("is_preferred AND deleted_at IS NULL"),
            sqlite_where=text("is_preferred AND deleted_at IS NULL"),
        ),
        CheckConstraint("unit_price >= 0", name="ck_msp_unit_price"),
        CheckConstraint("min_order_qty IS NULL OR min_order_qty > 0", name="ck_msp_min_order_qty"),
        CheckConstraint("lead_time_days IS NULL OR lead_time_days > 0", name="ck_msp_lead_time"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_msp_status"),
        Index("ix_msp_supplier_id", "supplier_id"),
    )
