from sqlalchemy import func, select

from app.model.user import Permission, Role, RolePermission, User, UserRole


class UserRepository:
    def __init__(self, db) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_users(self, offset: int, limit: int) -> tuple[list[User], int]:
        base = select(User).where(User.deleted_at.is_(None))
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


class PermissionRepository:
    def __init__(self, db) -> None:
        self.db = db

    def list_permissions(self) -> list[Permission]:
        stmt = select(Permission).where(Permission.deleted_at.is_(None)).order_by(Permission.sort_no, Permission.id)
        return list(self.db.execute(stmt).scalars().all())
