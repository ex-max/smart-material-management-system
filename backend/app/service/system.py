"""系统组业务（docs/db-schema.md §13）：数据字典 / 定时任务日志 / 附件。

边界：
- dict 只做展示型字典的 CRUD 与下拉查询，不做业务判断（业务枚举仍是代码常量 + CHECK）；
- scheduled_task_log 只追加/收尾/查询，不引入调度器（AGENTS：能不加依赖就不加）；
- attachment 文件本体落本地磁盘（可配置 ERP_ATTACHMENT_DIR），DB 只存元数据；
  上传做扩展名 + MIME 白名单与大小上限，落盘名由服务端生成（绝不用客户端文件名做路径）。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import (
    AttachmentStoreError,
    AttachmentTooLarge,
    AttachmentTypeNotAllowed,
    DictDuplicate,
    NotFound,
    TaskLogState,
)
from app.model.base import utcnow
from app.model.system import Attachment, Dict, ScheduledTaskLog
from app.repository.system import AttachmentRepo, DictRepo, ScheduledTaskLogRepo

_CHUNK = 1024 * 1024


def _to_naive_utc(value: datetime | None) -> datetime | None:
    """统一成 naive UTC，兼容 PG timestamptz 与 SQLite DATETIME 的比较/相减。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class DictService:
    def __init__(self, db) -> None:
        self.db = db
        self.repo = DictRepo(db)

    def list_types(self) -> list[dict]:
        return [
            {"dict_type": dict_type, "item_count": item_count, "active_count": active_count}
            for dict_type, item_count, active_count in self.repo.count_types()
        ]

    def list_items(self, page: int, page_size: int, **filters):
        return self.repo.list_items((page - 1) * page_size, page_size, **filters)

    def lookup(self, dict_type: str) -> list[Dict]:
        return self.repo.list_active(dict_type)

    def get(self, item_id: int) -> Dict:
        obj = self.repo.get_active(item_id)
        if obj is None:
            raise NotFound("字典项不存在")
        return obj

    def create(self, payload, operator_id: int | None = None) -> Dict:
        data = payload.model_dump(exclude_unset=True)
        if self.repo.find_by_type_key(data["dict_type"], data["dict_key"]) is not None:
            raise DictDuplicate("字典键已存在：" + data["dict_type"] + "/" + data["dict_key"])
        obj = Dict(**data)
        obj.created_by = operator_id
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, item_id: int, payload) -> Dict:
        obj = self.get(item_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, item_id: int) -> None:
        obj = self.get(item_id)
        obj.deleted_at = utcnow()
        self.db.commit()


class ScheduledTaskLogService:
    def __init__(self, db) -> None:
        self.db = db
        self.repo = ScheduledTaskLogRepo(db)

    def list(self, page: int, page_size: int, **filters):
        clean = {
            "start_time": _to_naive_utc(filters.get("start_time")),
            "end_time": _to_naive_utc(filters.get("end_time")),
        }
        for key in ("task_name", "task_type", "status"):
            clean[key] = filters.get(key)
        return self.repo.list((page - 1) * page_size, page_size, **clean)

    def get(self, item_id: int) -> ScheduledTaskLog:
        obj = self.repo.get(item_id)
        if obj is None:
            raise NotFound("任务日志不存在")
        return obj

    def append(self, payload) -> ScheduledTaskLog:
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("started_at", utcnow())
        obj = ScheduledTaskLog(**data)
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def finish(self, item_id: int, payload) -> ScheduledTaskLog:
        obj = self.get(item_id)
        if obj.status != "RUNNING":
            raise TaskLogState("任务日志已是终态（" + obj.status + "），不可再更新")
        data = payload.model_dump(exclude_unset=True)
        finished_at = utcnow()
        data["finished_at"] = finished_at
        if data.get("duration_ms") is None and obj.started_at is not None:
            delta = _to_naive_utc(finished_at) - _to_naive_utc(obj.started_at)
            data["duration_ms"] = max(0, int(delta.total_seconds() * 1000))
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj


class AttachmentService:
    """附件元数据 + 本地文件存储（LOCAL）。"""

    def __init__(self, db, storage_root: str | Path | None = None) -> None:
        self.db = db
        self.repo = AttachmentRepo(db)
        self._storage_root = Path(storage_root) if storage_root is not None else None

    @property
    def root(self) -> Path:
        base = self._storage_root if self._storage_root is not None else Path(get_settings().attachment_dir)
        return base

    def list(self, page: int, page_size: int, biz_type: str | None = None, biz_id: int | None = None):
        return self.repo.list((page - 1) * page_size, page_size, biz_type=biz_type, biz_id=biz_id)

    def get(self, item_id: int) -> Attachment:
        obj = self.repo.get_active(item_id)
        if obj is None:
            raise NotFound("附件不存在")
        return obj

    def _validate(self, file_name: str, content_type: str | None) -> str:
        ext = Path(file_name).suffix.lower()
        settings = get_settings()
        if ext not in settings.attachment_allowed_ext_set:
            raise AttachmentTypeNotAllowed("不允许的附件扩展名：" + (ext or "(无)"))
        mime = (content_type or "").lower()
        if mime and mime != "application/octet-stream":
            prefixes = settings.attachment_allowed_type_prefixes
            if not any(mime.startswith(prefix) for prefix in prefixes):
                raise AttachmentTypeNotAllowed("不允许的附件类型：" + mime)
        return ext

    def save(self, upload, biz_type: str, biz_id: int, operator_id: int | None = None) -> Attachment:
        original = Path(upload.filename or "unnamed").name or "unnamed"
        ext = self._validate(original, upload.content_type)
        settings = get_settings()
        max_bytes = max(1, int(settings.attachment_max_size_mb)) * 1024 * 1024

        rel_dir = datetime.now(timezone.utc).strftime("%Y/%m")
        target_dir = self.root / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (uuid.uuid4().hex + ext)

        digest = hashlib.sha256()
        size = 0
        try:
            with target.open("wb") as out:
                while True:
                    chunk = upload.file.read(_CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise AttachmentTooLarge(
                            "附件超过大小上限 %d MB" % settings.attachment_max_size_mb
                        )
                    digest.update(chunk)
                    out.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        if size == 0:
            target.unlink(missing_ok=True)
            raise AttachmentStoreError("附件为空")

        rel_path = (Path(rel_dir) / target.name).as_posix()
        obj = Attachment(
            biz_type=biz_type,
            biz_id=biz_id,
            file_name=original[:255],
            file_path=rel_path,
            file_size=size,
            content_type=(upload.content_type or None),
            sha256=digest.hexdigest(),
            storage="LOCAL",
            uploaded_by=operator_id,
        )
        obj.created_by = operator_id
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def resolve(self, item_id: int) -> tuple[Attachment, Path]:
        obj = self.get(item_id)
        root = self.root.resolve()
        path = (root / obj.file_path).resolve()
        if root != path and root not in path.parents:
            raise AttachmentStoreError("附件路径越界")
        if not path.is_file():
            raise NotFound("附件文件不存在（可能已被清理）")
        return obj, path

    def delete(self, item_id: int) -> None:
        """软删元数据；文件本体保留（可审计/可恢复），不做物理删除。"""
        obj = self.get(item_id)
        obj.deleted_at = utcnow()
        self.db.commit()

