"""角色业务：CRUD + 权限分配（builtin 保护、权限存在性校验）。"""

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.model.user import Permission, Role
from app.repository.user import PermissionRepository, RoleRepository
from app.schema.user import RoleCreate, RolePermissionAssignIn, RoleUpdate


class RoleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.roles = RoleRepository(db)
        self.permissions = PermissionRepository(db)

    def list_roles(self) -> list[Role]:
        return self.roles.list_roles()

    def get(self, role_id: int) -> Role:
        role = self.roles.get(role_id)
        if role is None or role.deleted_at is not None:
            raise NotFound("角色不存在")
        return role

    def create(self, payload: RoleCreate, operator_id: int | None = None) -> Role:
        if self.roles.get_by_code(payload.code) is not None:
            raise Conflict("角色编码已存在")
        role = Role(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            sort_no=payload.sort_no,
            status=payload.status,
            is_builtin=False,
            created_by=operator_id,
        )
        self.roles.add(role)
        if payload.permission_ids:
            self.roles.replace_permissions(role.id, self._validate_permission_ids(payload.permission_ids))
        self.db.commit()
        self.db.refresh(role)
        return role

    def update(self, role_id: int, payload: RoleUpdate, operator_id: int | None = None) -> Role:
        role = self.get(role_id)
        # builtin 角色（如 ADMIN）：禁止改 code（schema 无 code 字段，天然保护）；状态不允许停用
        if payload.status == "INACTIVE" and role.is_builtin:
            raise BadRequest("内置角色不允许停用")
        for field in ("name", "description", "sort_no", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(role, field, value)
        role.created_by = role.created_by or operator_id
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete(self, role_id: int) -> None:
        role = self.get(role_id)
        if role.is_builtin:
            raise BadRequest("内置角色不允许删除")
        self.roles.soft_delete(role_id)
        self.db.commit()

    def assign_permissions(self, role_id: int, payload: RolePermissionAssignIn) -> list[int]:
        role = self.get(role_id)
        self.roles.replace_permissions(role.id, self._validate_permission_ids(payload.permission_ids))
        self.db.commit()
        return self.roles.permission_ids(role.id)

    def permission_ids(self, role_id: int) -> list[int]:
        self.get(role_id)
        return self.roles.permission_ids(role_id)

    def _validate_permission_ids(self, permission_ids: list[int]) -> list[int]:
        if not permission_ids:
            return []
        existing: dict[int, Permission] = {p.id: p for p in self.permissions.list_permissions()}
        bad = [pid for pid in permission_ids if pid not in existing]
        if bad:
            raise BadRequest("存在无效的权限 id")
        return sorted(set(permission_ids))
