from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Forbidden
from app.core.security import create_access_token, verify_password
from app.model.user import User
from app.repository.user import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def login(self, username: str, password: str, ip: str | None = None) -> tuple[User, str, int]:
        user = self.users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise BadRequest("用户名或口令不正确")
        if user.status != "ACTIVE":
            raise Forbidden("账号已停用或锁定")
        token, expires_in = create_access_token(str(user.id))
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = ip
        self.db.commit()
        return user, token, expires_in
