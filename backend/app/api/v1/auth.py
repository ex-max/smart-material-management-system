from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.model.user import User
from app.schema.auth import LoginRequest, LoginResult
from app.schema.common import ApiResponse
from app.schema.user import UserOut
from app.service.auth import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=ApiResponse[LoginResult])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    user, token, expires_in = AuthService(db).login(payload.username, payload.password, ip)
    data = {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": UserOut.model_validate(user).model_dump(),
    }
    return ok(data)


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: User = Depends(get_current_user)):
    return ok(UserOut.model_validate(user).model_dump())
