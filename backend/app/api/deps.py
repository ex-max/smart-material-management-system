import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_token
from app.model.user import User
from app.repository.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise Unauthorized()
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise Unauthorized("凭证无效或已过期") from exc
    raw_sub = payload.get("sub")
    if raw_sub is None:
        raise Unauthorized("凭证缺少主体")
    user = UserRepository(db).get(int(raw_sub))
    if user is None or user.deleted_at is not None:
        raise Unauthorized("用户不存在")
    # 供审计中间件读取操作人（best-effort；匿名请求不设置）
    request.state.current_user = {"id": user.id, "username": user.username}
    return user


def require_perm(code: str):
    def _dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.is_superuser:
            return user
        if code not in UserRepository(db).permission_codes(user.id):
            raise Forbidden("缺少权限 " + code)
        return user

    return _dependency
