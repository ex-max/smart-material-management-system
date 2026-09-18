from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.schema.user import AssignRolesIn, UserCreate, UserOut, UserUpdate
from app.service.user import UserService

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: User = Depends(require_perm(Perm.USER_VIEW)),
    db: Session = Depends(get_db),
):
    items, total = UserService(db).list_users(page, page_size)
    return ok({"total": total, "items": [UserOut.model_validate(x).model_dump() for x in items]})


@router.post("", status_code=201)
def create_user(
    payload: UserCreate,
    user: User = Depends(require_perm(Perm.USER_CREATE)),
    db: Session = Depends(get_db),
):
    created = UserService(db).create(payload, user.id)
    return ok(UserOut.model_validate(created).model_dump())


@router.get("/{user_id}")
def get_user(
    user_id: int,
    user: User = Depends(require_perm(Perm.USER_VIEW)),
    db: Session = Depends(get_db),
):
    return ok(UserOut.model_validate(UserService(db).get(user_id)).model_dump())


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    user: User = Depends(require_perm(Perm.USER_UPDATE)),
    db: Session = Depends(get_db),
):
    updated = UserService(db).update(user_id, payload, user.id)
    return ok(UserOut.model_validate(updated).model_dump())


@router.post("/{user_id}/roles")
def assign_roles(
    user_id: int,
    payload: AssignRolesIn,
    user: User = Depends(require_perm(Perm.USER_UPDATE)),
    db: Session = Depends(get_db),
):
    updated = UserService(db).assign_roles(user_id, payload.role_ids)
    return ok(UserOut.model_validate(updated).model_dump())
