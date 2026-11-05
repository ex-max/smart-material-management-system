"""P3 RBAC：角色 CRUD / 保存权限 / 重置密码 / 分配角色（正常 / 边界 / 权限拒绝）。"""

import pytest

from app.model.user import Permission, Role, RolePermission

API = "/api/v1"


@pytest.fixture()
def role_perms(db_session, seeded):
    """追加 role:view / role:manage 权限，并给 viewer 授 role:view（可读不可写）。

    复用 conftest seeded 已建的 VIEWER 角色（code=VIEWER，含 user:view）。
    """
    rview = Permission(code="role:view", name="查看角色", type="API", sort_no=20)
    rmanage = Permission(code="role:manage", name="管理角色", type="API", sort_no=21)
    db_session.add_all([rview, rmanage])
    db_session.flush()
    viewer_role = db_session.query(Role).filter(Role.code == "VIEWER").one()
    # viewer→VIEWER 关联已在 conftest seeded 建立，这里只补充 role:view 权限
    db_session.add(RolePermission(role_id=viewer_role.id, permission_id=rview.id))
    db_session.commit()
    return {"rview": rview, "rmanage": rmanage}


def _h(client, username, password):
    r = client.post(API + "/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["data"]["access_token"]}


def test_admin_create_role(client, role_perms):
    token = _h(client, "admin", "admin123")
    resp = client.post(API + "/roles", headers=token, json={
        "code": "SALES", "name": "销售员", "description": "销售", "sort_no": 5,
        "permission_ids": [role_perms["rview"].id],
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["code"] == "SALES"
    assert not data["is_builtin"]


def test_role_code_conflict(client, role_perms):
    token = _h(client, "admin", "admin123")
    first = client.post(API + "/roles", headers=token, json={"code": "DUPE", "name": "重复"})
    assert first.status_code == 201, first.text
    second = client.post(API + "/roles", headers=token, json={"code": "DUPE", "name": "重复2"})
    assert second.status_code == 409
    assert second.json()["code"] == 10409


def test_role_crud_roundtrip(client, role_perms):
    token = _h(client, "admin", "admin123")
    created = client.post(API + "/roles", headers=token, json={"code": "OPS", "name": "运营"}).json()["data"]
    rid = created["id"]
    listed = client.get(API + "/roles", headers=token)
    assert listed.status_code == 200
    assert any(r["code"] == "OPS" for r in listed.json()["data"])
    got = client.get(API + f"/roles/{rid}", headers=token)
    assert got.json()["data"]["name"] == "运营"
    updated = client.put(API + f"/roles/{rid}", headers=token, json={"name": "运营部", "sort_no": 9})
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "运营部"
    assert updated.json()["data"]["sort_no"] == 9
    deleted = client.delete(API + f"/roles/{rid}", headers=token)
    assert deleted.status_code == 200
    gone = client.get(API + f"/roles/{rid}", headers=token)
    assert gone.status_code == 404


def test_builtin_role_not_deletable(client, role_perms, db_session):
    token = _h(client, "admin", "admin123")
    admin_role = Role(code="SYSADMIN", name="系统内置", is_builtin=True)
    db_session.add(admin_role)
    db_session.flush()
    db_session.commit()
    resp = client.delete(API + f"/roles/{admin_role.id}", headers=token)
    assert resp.status_code == 400
    assert resp.json()["code"] == 10001


def test_builtin_role_cannot_inactivate(client, role_perms, db_session):
    token = _h(client, "admin", "admin123")
    admin_role = Role(code="SYSADMIN2", name="系统内置2", is_builtin=True)
    db_session.add(admin_role)
    db_session.flush()
    db_session.commit()
    resp = client.put(API + f"/roles/{admin_role.id}", headers=token, json={"status": "INACTIVE"})
    assert resp.status_code == 400


def test_assign_role_permissions(client, role_perms):
    token = _h(client, "admin", "admin123")
    created = client.post(API + "/roles", headers=token, json={"code": "PERM", "name": "权限测试"}).json()["data"]
    rid = created["id"]
    saved = client.put(API + f"/roles/{rid}/permissions", headers=token,
                       json={"permission_ids": [role_perms["rview"].id, role_perms["rmanage"].id]})
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["data"]) == 2
    read = client.get(API + f"/roles/{rid}/permissions", headers=token)
    assert sorted(read.json()["data"]) == sorted([role_perms["rview"].id, role_perms["rmanage"].id])
    # 全量替换：传空清空
    cleared = client.put(API + f"/roles/{rid}/permissions", headers=token, json={"permission_ids": []})
    assert cleared.json()["data"] == []


def test_assign_permissions_invalid_id(client, role_perms):
    token = _h(client, "admin", "admin123")
    created = client.post(API + "/roles", headers=token, json={"code": "BADP", "name": "坏权限"}).json()["data"]
    resp = client.put(API + f"/roles/{created['id']}/permissions", headers=token, json={"permission_ids": [999999]})
    assert resp.status_code == 400


def test_roles_endpoint_permission_denied(client, role_perms):
    token = _h(client, "viewer", "viewer123")
    # viewer 有 role:view：可读列表
    listed = client.get(API + "/roles", headers=token)
    assert listed.status_code == 200
    # 但无 role:manage：写操作 403
    denied = client.post(API + "/roles", headers=token, json={"code": "X", "name": "x"})
    assert denied.status_code == 403
    assert denied.json()["code"] == 10403


def test_roles_endpoint_requires_auth(client, role_perms):
    assert client.get(API + "/roles").status_code == 401
    assert client.get(API + "/permissions").status_code == 401


def test_reset_password(client, seeded):
    token = _h(client, "admin", "admin123")
    resp = client.post(API + f"/users/{seeded['viewer_id']}/reset-password",
                       headers=token, json={"password": "newpass99"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == seeded["viewer_id"]
    login = client.post(API + "/auth/login", json={"username": "viewer", "password": "newpass99"})
    assert login.status_code == 200
    old = client.post(API + "/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert old.status_code == 400
    assert old.json()["code"] != 0


def test_reset_password_perm_denied(client, seeded):
    # viewer 只有 user:view（conftest seeded），无 user:update → 403
    token = _h(client, "viewer", "viewer123")
    resp = client.post(API + f"/users/{seeded['viewer_id']}/reset-password",
                       headers=token, json={"password": "whatever1"})
    assert resp.status_code == 403
    assert resp.json()["code"] == 10403


def test_assign_roles_roundtrip(client, role_perms, seeded):
    token = _h(client, "admin", "admin123")
    r1 = client.post(API + "/roles", headers=token, json={"code": "R1", "name": "角色一"}).json()["data"]
    r2 = client.post(API + "/roles", headers=token, json={"code": "R2", "name": "角色二"}).json()["data"]
    resp = client.post(API + f"/users/{seeded['viewer_id']}/roles", headers=token,
                       json={"role_ids": [r1["id"], r2["id"]]})
    assert resp.status_code == 200, resp.text
    codes = {r["code"] for r in resp.json()["data"]["roles"]}
    assert codes == {"R1", "R2"}
    # 全量替换：只留一个
    resp2 = client.post(API + f"/users/{seeded['viewer_id']}/roles", headers=token,
                        json={"role_ids": [r1["id"]]})
    codes2 = {r["code"] for r in resp2.json()["data"]["roles"]}
    assert codes2 == {"R1"}
    # 空列表清空
    resp3 = client.post(API + f"/users/{seeded['viewer_id']}/roles", headers=token, json={"role_ids": []})
    assert resp3.json()["data"]["roles"] == []
