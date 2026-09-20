import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, configure_bind, get_db, reset_engine
from app.core.permissions import Perm
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.model.user import Permission, Role, RolePermission, User, UserRole

TEST_DATABASE_URL = os.environ.get("ERP_TEST_DATABASE_URL")


@pytest.fixture()
def db_session():
    if TEST_DATABASE_URL:
        # 可选：对着真实 PostgreSQL 跑（ERP_TEST_DATABASE_URL=postgresql+psycopg://...）
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    else:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # 审计中间件用独立 session 落库：绑定到同一测试库，测试方可断言日志
    configure_bind(engine, factory)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
        reset_engine()


@pytest.fixture()
def client(db_session):
    def _override():
        # 与生产一致：请求结束回滚未提交改动（成功路径已在 service 内 commit）
        try:
            yield db_session
        finally:
            db_session.rollback()

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


def login_headers(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["data"]["access_token"]}


@pytest.fixture()
def login(client):
    def _login(username, password):
        return login_headers(client, username, password)

    return _login


@pytest.fixture()
def purchase_users(db_session, seeded):
    db_session.add_all(
        [
            Permission(code=Perm.PURCHASE_VIEW, name="查看采购", type="API", sort_no=40),
            Permission(code=Perm.PURCHASE_APPROVE, name="审批采购", type="API", sort_no=41),
            Permission(code=Perm.PURCHASE_MANAGE, name="管理采购", type="API", sort_no=42),
        ]
    )
    db_session.flush()
    perms = {p.code: p for p in db_session.query(Permission).all()}

    viewer_role = Role(code="P_VIEW", name="采购查看")
    buyer_role = Role(code="P_BUYER", name="采购员")
    approver_role = Role(code="P_APPROVER", name="采购审批")
    db_session.add_all([viewer_role, buyer_role, approver_role])
    db_session.flush()
    db_session.add_all(
        [
            RolePermission(role_id=viewer_role.id, permission_id=perms[Perm.PURCHASE_VIEW].id),
            RolePermission(role_id=buyer_role.id, permission_id=perms[Perm.PURCHASE_VIEW].id),
            RolePermission(role_id=buyer_role.id, permission_id=perms[Perm.PURCHASE_MANAGE].id),
            RolePermission(role_id=approver_role.id, permission_id=perms[Perm.PURCHASE_VIEW].id),
            RolePermission(role_id=approver_role.id, permission_id=perms[Perm.PURCHASE_APPROVE].id),
        ]
    )
    accounts = [
        ("pviewer", viewer_role, "pviewer123"),
        ("buyer", buyer_role, "buyer123"),
        ("approver", approver_role, "approver123"),
    ]
    for username, role, password in accounts:
        user = User(username=username, password_hash=hash_password(password), real_name=username, status="ACTIVE")
        db_session.add(user)
        db_session.flush()
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    return {u: p for u, _, p in accounts}


@pytest.fixture()
def inventory_users(db_session, purchase_users):
    db_session.add_all(
        [
            Permission(code=Perm.INVENTORY_VIEW, name="查看库存", type="API", sort_no=50),
            Permission(code=Perm.INVENTORY_MANAGE, name="库存作业", type="API", sort_no=51),
        ]
    )
    db_session.flush()
    perms = {p.code: p for p in db_session.query(Permission).all()}

    viewer_role = Role(code="I_VIEW", name="库存查看")
    manager_role = Role(code="I_MANAGER", name="库存管理")
    db_session.add_all([viewer_role, manager_role])
    db_session.flush()
    db_session.add_all(
        [
            RolePermission(role_id=viewer_role.id, permission_id=perms[Perm.INVENTORY_VIEW].id),
            RolePermission(role_id=manager_role.id, permission_id=perms[Perm.INVENTORY_VIEW].id),
            RolePermission(role_id=manager_role.id, permission_id=perms[Perm.INVENTORY_MANAGE].id),
        ]
    )
    accounts = [("iviewer", viewer_role, "iviewer123"), ("imanager", manager_role, "imanager123")]
    for username, role, password in accounts:
        user = User(username=username, password_hash=hash_password(password), real_name=username, status="ACTIVE")
        db_session.add(user)
        db_session.flush()
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    return {u: p for u, _, p in accounts}


@pytest.fixture()
def replenishment_users(db_session, seeded):
    db_session.add_all(
        [
            Permission(code=Perm.FORECAST_VIEW, name="查看预测", type="API", sort_no=60),
            Permission(code=Perm.FORECAST_MANAGE, name="管理预测", type="API", sort_no=61),
            Permission(code=Perm.REPLENISHMENT_VIEW, name="查看补货建议", type="API", sort_no=70),
            Permission(code=Perm.REPLENISHMENT_MANAGE, name="管理补货建议", type="API", sort_no=71),
            Permission(code=Perm.REPLENISHMENT_CONVERT, name="补货建议转请购单", type="API", sort_no=72),
        ]
    )
    db_session.flush()
    perms = {p.code: p for p in db_session.query(Permission).all()}

    viewer_role = Role(code="R_VIEW", name="补货查看")
    manager_role = Role(code="R_MANAGE", name="补货管理")
    converter_role = Role(code="R_CONVERT", name="补货转单")
    db_session.add_all([viewer_role, manager_role, converter_role])
    db_session.flush()
    db_session.add_all(
        [
            RolePermission(role_id=viewer_role.id, permission_id=perms[Perm.REPLENISHMENT_VIEW].id),
            RolePermission(role_id=manager_role.id, permission_id=perms[Perm.REPLENISHMENT_VIEW].id),
            RolePermission(role_id=manager_role.id, permission_id=perms[Perm.REPLENISHMENT_MANAGE].id),
            RolePermission(role_id=converter_role.id, permission_id=perms[Perm.REPLENISHMENT_VIEW].id),
            RolePermission(role_id=converter_role.id, permission_id=perms[Perm.REPLENISHMENT_MANAGE].id),
            RolePermission(role_id=converter_role.id, permission_id=perms[Perm.REPLENISHMENT_CONVERT].id),
        ]
    )
    accounts = [
        ("rviewer", viewer_role, "rviewer123"),
        ("rmanager", manager_role, "rmanager123"),
        ("rconverter", converter_role, "rconverter123"),
    ]
    for username, role, password in accounts:
        user = User(username=username, password_hash=hash_password(password), real_name=username, status="ACTIVE")
        db_session.add(user)
        db_session.flush()
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    return {u: p for u, _, p in accounts}


@pytest.fixture()
def procurement_master(client, seeded):
    admin = login_headers(client, "admin", "admin123")
    category = client.post("/api/v1/material-categories", headers=admin, json={"code": "C1", "name": "五金"}).json()["data"]
    unit = client.post("/api/v1/units", headers=admin, json={"code": "PCS", "name": "个"}).json()["data"]
    supplier = client.post("/api/v1/suppliers", headers=admin, json={"code": "S1", "name": "供应商甲"}).json()["data"]
    warehouse = client.post("/api/v1/warehouses", headers=admin, json={"code": "WH01", "name": "主仓"}).json()["data"]
    material = client.post(
        "/api/v1/materials",
        headers=admin,
        json={"code": "M1", "name": "螺丝", "category_id": category["id"], "unit_id": unit["id"]},
    ).json()["data"]
    batch_material = client.post(
        "/api/v1/materials",
        headers=admin,
        json={
            "code": "M2",
            "name": "疫苗",
            "category_id": category["id"],
            "unit_id": unit["id"],
            "is_batch_managed": True,
            "shelf_life_days": 365,
        },
    ).json()["data"]
    return {
        "admin": admin,
        "supplier_id": supplier["id"],
        "warehouse_id": warehouse["id"],
        "material_id": material["id"],
        "batch_material_id": batch_material["id"],
    }

