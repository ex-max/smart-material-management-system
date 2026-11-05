from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.repository.user import PermissionRepository
from app.schema.common import ApiResponse
from app.schema.user import (
    PermissionOut,
    RoleCreate,
    RoleOut,
    RolePermissionAssignIn,
    RoleUpdate,
)
from app.service.role import RoleService

router = APIRouter(tags=["角色与权限"])

_VIEW = require_perm(Perm.ROLE_VIEW)
_MANAGE = require_perm(Perm.ROLE_MANAGE)


@router.get("/roles", response_model=ApiResponse[list[RoleOut]])
def list_roles(
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    rows = RoleService(db).list_roles()
    return ok([RoleOut.model_validate(r).model_dump() for r in rows])


@router.post("/roles", status_code=201, response_model=ApiResponse[RoleOut])
def create_role(
    payload: RoleCreate,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    created = RoleService(db).create(payload, user.id)
    return ok(RoleOut.model_validate(created).model_dump())


@router.get("/roles/{role_id}", response_model=ApiResponse[RoleOut])
def get_role(
    role_id: int,
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    return ok(RoleOut.model_validate(RoleService(db).get(role_id)).model_dump())


@router.put("/roles/{role_id}", response_model=ApiResponse[RoleOut])
def update_role(
    role_id: int,
    payload: RoleUpdate,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    updated = RoleService(db).update(role_id, payload, user.id)
    return ok(RoleOut.model_validate(updated).model_dump())


@router.delete("/roles/{role_id}", response_model=ApiResponse[None])
def delete_role(
    role_id: int,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    RoleService(db).delete(role_id)
    return ok(None)


@router.put("/roles/{role_id}/permissions", response_model=ApiResponse[list[int]])
def assign_role_permissions(
    role_id: int,
    payload: RolePermissionAssignIn,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    ids = RoleService(db).assign_permissions(role_id, payload)
    return ok(ids)


@router.get("/roles/{role_id}/permissions", response_model=ApiResponse[list[int]])
def get_role_permissions(
    role_id: int,
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    return ok(RoleService(db).permission_ids(role_id))


@router.get("/permissions", response_model=ApiResponse[list[PermissionOut]])
def list_permissions(
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    rows = PermissionRepository(db).list_permissions()
    return ok([PermissionOut.model_validate(p).model_dump() for p in rows])
