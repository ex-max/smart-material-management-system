"""采购组：purchase_requisition / pr_item / purchase_order / po_item / supplier_delivery / supplier_delivery_item

Revision ID: 0003_procurement
Revises: 0002_master_data
Create Date: 2026-09-18

本机无 PostgreSQL，无法 autogenerate；迁移按 docs/db-schema.md §4 人工编写并逐一
核对 ORM 的列/CHECK/索引。upgrade head --sql 可解析，SQLite 内存库可建表。
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_procurement"
down_revision = "0002_master_data"
branch_labels = None
depends_on = None

_DOC_STATUS_CHECK = "status IN ('DRAFT','PENDING','APPROVED','IN_PROGRESS','COMPLETED','CANCELLED')"


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
        "purchase_requisition",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("title", sa.String(128)),
        sa.Column("requester_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("dept_name", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("expected_date", sa.Date()),
        sa.Column("reason", sa.String(255)),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(_DOC_STATUS_CHECK, name="ck_purchase_requisition_status"),
        sa.CheckConstraint("priority BETWEEN 1 AND 5", name="ck_purchase_requisition_priority"),
        sa.CheckConstraint("total_amount >= 0", name="ck_purchase_requisition_total_amount"),
        sa.CheckConstraint(
            "status <> 'APPROVED' OR approved_by IS NOT NULL", name="ck_purchase_requisition_approved_by"
        ),
        comment="请购单头",
    )
    op.create_index("uq_purchase_requisition_doc_no", "purchase_requisition", ["doc_no"], unique=True)
    op.create_index("ix_purchase_requisition_status", "purchase_requisition", ["status"])
    op.create_index("ix_purchase_requisition_requester_id", "purchase_requisition", ["requester_id"])
    op.create_index("ix_purchase_requisition_expected_date", "purchase_requisition", ["expected_date"])
    op.create_index("ix_purchase_requisition_created_at", "purchase_requisition", ["created_at"])

    op.create_table(
        "pr_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "requisition_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_requisition.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("purpose", sa.String(255)),
        sa.Column("expected_date", sa.Date()),
        sa.Column("remark", sa.String(255)),
        *_snapshot_columns(),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_pr_item_line_no"),
        sa.CheckConstraint("quantity > 0", name="ck_pr_item_quantity"),
        comment="请购单行",
    )
    op.create_index("uq_pr_item_requisition_line", "pr_item", ["requisition_id", "line_no"], unique=True)
    op.create_index("ix_pr_item_material_id", "pr_item", ["material_id"])

    op.create_table(
        "purchase_order",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("requisition_id", sa.BigInteger(), sa.ForeignKey("purchase_requisition.id", ondelete="RESTRICT")),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("order_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("expected_date", sa.Date()),
        sa.Column("buyer_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("delivery_address", sa.String(255)),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("payment_terms", sa.String(64)),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(_DOC_STATUS_CHECK, name="ck_purchase_order_status"),
        sa.CheckConstraint(
            "expected_date IS NULL OR expected_date >= order_date", name="ck_purchase_order_expected_date"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_purchase_order_total_amount"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_purchase_order_tax_amount"),
        comment="采购订单头",
    )
    op.create_index("uq_purchase_order_doc_no", "purchase_order", ["doc_no"], unique=True)
    op.create_index("ix_purchase_order_supplier_id", "purchase_order", ["supplier_id"])
    op.create_index("ix_purchase_order_status", "purchase_order", ["status"])
    op.create_index("ix_purchase_order_order_date", "purchase_order", ["order_date"])
    op.create_index("ix_purchase_order_requisition_id", "purchase_order", ["requisition_id"])

    op.create_table(
        "po_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("po_id", sa.BigInteger(), sa.ForeignKey("purchase_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("received_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("expected_date", sa.Date()),
        sa.Column("source_pr_item_id", sa.BigInteger(), sa.ForeignKey("pr_item.id", ondelete="RESTRICT")),
        sa.Column("remark", sa.String(255)),
        *_snapshot_columns(),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_po_item_line_no"),
        sa.CheckConstraint("quantity > 0", name="ck_po_item_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_po_item_unit_price"),
        sa.CheckConstraint("tax_rate BETWEEN 0 AND 100", name="ck_po_item_tax_rate"),
        sa.CheckConstraint("amount >= 0", name="ck_po_item_amount"),
        sa.CheckConstraint("received_qty >= 0 AND received_qty <= quantity", name="ck_po_item_received_qty"),
        comment="采购订单行",
    )
    op.create_index("uq_po_item_po_line", "po_item", ["po_id", "line_no"], unique=True)
    op.create_index("ix_po_item_material_id", "po_item", ["material_id"])
    op.create_index("ix_po_item_source_pr_item_id", "po_item", ["source_pr_item_id"])

    op.create_table(
        "supplier_delivery",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("doc_no", sa.String(32), nullable=False),
        sa.Column("po_id", sa.BigInteger(), sa.ForeignKey("purchase_order.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("received_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("inspected_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("inspected_at", sa.DateTime(timezone=True)),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint(_DOC_STATUS_CHECK, name="ck_supplier_delivery_status"),
        sa.CheckConstraint("total_amount >= 0", name="ck_supplier_delivery_total_amount"),
        sa.CheckConstraint(
            "status <> 'APPROVED' OR inspected_by IS NOT NULL", name="ck_supplier_delivery_inspected_by"
        ),
        comment="到货/验收单头",
    )
    op.create_index("uq_supplier_delivery_doc_no", "supplier_delivery", ["doc_no"], unique=True)
    op.create_index("ix_supplier_delivery_po_id", "supplier_delivery", ["po_id"])
    op.create_index("ix_supplier_delivery_supplier_id", "supplier_delivery", ["supplier_id"])
    op.create_index("ix_supplier_delivery_status", "supplier_delivery", ["status"])
    op.create_index("ix_supplier_delivery_delivery_date", "supplier_delivery", ["delivery_date"])

    op.create_table(
        "supplier_delivery_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "delivery_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier_delivery.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("po_item_id", sa.BigInteger(), sa.ForeignKey("po_item.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("accepted_qty", sa.Numeric(18, 4)),
        sa.Column("rejected_qty", sa.Numeric(18, 4)),
        sa.Column("batch_no", sa.String(64)),
        sa.Column("production_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("inspection_result", sa.String(16)),
        sa.Column("remark", sa.String(255)),
        *_snapshot_columns(),
        *_audit_columns(),
        sa.CheckConstraint("line_no > 0", name="ck_supplier_delivery_item_line_no"),
        sa.CheckConstraint("quantity > 0", name="ck_supplier_delivery_item_quantity"),
        sa.CheckConstraint("accepted_qty IS NULL OR accepted_qty >= 0", name="ck_supplier_delivery_item_accepted_qty"),
        sa.CheckConstraint("rejected_qty IS NULL OR rejected_qty >= 0", name="ck_supplier_delivery_item_rejected_qty"),
        sa.CheckConstraint(
            "accepted_qty IS NULL OR rejected_qty IS NULL OR accepted_qty + rejected_qty <= quantity",
            name="ck_supplier_delivery_item_inspection_qty",
        ),
        sa.CheckConstraint(
            "inspection_result IS NULL OR inspection_result IN ('PASS','CONCESSION','REJECT')",
            name="ck_supplier_delivery_item_inspection_result",
        ),
        comment="到货行",
    )
    op.create_index(
        "uq_supplier_delivery_item_delivery_line",
        "supplier_delivery_item",
        ["delivery_id", "line_no"],
        unique=True,
    )
    op.create_index("ix_supplier_delivery_item_po_item_id", "supplier_delivery_item", ["po_item_id"])
    op.create_index("ix_supplier_delivery_item_material_id", "supplier_delivery_item", ["material_id"])
    op.create_index("ix_supplier_delivery_item_batch_no", "supplier_delivery_item", ["batch_no"])


def downgrade() -> None:
    for name in (
        "ix_supplier_delivery_item_batch_no",
        "ix_supplier_delivery_item_material_id",
        "ix_supplier_delivery_item_po_item_id",
        "uq_supplier_delivery_item_delivery_line",
    ):
        op.drop_index(name, table_name="supplier_delivery_item")
    op.drop_table("supplier_delivery_item")

    for name in (
        "ix_supplier_delivery_delivery_date",
        "ix_supplier_delivery_status",
        "ix_supplier_delivery_supplier_id",
        "ix_supplier_delivery_po_id",
        "uq_supplier_delivery_doc_no",
    ):
        op.drop_index(name, table_name="supplier_delivery")
    op.drop_table("supplier_delivery")

    for name in ("ix_po_item_source_pr_item_id", "ix_po_item_material_id", "uq_po_item_po_line"):
        op.drop_index(name, table_name="po_item")
    op.drop_table("po_item")

    for name in (
        "ix_purchase_order_requisition_id",
        "ix_purchase_order_order_date",
        "ix_purchase_order_status",
        "ix_purchase_order_supplier_id",
        "uq_purchase_order_doc_no",
    ):
        op.drop_index(name, table_name="purchase_order")
    op.drop_table("purchase_order")

    op.drop_index("ix_pr_item_material_id", table_name="pr_item")
    op.drop_index("uq_pr_item_requisition_line", table_name="pr_item")
    op.drop_table("pr_item")

    for name in (
        "ix_purchase_requisition_created_at",
        "ix_purchase_requisition_expected_date",
        "ix_purchase_requisition_requester_id",
        "ix_purchase_requisition_status",
        "uq_purchase_requisition_doc_no",
    ):
        op.drop_index(name, table_name="purchase_requisition")
    op.drop_table("purchase_requisition")
