"""补货决策 API：策略 CRUD、生成建议、确认/驳回、一键转请购单。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.schema import purchase as ps
from app.schema import replenishment as rs
from app.service.replenishment import ReplenishmentPolicyService, ReplenishmentSuggestionService

router = APIRouter(tags=["补货决策"])

_VIEW = require_perm(Perm.REPLENISHMENT_VIEW)
_MANAGE = require_perm(Perm.REPLENISHMENT_MANAGE)
_CONVERT = require_perm(Perm.REPLENISHMENT_CONVERT)


# ---------------- 补货策略 ----------------
@router.get("/replenishment-policies", name="list_replenishment_policies")
def list_replenishment_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    material_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = ReplenishmentPolicyService(db).list(page, page_size, material_id, warehouse_id, is_active)
    return ok({"total": total, "items": [rs.ReplenishmentPolicyOut.model_validate(x).model_dump() for x in items]})


@router.post("/replenishment-policies", status_code=201, name="create_replenishment_policy")
def create_replenishment_policy(
    payload: rs.ReplenishmentPolicyCreate, user: User = Depends(_MANAGE), db: Session = Depends(get_db)
):
    obj = ReplenishmentPolicyService(db).create(payload, user.id)
    return ok(rs.ReplenishmentPolicyOut.model_validate(obj).model_dump())


@router.get("/replenishment-policies/{policy_id}", name="get_replenishment_policy")
def get_replenishment_policy(policy_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    obj = ReplenishmentPolicyService(db).get(policy_id)
    return ok(rs.ReplenishmentPolicyOut.model_validate(obj).model_dump())


@router.put("/replenishment-policies/{policy_id}", name="update_replenishment_policy")
def update_replenishment_policy(
    policy_id: int,
    payload: rs.ReplenishmentPolicyUpdate,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    obj = ReplenishmentPolicyService(db).update(policy_id, payload)
    return ok(rs.ReplenishmentPolicyOut.model_validate(obj).model_dump())


@router.delete("/replenishment-policies/{policy_id}", name="delete_replenishment_policy")
def delete_replenishment_policy(policy_id: int, user: User = Depends(_MANAGE), db: Session = Depends(get_db)):
    ReplenishmentPolicyService(db).delete(policy_id)
    return ok(None)


# ---------------- 补货建议 ----------------
@router.post("/replenishment-suggestions/generate", name="generate_replenishment_suggestions")
def generate_replenishment_suggestions(
    material_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    result = ReplenishmentSuggestionService(db).generate(user.id, material_id, warehouse_id)
    return ok(rs.GenerateResult.model_validate(result).model_dump())


@router.post("/replenishment-suggestions/convert-batch", name="batch_convert_replenishment_suggestions")
def batch_convert_replenishment_suggestions(
    payload: rs.BatchConvertIn, user: User = Depends(_CONVERT), db: Session = Depends(get_db)
):
    results = ReplenishmentSuggestionService(db).convert_batch(payload.suggestion_ids, user.id)
    return ok([rs.ConvertResult.model_validate(x).model_dump() for x in results])


@router.get("/replenishment-suggestions", name="list_replenishment_suggestions")
def list_replenishment_suggestions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    material_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    trigger_type: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = ReplenishmentSuggestionService(db).list(
        page, page_size, status, material_id, warehouse_id, trigger_type
    )
    return ok({"total": total, "items": [rs.ReplenishmentSuggestionOut.model_validate(x).model_dump() for x in items]})


@router.get("/replenishment-suggestions/{suggestion_id}", name="get_replenishment_suggestion")
def get_replenishment_suggestion(
    suggestion_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)
):
    obj = ReplenishmentSuggestionService(db).get(suggestion_id)
    return ok(rs.ReplenishmentSuggestionOut.model_validate(obj).model_dump())


@router.post("/replenishment-suggestions/{suggestion_id}/confirm", name="confirm_replenishment_suggestion")
def confirm_replenishment_suggestion(
    suggestion_id: int,
    payload: rs.SuggestionConfirmIn,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    obj = ReplenishmentSuggestionService(db).confirm(suggestion_id, payload, user.id)
    return ok(rs.ReplenishmentSuggestionOut.model_validate(obj).model_dump())


@router.post("/replenishment-suggestions/{suggestion_id}/reject", name="reject_replenishment_suggestion")
def reject_replenishment_suggestion(
    suggestion_id: int,
    payload: rs.SuggestionRejectIn,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    obj = ReplenishmentSuggestionService(db).reject(suggestion_id, payload, user.id)
    return ok(rs.ReplenishmentSuggestionOut.model_validate(obj).model_dump())


@router.post("/replenishment-suggestions/{suggestion_id}/convert", name="convert_replenishment_suggestion")
def convert_replenishment_suggestion(
    suggestion_id: int, user: User = Depends(_CONVERT), db: Session = Depends(get_db)
):
    suggestion, pr = ReplenishmentSuggestionService(db).convert(suggestion_id, user.id)
    return ok(
        {
            "suggestion": rs.ReplenishmentSuggestionOut.model_validate(suggestion).model_dump(),
            "pr": ps.PROut.model_validate(pr).model_dump(),
        }
    )
