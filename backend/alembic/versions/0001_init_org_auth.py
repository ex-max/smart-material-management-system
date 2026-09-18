"""组织与权限：users/roles/permissions/user_role/role_permission/operation_log

Revision ID: 0001_init_org_auth
Revises:
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_init_org_auth"
down_revision = None
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
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("real_name", sa.String(64)),
        sa.Column("phone", sa.String(32)),
        sa.Column("email", sa.String(128)),
        sa.Column("avatar", sa.String(255)),
        sa.Column("dept_name", sa.String(64)),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip", sa.String(45)),
        sa.Column("pwd_updated_at", sa.DateTime(timezone=True)),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('ACTIVE','DISABLED','LOCKED')", name="ck_users_status"),
        comment="用户",
    )
    op.create_index("uq_users_username", "users", ["username"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_roles_status"),
        comment="角色",
    )
    op.create_index("uq_roles_code", "roles", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("permissions.id")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("method", sa.String(8)),
        sa.Column("path", sa.String(255)),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("type IN ('MENU','API','BUTTON','DATA')", name="ck_permissions_type"),
        comment="权限",
    )
    op.create_index("uq_permissions_code", "permissions", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_permissions_parent_id", "permissions", ["parent_id"])
    op.create_index("ix_permissions_type", "permissions", ["type"])

    op.create_table(
        "user_role",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        *_audit_columns(),
        comment="用户-角色",
    )
    op.create_index("uq_user_role", "user_role", ["user_id", "role_id"], unique=True)
    op.create_index("ix_user_role_role_id", "user_role", ["role_id"])

    op.create_table(
        "role_permission",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        *_audit_columns(),
        comment="角色-权限",
    )
    op.create_index("uq_role_permission", "role_permission", ["role_id", "permission_id"], unique=True)
    op.create_index("ix_role_permission_permission_id", "role_permission", ["permission_id"])

    op.create_table(
        "operation_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(64)),
        sa.Column("module", sa.String(32)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("method", sa.String(8)),
        sa.Column("path", sa.String(255)),
        sa.Column("ip", sa.String(45)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("result", sa.String(16), nullable=False, server_default="SUCCESS"),
        sa.Column("error_code", sa.String(16)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("detail", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("result IN ('SUCCESS','FAIL')", name="ck_operation_log_result"),
        comment="操作日志",
    )
    op.create_index("ix_operation_log_created_at", "operation_log", ["created_at"])
    op.create_index("ix_operation_log_user_id", "operation_log", ["user_id"])
    op.create_index("ix_operation_log_action", "operation_log", ["action"])
    op.create_index("ix_operation_log_request_id", "operation_log", ["request_id"])


def downgrade() -> None:
    for name, table in (
        ("ix_operation_log_request_id", "operation_log"),
        ("ix_operation_log_action", "operation_log"),
        ("ix_operation_log_user_id", "operation_log"),
        ("ix_operation_log_created_at", "operation_log"),
    ):
        op.drop_index(name, table_name=table)
    op.drop_table("operation_log")
    op.drop_index("ix_role_permission_permission_id", table_name="role_permission")
    op.drop_index("uq_role_permission", table_name="role_permission")
    op.drop_table("role_permission")
    op.drop_index("ix_user_role_role_id", table_name="user_role")
    op.drop_index("uq_user_role", table_name="user_role")
    op.drop_table("user_role")
    op.drop_index("ix_permissions_type", table_name="permissions")
    op.drop_index("ix_permissions_parent_id", table_name="permissions")
    op.drop_index("uq_permissions_code", table_name="permissions")
    op.drop_table("permissions")
    op.drop_index("uq_roles_code", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("uq_users_username", table_name="users")
    op.drop_table("users")
