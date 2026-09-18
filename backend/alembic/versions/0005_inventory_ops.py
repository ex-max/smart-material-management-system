"""库存作业：transfer_order / outbound_order / outbound_item / transfer_item / stocktake_order / stocktake_item

Revision ID: 0005_inventory_ops
Revises: 0004_inventory_inbound
Create Date: 2026-09-18

同时给 inbound_order 补 transfer_order_id（调拨入库来源）。
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_inventory_ops"
down_revision = "0004_inventory_inbound"
branch_labels = None
depends_on = None

_DOC_STATUS_CHECK = "status IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED')"


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
        "transfer_order",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("from_warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("applicant_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("transfer_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(_DOC_STATUS_CHECK, name="ck_transfer_order_status"),
        sa.CheckConstraint("from_warehouse_id <> to_warehouse_id", name="ck_transfer_order_warehouses"),
        comment="调拨单头",
    )
    op.create_index("uq_transfer_order_doc_no", "transfer_order", ["doc_no"], unique=True)
    op.create_index("ix_transfer_order_from_warehouse_id", "transfer_order", ["from_warehouse_id"])
    op.create_index("ix_transfer_order_to_warehouse_id", "transfer_order", ["to_warehouse_id"])
    op.create_index("ix_transfer_order_status", "transfer_order", ["status"])

    op.create_table(
        "outbound_order",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="REQUISITION_ISSUE"),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("transfer_order_id", sa.BigInteger(), sa.ForeignKey("transfer_order.id", ondelete="RESTRICT")),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receiver_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("dept_name", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("outbound_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("outbound_at", sa.DateTime(timezone=True)),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(
            "source_type IN ('REQUISITION_ISSUE','TRANSFER','SCRAP','OTHER')", name="ck_outbound_order_source_type"
        ),
        sa.CheckConstraint(_DOC_STATUS_CHECK, name="ck_outbound_order_status"),
        sa.CheckConstraint("total_amount >= 0", name="ck_outbound_order_total_amount"),
        comment="出库单头",
    )
    op.create_index("uq_outbound_order_doc_no", "outbound_order", ["doc_no"], unique=True)
    op.create_index("ix_outbound_order_warehouse_id", "outbound_order", ["warehouse_id"])
    op.create_index("ix_outbound_order_status", "outbound_order", ["status"])
    op.create_index("ix_outbound_order_receiver_id", "outbound_order", ["receiver_id"])
    op.create_index("ix_outbound_order_transfer_order_id", "outbound_order", ["transfer_order_id"])

    op.create_table(
        "outbound_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("outbound_id", sa.BigInteger(), sa.ForeignKey("outbound_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("inventory_batch.id", ondelete="RESTRICT")),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("location.id", ondelete="RESTRICT")),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(255)),
        *_snapshot_columns(),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_outbound_item_line_no"),
        sa.CheckConstraint("quantity > 0", name="ck_outbound_item_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_outbound_item_unit_price"),
        sa.CheckConstraint("amount >= 0", name="ck_outbound_item_amount"),
        comment="出库单行",
    )
    op.create_index("uq_outbound_item_outbound_line", "outbound_item", ["outbound_id", "line_no"], unique=True)
    op.create_index("ix_outbound_item_material_id", "outbound_item", ["material_id"])
    op.create_index("ix_outbound_item_batch_id", "outbound_item", ["batch_id"])

    op.create_table(
        "transfer_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("transfer_id", sa.BigInteger(), sa.ForeignKey("transfer_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("inventory_batch.id", ondelete="RESTRICT")),
        sa.Column("from_location_id", sa.BigInteger(), sa.ForeignKey("location.id", ondelete="RESTRICT")),
        sa.Column("to_location_id", sa.BigInteger(), sa.ForeignKey("location.id", ondelete="RESTRICT")),
        sa.Column("outbound_item_id", sa.BigInteger(), sa.ForeignKey("outbound_item.id", ondelete="RESTRICT")),
        sa.Column("inbound_item_id", sa.BigInteger(), sa.ForeignKey("inbound_item.id", ondelete="RESTRICT")),
        sa.Column("remark", sa.String(255)),
        *_snapshot_columns(),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_transfer_item_line_no"),
        sa.CheckConstraint("quantity > 0", name="ck_transfer_item_quantity"),
        comment="调拨单行",
    )
    op.create_index("uq_transfer_item_transfer_line", "transfer_item", ["transfer_id", "line_no"], unique=True)
    op.create_index("ix_transfer_item_material_id", "transfer_item", ["material_id"])
    op.create_index("ix_transfer_item_batch_id", "transfer_item", ["batch_id"])

    op.create_table(
        "stocktake_order",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False, server_default="PARTIAL"),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("planned_date", sa.Date()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("posted_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(_DOC_STATUS_CHECK, name="ck_stocktake_order_status"),
        sa.CheckConstraint("scope IN ('FULL','PARTIAL')", name="ck_stocktake_order_scope"),
        comment="盘点单头",
    )
    op.create_index("uq_stocktake_order_doc_no", "stocktake_order", ["doc_no"], unique=True)
    op.create_index("ix_stocktake_order_warehouse_id", "stocktake_order", ["warehouse_id"])
    op.create_index("ix_stocktake_order_status", "stocktake_order", ["status"])

    op.create_table(
        "stocktake_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("stocktake_id", sa.BigInteger(), sa.ForeignKey("stocktake_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("inventory_batch.id", ondelete="RESTRICT")),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("location.id", ondelete="RESTRICT")),
        sa.Column("book_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("actual_qty", sa.Numeric(18, 4)),
        sa.Column("diff_qty", sa.Numeric(18, 4)),
        sa.Column("reason", sa.String(255)),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_stocktake_item_line_no"),
        sa.CheckConstraint("book_qty >= 0", name="ck_stocktake_item_book_qty"),
        sa.CheckConstraint("actual_qty IS NULL OR actual_qty >= 0", name="ck_stocktake_item_actual_qty"),
        sa.CheckConstraint(
            "diff_qty IS NULL OR actual_qty IS NULL OR diff_qty = actual_qty - book_qty",
            name="ck_stocktake_item_diff_qty",
        ),
        comment="盘点单行",
    )
    op.create_index("uq_stocktake_item_stocktake_line", "stocktake_item", ["stocktake_id", "line_no"], unique=True)
    op.create_index("ix_stocktake_item_material_id", "stocktake_item", ["material_id"])
    op.create_index("ix_stocktake_item_batch_id", "stocktake_item", ["batch_id"])

    op.add_column(
        "inbound_order",
        sa.Column("transfer_order_id", sa.BigInteger(), sa.ForeignKey("transfer_order.id", ondelete="RESTRICT")),
    )
    op.create_index("ix_inbound_order_transfer_order_id", "inbound_order", ["transfer_order_id"])


def downgrade() -> None:
    op.drop_index("ix_inbound_order_transfer_order_id", table_name="inbound_order")
    op.drop_column("inbound_order", "transfer_order_id")

    for name in ("ix_stocktake_item_batch_id", "ix_stocktake_item_material_id", "uq_stocktake_item_stocktake_line"):
        op.drop_index(name, table_name="stocktake_item")
    op.drop_table("stocktake_item")

    for name in ("ix_stocktake_order_status", "ix_stocktake_order_warehouse_id", "uq_stocktake_order_doc_no"):
        op.drop_index(name, table_name="stocktake_order")
    op.drop_table("stocktake_order")

    for name in ("ix_transfer_item_batch_id", "ix_transfer_item_material_id", "uq_transfer_item_transfer_line"):
        op.drop_index(name, table_name="transfer_item")
    op.drop_table("transfer_item")

    for name in ("ix_outbound_item_batch_id", "ix_outbound_item_material_id", "uq_outbound_item_outbound_line"):
        op.drop_index(name, table_name="outbound_item")
    op.drop_table("outbound_item")

    for name in (
        "ix_outbound_order_transfer_order_id",
        "ix_outbound_order_receiver_id",
        "ix_outbound_order_status",
        "ix_outbound_order_warehouse_id",
        "uq_outbound_order_doc_no",
    ):
        op.drop_index(name, table_name="outbound_order")
    op.drop_table("outbound_order")

    for name in (
        "ix_transfer_order_status",
        "ix_transfer_order_to_warehouse_id",
        "ix_transfer_order_from_warehouse_id",
        "uq_transfer_order_doc_no",
    ):
        op.drop_index(name, table_name="transfer_order")
    op.drop_table("transfer_order")
