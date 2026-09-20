"""系统组 ORM（docs/db-schema.md §13）：dict 数据字典 / scheduled_task_log 定时任务日志 / attachment 附件元数据。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.model.base import PK, AuditMixin, utcnow

_DICT_ACTIVE_WHERE = "deleted_at IS NULL"


class Dict(Base, AuditMixin):
    """展示型数据字典（§13.1）。

    边界：业务枚举以代码常量 + 列 CHECK 为单一事实源，dict **只**提供展示标签/排序/启停，
    不承载业务判断（避免双份真值）。
    """

    __tablename__ = "dict"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    dict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    dict_key: Mapped[str] = mapped_column(String(64), nullable=False)
    dict_label: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index(
            "uq_dict_type_key",
            "dict_type",
            "dict_key",
            unique=True,
            postgresql_where=text(_DICT_ACTIVE_WHERE),
            sqlite_where=text(_DICT_ACTIVE_WHERE),
        ),
        Index("ix_dict_type", "dict_type"),
    )


class ScheduledTaskLog(Base):
    """定时任务执行日志（§13.2）：追加写；不更新历史、不软删（日志类例外）。

    真正的调度器（APScheduler/Celery）未引入（AGENTS：能不引入依赖就不引入）；
    本表 + 记录接口供 shell/cron 或后台任务上报执行结果，便于排查。
    """

    __tablename__ = "scheduled_task_log"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    task_name: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="RUNNING", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    affected_rows: Mapped[int | None] = mapped_column(Integer)
    result_summary: Mapped[str | None] = mapped_column(String(255))
    error_detail: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','SUCCESS','FAILED','SKIPPED')",
            name="ck_scheduled_task_log_status",
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_stl_duration_ms"),
        CheckConstraint("affected_rows IS NULL OR affected_rows >= 0", name="ck_stl_affected_rows"),
        Index("ix_stl_task_name_started_at", "task_name", "started_at"),
        Index("ix_stl_status", "status"),
    )


class Attachment(Base, AuditMixin):
    """附件元数据（§13.3）：文件本体不入库，DB 只存元数据与相对路径。"""

    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(String(128))
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage: Mapped[str] = mapped_column(String(16), default="LOCAL", nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))

    __table_args__ = (
        CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_attachment_file_size"),
        CheckConstraint("storage IN ('LOCAL','OSS','S3')", name="ck_attachment_storage"),
        Index("ix_attachment_biz", "biz_type", "biz_id"),
        Index("ix_attachment_sha256", "sha256"),
    )
