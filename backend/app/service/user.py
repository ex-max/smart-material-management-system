from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_password
from app.model.user import User, UserRole
from app.repository.user import RoleRepository, UserRepository
from app.schema.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)

    def list_users(self, page: int, page_size: int) -> tuple[list[User], int]:
        offset = (page - 1) * page_size
        return self.users.list_users(offset, page_size)

    def get(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None or user.deleted_at is not None:
            raise NotFound("用户不存在")
        return user

    def create(self, payload: UserCreate, operator_id: int | None = None) -> User:
        if self.users.get_by_username(payload.username) is not None:
            raise Conflict("用户名已存在")
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            real_name=payload.real_name,
            phone=payload.phone,
            email=payload.email,
            dept_name=payload.dept_name,
            status="ACTIVE",
            is_superuser=False,
            created_by=operator_id,
        )
        self.users.add(user)
        self._sync_roles(user, payload.role_ids)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id: int, payload: UserUpdate, operator_id: int | None = None) -> User:
        user = self.get(user_id)
        for field in ("real_name", "phone", "email", "dept_name", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(user, field, value)
        user.created_by = user.created_by or operator_id
        self.db.commit()
        self.db.refresh(user)
        return user

    def assign_roles(self, user_id: int, role_ids: list[int]) -> User:
        user = self.get(user_id)
        self._sync_roles(user, role_ids)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _sync_roles(self, user: User, role_ids: list[int]) -> None:
        if not role_ids:
            return
        found = [self.roles.get(rid) for rid in role_ids]
        if any(r is None for r in found):
            raise BadRequest("存在无效的角色 id")
        existing = {ur.role_id for ur in self.db.query(UserRole).filter(UserRole.user_id == user.id).all()}
        for rid in role_ids:
            if rid not in existing:
                self.db.add(UserRole(user_id=user.id, role_id=rid))
