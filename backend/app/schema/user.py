from pydantic import BaseModel, ConfigDict, Field


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    real_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    dept_name: str | None = Field(default=None, max_length=64)
    role_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    real_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    dept_name: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, pattern="^(ACTIVE|DISABLED|LOCKED)$")


class AssignRolesIn(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str | None
    phone: str | None
    email: str | None
    dept_name: str | None
    status: str
    is_superuser: bool
    roles: list[RoleBrief] = Field(default_factory=list)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    is_builtin: bool
    status: str


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: str
    path: str | None
