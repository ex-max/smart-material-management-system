"""附件 biz_type/biz_id 可空（P2：前端附件页通用上传，允许不绑定业务单据）。

Revision ID: 0009_attachment_biz_nullable
Revises: 0008_system_tables
Create Date: 2026-11-04
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_attachment_biz_nullable"
down_revision = "0008_system_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # biz_type/biz_id 允许为空：表示未绑定业务单据的通用附件（前端上传可选项）
    op.alter_column(
        "attachment",
        "biz_type",
        existing_type=sa.String(32),
        nullable=True,
        existing_comment="关联业务类型（purchase_order…）",
    )
    op.alter_column(
        "attachment",
        "biz_id",
        existing_type=sa.BigInteger(),
        nullable=True,
        existing_comment="关联业务 id",
    )


def downgrade() -> None:
    # 恢复 NOT NULL 前需先清理未绑定行（通用附件需绑定业务后回滚）
    op.execute("UPDATE attachment SET biz_type = 'GENERAL' WHERE biz_type IS NULL")
    op.execute("UPDATE attachment SET biz_id = 0 WHERE biz_id IS NULL")
    op.alter_column(
        "attachment",
        "biz_type",
        existing_type=sa.String(32),
        nullable=False,
        existing_comment="关联业务类型（purchase_order…）",
    )
    op.alter_column(
        "attachment",
        "biz_id",
        existing_type=sa.BigInteger(),
        nullable=False,
        existing_comment="关联业务 id",
    )
