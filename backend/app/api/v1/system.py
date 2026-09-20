"""系统组 API（docs/db-schema.md §13）：数据字典 / 定时任务日志 / 附件。"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.schema import system as ss
from app.schema.common import ApiResponse, PageOut
from app.service.system import AttachmentService, DictService, ScheduledTaskLogService

router = APIRouter(tags=["系统"])

_DICT_VIEW = require_perm(Perm.DICT_VIEW)
_DICT_MANAGE = require_perm(Perm.DICT_MANAGE)
_TASK_VIEW = require_perm(Perm.TASK_VIEW)
_TASK_MANAGE = require_perm(Perm.TASK_MANAGE)
_ATT_VIEW = require_perm(Perm.ATTACHMENT_VIEW)
_ATT_MANAGE = require_perm(Perm.ATTACHMENT_MANAGE)


# ---------------- §13.1 dict ----------------
@router.get("/dict-types", name="list_dict_types", response_model=ApiResponse[list[ss.DictTypeOut]])
def list_dict_types(user: User = Depends(_DICT_VIEW), db: Session = Depends(get_db)):
    return ok([ss.DictTypeOut(**item).model_dump() for item in DictService(db).list_types()])


@router.get("/dicts/{dict_type}", name="lookup_dict", response_model=ApiResponse[list[ss.DictItemOut]])
def lookup_dict(
    dict_type: str,
    user: User = Depends(_DICT_VIEW),
    db: Session = Depends(get_db),
):
    items = DictService(db).lookup(dict_type)
    return ok([ss.DictItemOut.model_validate(x).model_dump() for x in items])


@router.get("/dict-items", name="list_dict_items", response_model=ApiResponse[PageOut[ss.DictItemOut]])
def list_dict_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    dict_type: str | None = Query(None, max_length=64),
    keyword: str | None = Query(None, max_length=64),
    is_active: bool | None = Query(None),
    user: User = Depends(_DICT_VIEW),
    db: Session = Depends(get_db),
):
    items, total = DictService(db).list_items(
        page, page_size, dict_type=dict_type, keyword=keyword, is_active=is_active
    )
    return ok({"total": total, "items": [ss.DictItemOut.model_validate(x).model_dump() for x in items]})


@router.post(
    "/dict-items", name="create_dict_item", status_code=201, response_model=ApiResponse[ss.DictItemOut]
)
def create_dict_item(
    payload: ss.DictItemCreate,
    user: User = Depends(_DICT_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ss.DictItemOut.model_validate(DictService(db).create(payload, user.id)).model_dump())


@router.get("/dict-items/{item_id}", name="get_dict_item", response_model=ApiResponse[ss.DictItemOut])
def get_dict_item(item_id: int, user: User = Depends(_DICT_VIEW), db: Session = Depends(get_db)):
    return ok(ss.DictItemOut.model_validate(DictService(db).get(item_id)).model_dump())


@router.put("/dict-items/{item_id}", name="update_dict_item", response_model=ApiResponse[ss.DictItemOut])
def update_dict_item(
    item_id: int,
    payload: ss.DictItemUpdate,
    user: User = Depends(_DICT_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ss.DictItemOut.model_validate(DictService(db).update(item_id, payload)).model_dump())


@router.delete("/dict-items/{item_id}", name="delete_dict_item")
def delete_dict_item(item_id: int, user: User = Depends(_DICT_MANAGE), db: Session = Depends(get_db)):
    DictService(db).delete(item_id)
    return ok(None)


# ---------------- §13.2 scheduled_task_log ----------------
@router.get(
    "/scheduled-task-logs",
    name="list_scheduled_task_logs",
    response_model=ApiResponse[PageOut[ss.ScheduledTaskLogOut]],
)
def list_scheduled_task_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    task_name: str | None = Query(None, max_length=64),
    task_type: str | None = Query(None, max_length=32),
    status: str | None = Query(None, pattern="^(RUNNING|SUCCESS|FAILED|SKIPPED)$"),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    user: User = Depends(_TASK_VIEW),
    db: Session = Depends(get_db),
):
    items, total = ScheduledTaskLogService(db).list(
        page,
        page_size,
        task_name=task_name,
        task_type=task_type,
        status=status,
        start_time=start_time,
        end_time=end_time,
    )
    return ok({
        "total": total,
        "items": [ss.ScheduledTaskLogOut.model_validate(x).model_dump() for x in items],
    })


@router.get(
    "/scheduled-task-logs/{item_id}",
    name="get_scheduled_task_log",
    response_model=ApiResponse[ss.ScheduledTaskLogOut],
)
def get_scheduled_task_log(
    item_id: int,
    user: User = Depends(_TASK_VIEW),
    db: Session = Depends(get_db),
):
    return ok(ss.ScheduledTaskLogOut.model_validate(ScheduledTaskLogService(db).get(item_id)).model_dump())


@router.post(
    "/scheduled-task-logs",
    name="append_scheduled_task_log",
    status_code=201,
    response_model=ApiResponse[ss.ScheduledTaskLogOut],
)
def append_scheduled_task_log(
    payload: ss.TaskLogAppend,
    user: User = Depends(_TASK_MANAGE),
    db: Session = Depends(get_db),
):
    obj = ScheduledTaskLogService(db).append(payload)
    return ok(ss.ScheduledTaskLogOut.model_validate(obj).model_dump())


@router.post(
    "/scheduled-task-logs/{item_id}/finish",
    name="finish_scheduled_task_log",
    response_model=ApiResponse[ss.ScheduledTaskLogOut],
)
def finish_scheduled_task_log(
    item_id: int,
    payload: ss.TaskLogFinish,
    user: User = Depends(_TASK_MANAGE),
    db: Session = Depends(get_db),
):
    obj = ScheduledTaskLogService(db).finish(item_id, payload)
    return ok(ss.ScheduledTaskLogOut.model_validate(obj).model_dump())


# ---------------- §13.3 attachment ----------------
@router.get("/attachments", name="list_attachments", response_model=ApiResponse[PageOut[ss.AttachmentOut]])
def list_attachments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    biz_type: str | None = Query(None, max_length=32),
    biz_id: int | None = Query(None, ge=1),
    user: User = Depends(_ATT_VIEW),
    db: Session = Depends(get_db),
):
    items, total = AttachmentService(db).list(page, page_size, biz_type=biz_type, biz_id=biz_id)
    return ok({"total": total, "items": [ss.AttachmentOut.model_validate(x).model_dump() for x in items]})


@router.post(
    "/attachments", name="upload_attachment", status_code=201, response_model=ApiResponse[ss.AttachmentOut]
)
def upload_attachment(
    file: UploadFile = File(...),
    biz_type: str = Form(..., min_length=1, max_length=32),
    biz_id: int = Form(..., ge=1),
    user: User = Depends(_ATT_MANAGE),
    db: Session = Depends(get_db),
):
    obj = AttachmentService(db).save(file, biz_type=biz_type, biz_id=biz_id, operator_id=user.id)
    return ok(ss.AttachmentOut.model_validate(obj).model_dump())


@router.get("/attachments/{item_id}", name="get_attachment", response_model=ApiResponse[ss.AttachmentOut])
def get_attachment(item_id: int, user: User = Depends(_ATT_VIEW), db: Session = Depends(get_db)):
    return ok(ss.AttachmentOut.model_validate(AttachmentService(db).get(item_id)).model_dump())


@router.get("/attachments/{item_id}/download", name="download_attachment")
def download_attachment(item_id: int, user: User = Depends(_ATT_VIEW), db: Session = Depends(get_db)):
    att, path = AttachmentService(db).resolve(item_id)
    return FileResponse(
        path,
        filename=att.file_name,
        media_type=att.content_type or "application/octet-stream",
    )


@router.delete("/attachments/{item_id}", name="delete_attachment")
def delete_attachment(item_id: int, user: User = Depends(_ATT_MANAGE), db: Session = Depends(get_db)):
    AttachmentService(db).delete(item_id)
    return ok(None)
