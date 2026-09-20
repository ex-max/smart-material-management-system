"""操作日志 DTO（只读查询）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OperationLogOut(ORMBase):
    id: int
    user_id: int | None
    username: str | None
    module: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    method: str | None
    path: str | None
    ip: str | None
    user_agent: str | None
    request_id: str | None
    result: str
    error_code: str | None
    duration_ms: int | None
    detail: dict | None
    created_at: datetime
