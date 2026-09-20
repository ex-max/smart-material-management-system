"""系统组：dict / scheduled_task_log / attachment（docs/db-schema.md §13）。

Revision ID: 0008_system_tables
Revises: 0007_forecast_replenishment
Create Date: 2026-09-20
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_system_tables"
down_revision = "0007_forecast_replenishment"
branch_labels = None
depends_on = None

_DICT_ACTIVE_WHERE = "deleted_at IS NULL"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # ---------- §13.1 dict 数据字典 ----------
    op.create_table(
        "dict",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("dict_type", sa.String(64), nullable=False, comment="字典类型（如 doc_status、alert_type）"),
        sa.Column("dict_key", sa.String(64), nullable=False, comment="键"),
        sa.Column("dict_label", sa.String(128), nullable=False, comment="展示值"),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0", comment="排序"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="是否启用"),
        sa.Column("remark", sa.String(255), comment="备注"),
        *_audit_columns(),
        comment="数据字典（展示型：业务枚举仍以代码常量 + 列 CHECK 为单一事实源）",
    )
    op.create_index(
        "uq_dict_type_key",
        "dict",
        ["dict_type", "dict_key"],
        unique=True,
        postgresql_where=sa.text(_DICT_ACTIVE_WHERE),
        sqlite_where=sa.text(_DICT_ACTIVE_WHERE),
    )
    op.create_index("ix_dict_type", "dict", ["dict_type"])

    # ---------- §13.2 scheduled_task_log 定时任务日志 ----------
    op.create_table(
        "scheduled_task_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("task_name", sa.String(64), nullable=False, comment="任务名（alert_scan/snapshot_daily…）"),
        sa.Column("task_type", sa.String(32), comment="任务类型"),
        sa.Column("status", sa.String(16), nullable=False, server_default="RUNNING", comment="状态"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="开始时间",
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), comment="结束时间"),
        sa.Column("duration_ms", sa.Integer(), comment="耗时（毫秒）"),
        sa.Column("affected_rows", sa.Integer(), comment="影响行数"),
        sa.Column("result_summary", sa.String(255), comment="结果摘要"),
        sa.Column("error_detail", sa.Text(), comment="错误详情"),
        sa.Column("trace_id", sa.String(64), comment="链路 id"),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCESS','FAILED','SKIPPED')",
            name="ck_scheduled_task_log_status",
        ),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_stl_duration_ms"),
        sa.CheckConstraint("affected_rows IS NULL OR affected_rows >= 0", name="ck_stl_affected_rows"),
        comment="定时任务执行日志（追加写，便于排查）",
    )
    op.create_index("ix_stl_task_name_started_at", "scheduled_task_log", ["task_name", "started_at"])
    op.create_index("ix_stl_status", "scheduled_task_log", ["status"])

    # ---------- §13.3 attachment 附件元数据 ----------
    op.create_table(
        "attachment",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("biz_type", sa.String(32), nullable=False, comment="关联业务类型（purchase_order…）"),
        sa.Column("biz_id", sa.BigInteger(), nullable=False, comment="关联业务 id"),
        sa.Column("file_name", sa.String(255), nullable=False, comment="原始文件名"),
        sa.Column("file_path", sa.String(512), nullable=False, comment="存储相对路径（本地磁盘，不入 git）"),
        sa.Column("file_size", sa.BigInteger(), comment="字节数"),
        sa.Column("content_type", sa.String(128), comment="MIME 类型"),
        sa.Column("sha256", sa.String(64), comment="校验和"),
        sa.Column("storage", sa.String(16), nullable=False, server_default="LOCAL", comment="存储类型"),
        sa.Column(
            "uploaded_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
            comment="上传人",
        ),
        *_audit_columns(),
        sa.CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_attachment_file_size"),
        sa.CheckConstraint("storage IN ('LOCAL','OSS','S3')", name="ck_attachment_storage"),
        comment="附件元数据（文件本体不入库）",
    )
    op.create_index("ix_attachment_biz", "attachment", ["biz_type", "biz_id"])
    op.create_index("ix_attachment_sha256", "attachment", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_attachment_sha256", table_name="attachment")
    op.drop_index("ix_attachment_biz", table_name="attachment")
    op.drop_table("attachment")

    op.drop_index("ix_stl_status", table_name="scheduled_task_log")
    op.drop_index("ix_stl_task_name_started_at", table_name="scheduled_task_log")
    op.drop_table("scheduled_task_log")

    op.drop_index("ix_dict_type", table_name="dict")
    op.drop_index("uq_dict_type_key", table_name="dict")
    op.drop_table("dict")
