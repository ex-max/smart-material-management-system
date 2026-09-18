"""库存与入库：inventory_batch / inventory / inventory_transaction / inbound_order / inbound_item

Revision ID: 0004_inventory_inbound
Revises: 0003_procurement
Create Date: 2026-09-18

库存流水为唯一真值源；inventory / inventory_batch 只能由过账服务同事务更新。
本迁移人工编写（已在本机 PostgreSQL 16 实例上 upgrade/downgrade 验证）。
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_inventory_inbound"
down_revision = "0003_procurement"
branch_labels = None
depends_on = None

_BATCH_DEFAULT_NO = "__DEFAULT__"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _snapshot_columns() -> list[sa.Column]:
    return [
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("material_code", sa.String(32), nullable=False),
        sa.Column("material_name", sa.String(128), nullable=False),
        sa.Column("spec", sa.String(128)),
        sa.Column("unit_name", sa.String(32), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "inventory_batch",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_no", sa.String(64), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("production_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("inbound_date", sa.Date()),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("locked_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="NORMAL"),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_batch_quantity"),
        sa.CheckConstraint("locked_qty >= 0", name="ck_inventory_batch_locked_qty"),
        sa.CheckConstraint("quantity >= locked_qty", name="ck_inventory_batch_available"),
        sa.CheckConstraint(
            "status IN ('NORMAL','NEAR_EXPIRY','EXPIRED','FROZEN')", name="ck_inventory_batch_status"
        ),
        comment="批次结存（物资×仓库×批次）",
    )
    op.create_index(
        "uq_inventory_batch_grain",
        "inventory_batch",
        ["material_id", "warehouse_id", "batch_no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_inventory_batch_default",
        "inventory_batch",
        ["material_id", "warehouse_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND deleted_at IS NULL"),
    )
    op.create_index("ix_inventory_batch_warehouse_id", "inventory_batch", ["warehouse_id"])
    op.create_index("ix_inventory_batch_expiry_date", "inventory_batch", ["expiry_date"])
    op.create_index("ix_inventory_batch_material_warehouse", "inventory_batch", ["material_id", "warehouse_id"])
    op.create_index("ix_inventory_batch_status", "inventory_batch", ["status"])

    op.create_table(
        "inventory",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("locked_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_txn_at", sa.DateTime(timezone=True)),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_quantity"),
        sa.CheckConstraint("locked_qty >= 0", name="ck_inventory_locked_qty"),
        sa.CheckConstraint("quantity >= locked_qty", name="ck_inventory_available"),
        comment="汇总结存（物资×仓库）",
    )
    op.create_index(
        "uq_inventory_material_warehouse",
        "inventory",
        ["material_id", "warehouse_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_inventory_warehouse_id", "inventory", ["warehouse_id"])
    op.create_index("ix_inventory_material_warehouse", "inventory", ["material_id", "warehouse_id"])

    op.create_table(
        "inventory_transaction",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("idem_key", sa.String(64)),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "batch_id", sa.BigInteger(), sa.ForeignKey("inventory_batch.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("txn_type", sa.String(16), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("source_no", sa.String(32)),
        sa.Column("source_line_id", sa.BigInteger()),
        sa.Column("balance_after", sa.Numeric(18, 4)),
        sa.Column("unit_price", sa.Numeric(18, 4)),
        sa.Column("amount", sa.Numeric(18, 4)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("remark", sa.String(255)),
        sa.CheckConstraint("quantity <> 0", name="ck_inventory_transaction_quantity"),
        sa.CheckConstraint(
            "txn_type IN ('INBOUND','OUTBOUND','TRANSFER_IN','TRANSFER_OUT',"
            "'STOCKTAKE_GAIN','STOCKTAKE_LOSS','REVERSAL')",
            name="ck_inventory_transaction_txn_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('INBOUND','OUTBOUND','TRANSFER','STOCKTAKE','MANUAL')",
            name="ck_inventory_transaction_source_type",
        ),
        comment="库存流水（唯一真值源，只 INSERT）",
    )
    op.create_index(
        "uq_inventory_transaction_idem_key",
        "inventory_transaction",
        ["idem_key"],
        unique=True,
        postgresql_where=sa.text("idem_key IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_transaction_material_warehouse_occurred",
        "inventory_transaction",
        ["material_id", "warehouse_id", "occurred_at"],
    )
    op.create_index("ix_inventory_transaction_batch_id", "inventory_transaction", ["batch_id"])
    op.create_index("ix_inventory_transaction_source", "inventory_transaction", ["source_type", "source_id"])
    op.create_index("ix_inventory_transaction_txn_type", "inventory_transaction", ["txn_type"])
    op.create_index("ix_inventory_transaction_occurred_at", "inventory_transaction", ["occurred_at"])

    op.create_table(
        "inbound_order",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="PURCHASE"),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("delivery_id", sa.BigInteger(), sa.ForeignKey("supplier_delivery.id", ondelete="RESTRICT")),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("inbound_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("inbound_at", sa.DateTime(timezone=True)),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(
            "source_type IN ('PURCHASE','TRANSFER','RETURN','OTHER')", name="ck_inbound_order_source_type"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED')", name="ck_inbound_order_status"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_inbound_order_total_amount"),
        sa.CheckConstraint(
            "source_type <> 'PURCHASE' OR delivery_id IS NOT NULL", name="ck_inbound_order_purchase_delivery"
        ),
        comment="入库单头",
    )
    op.create_index("uq_inbound_order_doc_no", "inbound_order", ["doc_no"], unique=True)
    op.create_index("ix_inbound_order_warehouse_id", "inbound_order", ["warehouse_id"])
    op.create_index("ix_inbound_order_status", "inbound_order", ["status"])
    op.create_index("ix_inbound_order_delivery_id", "inbound_order", ["delivery_id"])
    op.create_index("ix_inbound_order_source", "inbound_order", ["source_type", "source_id"])

    op.create_table(
        "inbound_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("inbound_id", sa.BigInteger(), sa.ForeignKey("inbound_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("inventory_batch.id", ondelete="RESTRICT")),
        sa.Column("batch_no", sa.String(64)),
        sa.Column("production_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("location.id", ondelete="RESTRICT")),
        sa.Column("po_item_id", sa.BigInteger(), sa.ForeignKey("po_item.id", ondelete="RESTRICT")),
        sa.Column("remark", sa.String(255)),
        *_snapshot_columns(),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_inbound_item_line_no"),
        sa.CheckConstraint("quantity > 0", name="ck_inbound_item_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_inbound_item_unit_price"),
        sa.CheckConstraint("amount >= 0", name="ck_inbound_item_amount"),
        sa.CheckConstraint("batch_id IS NULL OR batch_no IS NOT NULL", name="ck_inbound_item_batch"),
        comment="入库单行",
    )
    op.create_index("uq_inbound_item_inbound_line", "inbound_item", ["inbound_id", "line_no"], unique=True)
    op.create_index("ix_inbound_item_material_id", "inbound_item", ["material_id"])
    op.create_index("ix_inbound_item_batch_id", "inbound_item", ["batch_id"])
    op.create_index("ix_inbound_item_po_item_id", "inbound_item", ["po_item_id"])
    op.create_index("ix_inbound_item_location_id", "inbound_item", ["location_id"])


def downgrade() -> None:
    for name in (
        "ix_inbound_item_location_id",
        "ix_inbound_item_po_item_id",
        "ix_inbound_item_batch_id",
        "ix_inbound_item_material_id",
        "uq_inbound_item_inbound_line",
    ):
        op.drop_index(name, table_name="inbound_item")
    op.drop_table("inbound_item")

    for name in (
        "ix_inbound_order_source",
        "ix_inbound_order_delivery_id",
        "ix_inbound_order_status",
        "ix_inbound_order_warehouse_id",
        "uq_inbound_order_doc_no",
    ):
        op.drop_index(name, table_name="inbound_order")
    op.drop_table("inbound_order")

    for name in (
        "ix_inventory_transaction_occurred_at",
        "ix_inventory_transaction_txn_type",
        "ix_inventory_transaction_source",
        "ix_inventory_transaction_batch_id",
        "ix_inventory_transaction_material_warehouse_occurred",
        "uq_inventory_transaction_idem_key",
    ):
        op.drop_index(name, table_name="inventory_transaction")
    op.drop_table("inventory_transaction")

    for name in ("ix_inventory_material_warehouse", "ix_inventory_warehouse_id", "uq_inventory_material_warehouse"):
        op.drop_index(name, table_name="inventory")
    op.drop_table("inventory")

    for name in (
        "ix_inventory_batch_status",
        "ix_inventory_batch_material_warehouse",
        "ix_inventory_batch_expiry_date",
        "ix_inventory_batch_warehouse_id",
        "uq_inventory_batch_default",
        "uq_inventory_batch_grain",
    ):
        op.drop_index(name, table_name="inventory_batch")
    op.drop_table("inventory_batch")
