"""系统组 DTO（docs/db-schema.md §13）：dict / scheduled_task_log / attachment。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- §13.1 dict ----------------
class DictItemCreate(BaseModel):
    dict_type: str = Field(min_length=1, max_length=64)
    dict_key: str = Field(min_length=1, max_length=64)
    dict_label: str = Field(min_length=1, max_length=128)
    sort_no: int = Field(default=0, ge=0)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class DictItemUpdate(BaseModel):
    """dict_type/dict_key 不可改（与主数据 code 口径一致）。"""

    dict_label: str | None = Field(default=None, min_length=1, max_length=128)
    sort_no: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class DictItemOut(ORMBase):
    id: int
    dict_type: str
    dict_key: str
    dict_label: str
    sort_no: int
    is_active: bool
    remark: str | None


class DictTypeOut(BaseModel):
    dict_type: str
    item_count: int
    active_count: int


# ---------------- §13.2 scheduled_task_log ----------------
class TaskLogAppend(BaseModel):
    task_name: str = Field(min_length=1, max_length=64)
    task_type: str | None = Field(default=None, max_length=32)
    status: str = Field(default="RUNNING", pattern="^(RUNNING|SUCCESS|FAILED|SKIPPED)$")
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    affected_rows: int | None = Field(default=None, ge=0)
    result_summary: str | None = Field(default=None, max_length=255)
    error_detail: str | None = None
    trace_id: str | None = Field(default=None, max_length=64)


class TaskLogFinish(BaseModel):
    """把 RUNNING 记录收尾为终态；已终态不可再改。"""

    status: str = Field(default="SUCCESS", pattern="^(SUCCESS|FAILED|SKIPPED)$")
    duration_ms: int | None = Field(default=None, ge=0)
    affected_rows: int | None = Field(default=None, ge=0)
    result_summary: str | None = Field(default=None, max_length=255)
    error_detail: str | None = None


class ScheduledTaskLogOut(ORMBase):
    id: int
    task_name: str
    task_type: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    affected_rows: int | None
    result_summary: str | None
    error_detail: str | None
    trace_id: str | None


# ---------------- §13.3 attachment ----------------
class AttachmentOut(ORMBase):
    id: int
    biz_type: str
    biz_id: int
    file_name: str
    file_path: str
    file_size: int | None
    content_type: str | None
    sha256: str | None
    storage: str
    uploaded_by: int | None
    created_at: datetime
