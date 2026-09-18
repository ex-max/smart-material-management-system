from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.model.base import PK, AuditMixin

# jsonb 在 PostgreSQL 上启用；SQLite（测试）退化为基础 JSON
JsonType = JSON().with_variant(JSONB, "postgresql")


class User(Base, AuditMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    avatar: Mapped[str | None] = mapped_column(String(255))
    dept_name: Mapped[str | None] = mapped_column(String(64))
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(String(45))
    pwd_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_role",
        primaryjoin="User.id == UserRole.user_id",
        secondaryjoin="Role.id == UserRole.role_id",
        lazy="selectin",
    )

    __table_args__ = (
        Index("uq_users_username", "username", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("status IN ('ACTIVE','DISABLED','LOCKED')", name="ck_users_status"),
        Index("ix_users_status", "status"),
    )


class Role(Base, AuditMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permission",
        primaryjoin="Role.id == RolePermission.role_id",
        secondaryjoin="Permission.id == RolePermission.permission_id",
        lazy="selectin",
    )

    __table_args__ = (
        Index("uq_roles_code", "code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_roles_status"),
    )


class Permission(Base, AuditMixin):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("permissions.id"))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str | None] = mapped_column(String(8))
    path: Mapped[str | None] = mapped_column(String(255))
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("uq_permissions_code", "code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("type IN ('MENU','API','BUTTON','DATA')", name="ck_permissions_type"),
        Index("ix_permissions_parent_id", "parent_id"),
        Index("ix_permissions_type", "type"),
    )


class UserRole(Base, AuditMixin):
    __tablename__ = "user_role"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("uq_user_role", "user_id", "role_id", unique=True),
        Index("ix_user_role_role_id", "role_id"),
    )


class RolePermission(Base, AuditMixin):
    __tablename__ = "role_permission"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        Index("uq_role_permission", "role_id", "permission_id", unique=True),
        Index("ix_role_permission_permission_id", "permission_id"),
    )


class OperationLog(Base):
    """操作日志：追加写、不更新、不软删（§10.6 例外）。"""

    __tablename__ = "operation_log"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    username: Mapped[str | None] = mapped_column(String(64))
    module: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str | None] = mapped_column(String(8))
    path: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    request_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(16), default="SUCCESS", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(16))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("result IN ('SUCCESS','FAIL')", name="ck_operation_log_result"),
        Index("ix_operation_log_created_at", "created_at"),
        Index("ix_operation_log_user_id", "user_id"),
        Index("ix_operation_log_action", "action"),
        Index("ix_operation_log_request_id", "request_id"),
    )
