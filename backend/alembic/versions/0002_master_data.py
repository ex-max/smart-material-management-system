"""主数据：material_category / unit / supplier / warehouse / location / material

Revision ID: 0002_master_data
Revises: 0001_init_org_auth
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_master_data"
down_revision = "0001_init_org_auth"
branch_labels = None
depends_on = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "unit",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("scale", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("scale BETWEEN 0 AND 4", name="ck_unit_scale"),
        comment="计量单位",
    )
    op.create_index("uq_unit_code", "unit", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "supplier",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("short_name", sa.String(64)),
        sa.Column("contact_person", sa.String(64)),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("email", sa.String(128)),
        sa.Column("address", sa.String(255)),
        sa.Column("tax_no", sa.String(64)),
        sa.Column("payment_terms", sa.String(64)),
        sa.Column("lead_time_days", sa.Numeric(8, 2)),
        sa.Column("rating", sa.Numeric(3, 2)),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE','BLACKLIST')", name="ck_supplier_status"),
        sa.CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_supplier_rating"),
        comment="供应商",
    )
    op.create_index("uq_supplier_code", "supplier", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_supplier_name", "supplier", ["name"])
    op.create_index("ix_supplier_status", "supplier", ["status"])

    op.create_table(
        "warehouse",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("address", sa.String(255)),
        sa.Column("manager_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        comment="仓库",
    )
    op.create_index("uq_warehouse_code", "warehouse", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_warehouse_manager_id", "warehouse", ["manager_id"])

    op.create_table(
        "material_category",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("material_category.id")),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("path", sa.String(255), nullable=False, server_default="/"),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("level BETWEEN 1 AND 5", name="ck_material_category_level"),
        comment="物资分类",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_material_category_parent_code "
        "ON material_category (COALESCE(parent_id, 0), code) WHERE deleted_at IS NULL"
    )
    op.create_index("ix_material_category_parent_id", "material_category", ["parent_id"])
    op.create_index("ix_material_category_path", "material_category", ["path"])
    op.create_index("ix_material_category_is_active", "material_category", ["is_active"])

    op.create_table(
        "location",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64)),
        sa.Column("zone", sa.String(32)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        comment="库位",
    )
    op.create_index(
        "uq_location_warehouse_code",
        "location",
        ["warehouse_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_location_warehouse_id", "location", ["warehouse_id"])

    op.create_table(
        "material",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("spec", sa.String(128)),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("material_category.id"), nullable=False),
        sa.Column("unit_id", sa.BigInteger(), sa.ForeignKey("unit.id"), nullable=False),
        sa.Column("brand", sa.String(64)),
        sa.Column("barcode", sa.String(64)),
        sa.Column("safety_stock", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("max_stock", sa.Numeric(18, 4)),
        sa.Column("reorder_point", sa.Numeric(18, 4)),
        sa.Column("lead_time_days", sa.Numeric(8, 2)),
        sa.Column("is_batch_managed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("shelf_life_days", sa.Integer()),
        sa.Column("default_supplier_id", sa.BigInteger(), sa.ForeignKey("supplier.id")),
        sa.Column("abc_class", sa.String(1)),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.Text()),
        *_audit_columns(),
        sa.CheckConstraint("safety_stock >= 0", name="ck_material_safety_stock"),
        sa.CheckConstraint("max_stock IS NULL OR max_stock >= safety_stock", name="ck_material_max_stock"),
        sa.CheckConstraint("abc_class IS NULL OR abc_class IN ('A','B','C')", name="ck_material_abc_class"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_material_status"),
        comment="物资档案",
    )
    op.create_index("uq_material_code", "material", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_material_category_id", "material", ["category_id"])
    op.create_index("ix_material_unit_id", "material", ["unit_id"])
    op.create_index("ix_material_default_supplier_id", "material", ["default_supplier_id"])
    op.create_index("ix_material_status", "material", ["status"])


def downgrade() -> None:
    for name in ("ix_material_status", "ix_material_default_supplier_id", "ix_material_unit_id", "ix_material_category_id", "uq_material_code"):
        op.drop_index(name, table_name="material")
    op.drop_table("material")
    op.drop_index("ix_location_warehouse_id", table_name="location")
    op.drop_index("uq_location_warehouse_code", table_name="location")
    op.drop_table("location")
    op.drop_index("ix_material_category_is_active", table_name="material_category")
    op.drop_index("ix_material_category_path", table_name="material_category")
    op.drop_index("ix_material_category_parent_id", table_name="material_category")
    op.execute("DROP INDEX IF EXISTS uq_material_category_parent_code")
    op.drop_table("material_category")
    op.drop_index("ix_warehouse_manager_id", table_name="warehouse")
    op.drop_index("uq_warehouse_code", table_name="warehouse")
    op.drop_table("warehouse")
    op.drop_index("ix_supplier_status", table_name="supplier")
    op.drop_index("ix_supplier_name", table_name="supplier")
    op.drop_index("uq_supplier_code", table_name="supplier")
    op.drop_table("supplier")
    op.drop_index("uq_unit_code", table_name="unit")
    op.drop_table("unit")
