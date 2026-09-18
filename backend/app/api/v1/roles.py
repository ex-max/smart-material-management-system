from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.repository.user import PermissionRepository, RoleRepository
from app.schema.user import PermissionOut, RoleOut

router = APIRouter(tags=["角色与权限"])


@router.get("/roles")
def list_roles(
    user: User = Depends(require_perm(Perm.ROLE_VIEW)),
    db: Session = Depends(get_db),
):
    rows = RoleRepository(db).list_roles()
    return ok([RoleOut.model_validate(r).model_dump() for r in rows])


@router.get("/permissions")
def list_permissions(
    user: User = Depends(require_perm(Perm.ROLE_VIEW)),
    db: Session = Depends(get_db),
):
    rows = PermissionRepository(db).list_permissions()
    return ok([PermissionOut.model_validate(p).model_dump() for p in rows])
