"""系统组数据访问（docs/db-schema.md §13）。"""

from datetime import datetime

from sqlalchemy import case, func, or_, select

from app.model.system import Attachment, Dict, ScheduledTaskLog


class DictRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, item_id: int):
        obj = self.db.get(Dict, item_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def find_by_type_key(self, dict_type: str, dict_key: str, exclude_id: int | None = None):
        stmt = select(Dict).where(
            Dict.dict_type == dict_type, Dict.dict_key == dict_key, Dict.deleted_at.is_(None)
        )
        if exclude_id is not None:
            stmt = stmt.where(Dict.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_items(
        self,
        offset: int,
        limit: int,
        dict_type: str | None = None,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Dict], int]:
        stmt = select(Dict).where(Dict.deleted_at.is_(None))
        if dict_type:
            stmt = stmt.where(Dict.dict_type == dict_type)
        if is_active is not None:
            stmt = stmt.where(Dict.is_active.is_(is_active))
        if keyword:
            pattern = "%" + keyword + "%"
            stmt = stmt.where(or_(Dict.dict_key.ilike(pattern), Dict.dict_label.ilike(pattern)))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = (
            self.db.execute(
                stmt.order_by(Dict.dict_type, Dict.sort_no, Dict.id).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    def list_active(self, dict_type: str) -> list[Dict]:
        stmt = (
            select(Dict)
            .where(Dict.dict_type == dict_type, Dict.is_active.is_(True), Dict.deleted_at.is_(None))
            .order_by(Dict.sort_no, Dict.id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_types(self) -> list[tuple[str, int, int]]:
        stmt = (
            select(
                Dict.dict_type,
                func.count(Dict.id),
                func.sum(case((Dict.is_active.is_(True), 1), else_=0)),
            )
            .where(Dict.deleted_at.is_(None))
            .group_by(Dict.dict_type)
            .order_by(Dict.dict_type)
        )
        return [(row[0], int(row[1]), int(row[2] or 0)) for row in self.db.execute(stmt).all()]

    def add(self, obj: Dict) -> Dict:
        self.db.add(obj)
        self.db.flush()
        return obj


class ScheduledTaskLogRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get(self, item_id: int):
        return self.db.get(ScheduledTaskLog, item_id)

    def list(
        self,
        offset: int,
        limit: int,
        task_name: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[list[ScheduledTaskLog], int]:
        stmt = select(ScheduledTaskLog)
        if task_name:
            stmt = stmt.where(ScheduledTaskLog.task_name == task_name)
        if task_type:
            stmt = stmt.where(ScheduledTaskLog.task_type == task_type)
        if status:
            stmt = stmt.where(ScheduledTaskLog.status == status)
        if start_time is not None:
            stmt = stmt.where(ScheduledTaskLog.started_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(ScheduledTaskLog.started_at <= end_time)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = (
            self.db.execute(
                stmt.order_by(ScheduledTaskLog.started_at.desc(), ScheduledTaskLog.id.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    def add(self, obj: ScheduledTaskLog) -> ScheduledTaskLog:
        self.db.add(obj)
        self.db.flush()
        return obj


class AttachmentRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, item_id: int):
        obj = self.db.get(Attachment, item_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def list(
        self,
        offset: int,
        limit: int,
        biz_type: str | None = None,
        biz_id: int | None = None,
    ) -> tuple[list[Attachment], int]:
        stmt = select(Attachment).where(Attachment.deleted_at.is_(None))
        if biz_type:
            stmt = stmt.where(Attachment.biz_type == biz_type)
        if biz_id is not None:
            stmt = stmt.where(Attachment.biz_id == biz_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(Attachment.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def add(self, obj: Attachment) -> Attachment:
        self.db.add(obj)
        self.db.flush()
        return obj

