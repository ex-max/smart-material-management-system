import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.model.user import Permission, Role, RolePermission, User, UserRole


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def seeded(db_session):
    view_perm = Permission(code="user:view", name="查看用户", type="API", sort_no=10)
    create_perm = Permission(code="user:create", name="新建用户", type="API", sort_no=11)
    db_session.add_all([view_perm, create_perm])
    db_session.flush()

    viewer_role = Role(code="VIEWER", name="查看者")
    db_session.add(viewer_role)
    db_session.flush()
    db_session.add(RolePermission(role_id=viewer_role.id, permission_id=view_perm.id))

    admin = User(
        username="admin",
        password_hash=hash_password("admin123"),
        real_name="管理员",
        is_superuser=True,
        status="ACTIVE",
    )
    viewer = User(
        username="viewer",
        password_hash=hash_password("viewer123"),
        real_name="查看者",
        status="ACTIVE",
    )
    db_session.add_all([admin, viewer])
    db_session.flush()
    db_session.add(UserRole(user_id=viewer.id, role_id=viewer_role.id))
    db_session.commit()
    return {"admin_id": admin.id, "viewer_id": viewer.id}
