"""台账与统计：stock_alert / inventory_snapshot_daily / material_supplier_price

Revision ID: 0006_ledger
Revises: 0005_inventory_ops
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_ledger"
down_revision = "0005_inventory_ops"
branch_labels = None
depends_on = None

_ALERT_OPEN_WHERE = "status IN ('OPEN','ACKED') AND deleted_at IS NULL"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "stock_alert",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT")),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("inventory_batch.id", ondelete="RESTRICT")),
        sa.Column("alert_type", sa.String(16), nullable=False),
        sa.Column("level", sa.String(8), nullable=False, server_default="WARN"),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("threshold", sa.Numeric(18, 4)),
        sa.Column("current_value", sa.Numeric(18, 4)),
        sa.Column("message", sa.String(255)),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("acked_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("acked_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint(
            "alert_type IN ('LOW_STOCK','OUT_OF_STOCK','OVER_STOCK','NEAR_EXPIRY','EXPIRED','SLOW_MOVING')",
            name="ck_stock_alert_type",
        ),
        sa.CheckConstraint("level IN ('INFO','WARN','CRITICAL')", name="ck_stock_alert_level"),
        sa.CheckConstraint("status IN ('OPEN','ACKED','RESOLVED','IGNORED')", name="ck_stock_alert_status"),
        comment="库存预警",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_stock_alert_open ON stock_alert "
        "(material_id, COALESCE(warehouse_id, 0), COALESCE(batch_id, 0), alert_type) "
        "WHERE " + _ALERT_OPEN_WHERE
    )
    op.create_index("ix_stock_alert_material_status", "stock_alert", ["material_id", "status"])
    op.create_index("ix_stock_alert_type_status", "stock_alert", ["alert_type", "status"])
    op.create_index("ix_stock_alert_triggered_at", "stock_alert", ["triggered_at"])

    op.create_table(
        "inventory_snapshot_daily",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("locked_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("in_transit_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        comment="每日结存快照",
    )
    op.create_index(
        "uq_inventory_snapshot_daily",
        "inventory_snapshot_daily",
        ["snapshot_date", "material_id", "warehouse_id"],
        unique=True,
    )
    op.create_index("ix_isd_snapshot_date", "inventory_snapshot_daily", ["snapshot_date"])
    op.create_index("ix_isd_material_date", "inventory_snapshot_daily", ["material_id", "snapshot_date"])

    op.create_table(
        "material_supplier_price",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("min_order_qty", sa.Numeric(18, 4)),
        sa.Column("lead_time_days", sa.Numeric(8, 2)),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("unit_price >= 0", name="ck_msp_unit_price"),
        sa.CheckConstraint("min_order_qty IS NULL OR min_order_qty > 0", name="ck_msp_min_order_qty"),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days > 0", name="ck_msp_lead_time"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_msp_status"),
        comment="供货物资/供货价",
    )
    op.create_index(
        "uq_msp_material_supplier",
        "material_supplier_price",
        ["material_id", "supplier_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_msp_preferred",
        "material_supplier_price",
        ["material_id"],
        unique=True,
        postgresql_where=sa.text("is_preferred AND deleted_at IS NULL"),
    )
    op.create_index("ix_msp_supplier_id", "material_supplier_price", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_msp_supplier_id", table_name="material_supplier_price")
    op.drop_index("uq_msp_preferred", table_name="material_supplier_price")
    op.drop_index("uq_msp_material_supplier", table_name="material_supplier_price")
    op.drop_table("material_supplier_price")

    op.drop_index("ix_isd_material_date", table_name="inventory_snapshot_daily")
    op.drop_index("ix_isd_snapshot_date", table_name="inventory_snapshot_daily")
    op.drop_index("uq_inventory_snapshot_daily", table_name="inventory_snapshot_daily")
    op.drop_table("inventory_snapshot_daily")

    op.drop_index("ix_stock_alert_triggered_at", table_name="stock_alert")
    op.drop_index("ix_stock_alert_type_status", table_name="stock_alert")
    op.drop_index("ix_stock_alert_material_status", table_name="stock_alert")
    op.execute("DROP INDEX IF EXISTS uq_stock_alert_open")
    op.drop_table("stock_alert")
