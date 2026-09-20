"""操作日志业务：best-effort 写入 + 只读分页查询。

写入使用**独立 session**（AGENTS：禁止跨请求复用 session；后台/旁路任务用独立 session）；
任何异常只记服务端日志，绝不影响主请求。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.database import get_session_factory
from app.model.base import utcnow
from app.model.user import OperationLog
from app.repository.operation_log import OperationLogRepo

logger = logging.getLogger("app.audit")


def record_operation_log(fields: dict) -> None:
    """追加一条操作日志；best-effort，失败只记日志。"""
    try:
        db = get_session_factory()()
        try:
            db.add(OperationLog(created_at=utcnow(), **fields))
            db.commit()
        finally:
            db.close()
    except Exception:  # pragma: no cover - 依赖真实故障路径
        logger.exception("操作日志写入失败（best-effort，已忽略）")


def _to_naive_utc(value: datetime | None) -> datetime | None:
    """统一成 naive UTC，兼容 PG timestamptz 与 SQLite DATETIME 的比较。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class OperationLogService:
    def __init__(self, db) -> None:
        self.db = db
        self.repo = OperationLogRepo(db)

    def list(
        self,
        page: int,
        page_size: int,
        user_id: int | None = None,
        module: str | None = None,
        action: str | None = None,
        result: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ):
        return self.repo.list(
            (page - 1) * page_size,
            page_size,
            user_id=user_id,
            module=module,
            action=action,
            result=result,
            start_time=_to_naive_utc(start_time),
            end_time=_to_naive_utc(end_time),
        )
