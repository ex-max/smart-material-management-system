"""预测与决策组（二）——补货策略与可解释建议 ORM（docs/db-schema.md §12.5/§12.6）。"""

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.model.base import PK, AuditMixin, utcnow

_STRATEGY_CHECK = "strategy IN ('FIXED','FORECAST','EOQ','MIN_MAX')"
_SERVICE_LEVEL_TYPE_CHECK = "service_level_type IN ('CSL','FILL_RATE')"
_TRIGGER_TYPE_CHECK = "trigger_type IN ('BELOW_ROP','FORECAST','SAFETY','MANUAL')"
_STATUS_CHECK = "status IN ('OPEN','SUGGESTED','CONVERTED','REJECTED','EXPIRED','CLOSED')"
_RS_OPEN_WHERE = "status IN ('OPEN','SUGGESTED') AND deleted_at IS NULL"


class ReplenishmentPolicy(Base, AuditMixin):
    """补货策略参数；取值优先级：material+warehouse > material > warehouse > 全局（service 层）。"""

    __tablename__ = "replenishment_policy"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    policy_code: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_name: Mapped[str | None] = mapped_column(String(64))
    material_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("material.id", ondelete="RESTRICT"))
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"))
    strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    # service_level 存小数口径（0<x<1，如 0.95），与 M5/ADR-0002 的 CSL 一致
    service_level_type: Mapped[str | None] = mapped_column(String(16))
    service_level: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    z_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    review_period_days: Mapped[int | None] = mapped_column(Integer)
    order_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    holding_cost_rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    min_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pack_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lead_time_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    safety_stock_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    rop_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_replenishment_policy_code",
            "policy_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(_STRATEGY_CHECK, name="ck_replenishment_policy_strategy"),
        CheckConstraint(
            "service_level_type IS NULL OR " + _SERVICE_LEVEL_TYPE_CHECK,
            name="ck_replenishment_policy_service_level_type",
        ),
        CheckConstraint(
            "service_level IS NULL OR (service_level > 0 AND service_level < 1)",
            name="ck_replenishment_policy_service_level",
        ),
        CheckConstraint("z_value IS NULL OR z_value >= 0", name="ck_replenishment_policy_z_value"),
        CheckConstraint(
            "review_period_days IS NULL OR review_period_days > 0",
            name="ck_replenishment_policy_review_period",
        ),
        CheckConstraint("order_cost IS NULL OR order_cost >= 0", name="ck_replenishment_policy_order_cost"),
        CheckConstraint(
            "holding_cost_rate IS NULL OR holding_cost_rate >= 0", name="ck_replenishment_policy_holding_cost"
        ),
        CheckConstraint("min_order_qty IS NULL OR min_order_qty > 0", name="ck_replenishment_policy_min_order_qty"),
        CheckConstraint("pack_size IS NULL OR pack_size > 0", name="ck_replenishment_policy_pack_size"),
        CheckConstraint("lead_time_days IS NULL OR lead_time_days > 0", name="ck_replenishment_policy_lead_time"),
        CheckConstraint(
            "safety_stock_override IS NULL OR safety_stock_override >= 0",
            name="ck_replenishment_policy_ss_override",
        ),
        CheckConstraint("rop_override IS NULL OR rop_override >= 0", name="ck_replenishment_policy_rop_override"),
        Index("ix_replenishment_policy_material_warehouse", "material_id", "warehouse_id"),
    )


class ReplenishmentSuggestion(Base, AuditMixin):
    """补货建议（可解释，AGENTS 不变量 5）：触发依据/参数来源/reason 齐备。"""

    __tablename__ = "replenishment_suggestion"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    suggestion_no: Mapped[str] = mapped_column(String(32), nullable=False)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    policy_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("replenishment_policy.id", ondelete="RESTRICT")
    )
    forecast_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("forecast_run.id", ondelete="RESTRICT")
    )
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    current_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    locked_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    in_transit_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    available_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    daily_demand_hat: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lead_time_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    sigma_d: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    sigma_lt: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    safety_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    rop: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    eoq: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    suggested_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    final_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    reason: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_pr_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase_requisition.id", ondelete="RESTRICT")
    )
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("uq_replenishment_suggestion_no", "suggestion_no", unique=True),
        CheckConstraint(_TRIGGER_TYPE_CHECK, name="ck_replenishment_suggestion_trigger_type"),
        CheckConstraint(_STATUS_CHECK, name="ck_replenishment_suggestion_status"),
        CheckConstraint("suggested_qty >= 0", name="ck_replenishment_suggestion_suggested_qty"),
        CheckConstraint("final_qty IS NULL OR final_qty >= 0", name="ck_replenishment_suggestion_final_qty"),
        Index(
            "uq_rs_open",
            "material_id",
            "warehouse_id",
            unique=True,
            postgresql_where=text(_RS_OPEN_WHERE),
            sqlite_where=text(_RS_OPEN_WHERE),
        ),
        Index("ix_rs_status_generated", "status", "generated_at"),
        Index("ix_rs_material_warehouse", "material_id", "warehouse_id"),
    )
