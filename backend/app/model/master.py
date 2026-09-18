from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.model.base import PK, AuditMixin


class MaterialCategory(Base, AuditMixin):
    __tablename__ = "material_category"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("material_category.id"))
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    path: Mapped[str] = mapped_column(String(255), default="/", nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_material_category_parent_code",
            text("COALESCE(parent_id, 0)"),
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_material_category_level"),
        Index("ix_material_category_parent_id", "parent_id"),
        Index("ix_material_category_path", "path"),
        Index("ix_material_category_is_active", "is_active"),
    )


class Unit(Base, AuditMixin):
    __tablename__ = "unit"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    scale: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("uq_unit_code", "code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("scale BETWEEN 0 AND 4", name="ck_unit_scale"),
    )


class Supplier(Base, AuditMixin):
    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(64))
    contact_person: Mapped[str | None] = mapped_column(String(64))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    address: Mapped[str | None] = mapped_column(String(255))
    tax_no: Mapped[str | None] = mapped_column(String(64))
    payment_terms: Mapped[str | None] = mapped_column(String(64))
    lead_time_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("uq_supplier_code", "code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','BLACKLIST')", name="ck_supplier_status"),
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_supplier_rating"),
        Index("ix_supplier_name", "name"),
        Index("ix_supplier_status", "status"),
    )


class Warehouse(Base, AuditMixin):
    __tablename__ = "warehouse"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    manager_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("uq_warehouse_code", "code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_warehouse_manager_id", "manager_id"),
    )


class Location(Base, AuditMixin):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64))
    zone: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_location_warehouse_code",
            "warehouse_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_location_warehouse_id", "warehouse_id"),
    )


class Material(Base, AuditMixin):
    __tablename__ = "material"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(128))
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("material_category.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("unit.id"), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(64))
    barcode: Mapped[str | None] = mapped_column(String(64))
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    max_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    reorder_point: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lead_time_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_batch_managed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)
    default_supplier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("supplier.id"))
    abc_class: Mapped[str | None] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("uq_material_code", "code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("safety_stock >= 0", name="ck_material_safety_stock"),
        CheckConstraint("max_stock IS NULL OR max_stock >= safety_stock", name="ck_material_max_stock"),
        CheckConstraint("abc_class IS NULL OR abc_class IN ('A','B','C')", name="ck_material_abc_class"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_material_status"),
        Index("ix_material_category_id", "category_id"),
        Index("ix_material_unit_id", "unit_id"),
        Index("ix_material_default_supplier_id", "default_supplier_id"),
        Index("ix_material_status", "status"),
    )
