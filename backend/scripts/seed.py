"""初始化 RBAC 参考数据与管理员账号。

用法（在 backend/ 下）：.venv/bin/python scripts/seed.py
幂等：已存在的权限/角色/用户不会重复插入。
"""

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.dictionaries import DICT_SEED
from app.core.permissions import PERMISSION_SEED, ROLE_ADMIN, ROLE_ADMIN_NAME
from app.core.security import hash_password
from app.model.system import Dict
from app.model.user import Permission, Role, RolePermission, User, UserRole


def main() -> None:
    settings = get_settings()
    db = get_session_factory()()
    try:
        existing = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
        for code, name, perm_type, sort_no in PERMISSION_SEED:
            if code not in existing:
                perm = Permission(code=code, name=name, type=perm_type, sort_no=sort_no)
                db.add(perm)
                db.flush()
                existing[code] = perm

        role = db.execute(select(Role).where(Role.code == ROLE_ADMIN)).scalar_one_or_none()
        if role is None:
            role = Role(code=ROLE_ADMIN, name=ROLE_ADMIN_NAME, is_builtin=True)
            db.add(role)
            db.flush()

        granted = {
            rp.permission_id
            for rp in db.execute(select(RolePermission).where(RolePermission.role_id == role.id)).scalars().all()
        }
        for perm in existing.values():
            if perm.id not in granted:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))

        user = db.execute(
            select(User).where(User.username == settings.admin_username)
        ).scalar_one_or_none()
        if user is None:
            user = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                real_name="系统管理员",
                is_superuser=True,
                status="ACTIVE",
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))

        # 数据字典预置（展示型；按 (dict_type, dict_key) 幂等，已存在不改）
        existing_dict = {
            (d.dict_type, d.dict_key) for d in db.execute(select(Dict)).scalars().all()
        }
        dict_added = 0
        for dict_type, dict_key, dict_label, sort_no in DICT_SEED:
            if (dict_type, dict_key) not in existing_dict:
                db.add(Dict(dict_type=dict_type, dict_key=dict_key, dict_label=dict_label, sort_no=sort_no))
                dict_added += 1

        db.commit()
        print(
            "seed ok: permissions=%d dict=%d(+%d) role=%s admin=%s"
            % (len(existing), len(existing_dict) + dict_added, dict_added, ROLE_ADMIN, settings.admin_username)
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
