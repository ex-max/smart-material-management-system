from sqlalchemy import func, or_, select

from app.model.base import utcnow
from app.model.user import Permission, Role, RolePermission, User, UserRole


class UserRepository:
    def __init__(self, db) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_users(self, offset: int, limit: int, keyword: str | None = None) -> tuple[list[User], int]:
        base = select(User).where(User.deleted_at.is_(None))
        if keyword:
            like = f"%{keyword}%"
            base = base.where(or_(User.username.like(like), User.real_name.like(like)))
        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        rows = self.db.execute(base.order_by(User.id).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def permission_codes(self, user_id: int) -> set[str]:
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return set(self.db.execute(stmt).scalars().all())


class RoleRepository:
    def __init__(self, db) -> None:
        self.db = db

    def get(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id)

    def get_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code, Role.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_roles(self) -> list[Role]:
        stmt = select(Role).where(Role.deleted_at.is_(None)).order_by(Role.sort_no, Role.id)
        return list(self.db.execute(stmt).scalars().all())

    def add(self, role: Role) -> Role:
        self.db.add(role)
        self.db.flush()
        return role

    def save(self, role: Role) -> Role:
        self.db.flush()
        return role

    def soft_delete(self, role_id: int) -> None:
        role = self.get(role_id)
        if role is None:
            return
        role.deleted_at = utcnow()
        # 软删后其用户关联与权限关联一并清理，避免残留影响权限并集
        self.db.query(UserRole).filter(UserRole.role_id == role_id).delete()
        self.db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

    def permission_ids(self, role_id: int) -> list[int]:
        stmt = select(RolePermission.permission_id).where(RolePermission.role_id == role_id)
        return list(self.db.execute(stmt).scalars().all())

    def replace_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        self.db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        for pid in permission_ids:
            self.db.add(RolePermission(role_id=role_id, permission_id=pid))


class PermissionRepository:
    def __init__(self, db) -> None:
        self.db = db

    def list_permissions(self) -> list[Permission]:
        stmt = select(Permission).where(Permission.deleted_at.is_(None)).order_by(Permission.sort_no, Permission.id)
        return list(self.db.execute(stmt).scalars().all())
