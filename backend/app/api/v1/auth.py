from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.model.user import User
from app.repository.user import PermissionRepository, UserRepository
from app.schema.auth import LoginRequest, LoginResult
from app.schema.common import ApiResponse
from app.schema.user import CurrentUserOut, UserOut
from app.service.auth import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


def _current_user_out(db: Session, user: User) -> dict:
    """序列化当前用户：超管返回全部权限码，其余返回其角色的权限并集（供前端按钮级鉴权）。"""
    base = UserOut.model_validate(user).model_dump()
    if user.is_superuser:
        permissions = sorted(p.code for p in PermissionRepository(db).list_permissions())
    else:
        permissions = sorted(UserRepository(db).permission_codes(user.id))
    return CurrentUserOut(**base, permissions=permissions).model_dump()


@router.post("/login", response_model=ApiResponse[LoginResult])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    user, token, expires_in = AuthService(db).login(payload.username, payload.password, ip)
    request.state.current_user = {"id": user.id, "username": user.username}
    data = {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": _current_user_out(db, user),
    }
    return ok(data)


@router.get("/me", response_model=ApiResponse[CurrentUserOut])
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_current_user_out(db, user))
