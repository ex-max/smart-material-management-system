"""操作日志数据访问（§10.6：只追加、可重算查询）。"""

from datetime import datetime

from sqlalchemy import func, select

from app.model.user import OperationLog


class OperationLogRepo:
    def __init__(self, db) -> None:
        self.db = db

    def list(
        self,
        offset: int,
        limit: int,
        user_id: int | None = None,
        module: str | None = None,
        action: str | None = None,
        result: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[list[OperationLog], int]:
        base = select(OperationLog)
        if user_id is not None:
            base = base.where(OperationLog.user_id == user_id)
        if module:
            base = base.where(OperationLog.module == module)
        if action:
            base = base.where(OperationLog.action == action)
        if result:
            base = base.where(OperationLog.result == result)
        if start_time is not None:
            base = base.where(OperationLog.created_at >= start_time)
        if end_time is not None:
            base = base.where(OperationLog.created_at <= end_time)
        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        rows = (
            self.db.execute(
                base.order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)
