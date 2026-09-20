"""系统 API：操作日志只读查询。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.schema import operation_log as os
from app.schema.common import ApiResponse, PageOut
from app.service.operation_log import OperationLogService

router = APIRouter(tags=["系统"])

_VIEW = require_perm(Perm.OPERATION_VIEW)


@router.get("/operation-logs", name="list_operation_logs", response_model=ApiResponse[PageOut[os.OperationLogOut]])
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: int | None = Query(None),
    module: str | None = Query(None, max_length=32),
    action: str | None = Query(None, max_length=64),
    result: str | None = Query(None, pattern="^(SUCCESS|FAIL)$"),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = OperationLogService(db).list(
        page,
        page_size,
        user_id=user_id,
        module=module,
        action=action,
        result=result,
        start_time=start_time,
        end_time=end_time,
    )
    return ok({"total": total, "items": [os.OperationLogOut.model_validate(x).model_dump() for x in items]})
