"""S3 操作日志测试：成功/失败写入、脱敏、trace 关联、分页过滤、权限。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.permissions import Perm
from app.core.security import hash_password
from app.model.user import OperationLog, Permission, Role, RolePermission, User, UserRole


@pytest.fixture()
def log_viewer(db_session, seeded):
    """具备 operation:view 的普通用户（非超管）。"""
    db_session.add(Permission(code=Perm.OPERATION_VIEW, name="查看操作日志", type="API", sort_no=80))
    db_session.flush()
    perms = {p.code: p for p in db_session.query(Permission).all()}
    role = Role(code="LOG_VIEW", name="日志查看")
    db_session.add(role)
    db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission_id=perms[Perm.OPERATION_VIEW].id))
    user = User(
        username="logviewer",
        password_hash=hash_password("logviewer123"),
        real_name="logviewer",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    return {"id": user.id, "username": "logviewer", "password": "logviewer123"}


def _logs_by_request(db_session, request_id: str) -> list[OperationLog]:
    return (
        db_session.query(OperationLog)
        .filter(OperationLog.request_id == request_id)
        .order_by(OperationLog.id)
        .all()
    )


def test_success_request_writes_log_with_operator(client, login, log_viewer, db_session):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": log_viewer["username"], "password": log_viewer["password"]},
    )
    assert resp.status_code == 200, resp.text
    trace_id = resp.headers["X-Trace-Id"]

    rows = _logs_by_request(db_session, trace_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.result == "SUCCESS"
    assert row.module == "auth"
    assert row.action == "login"
    assert row.method == "POST"
    assert row.path == "/api/v1/auth/login"
    assert row.user_id == log_viewer["id"]
    assert row.username == log_viewer["username"]
    assert row.error_code is None
    assert row.duration_ms is not None and row.duration_ms >= 0
    # 脱敏：不落请求体 detail
    assert row.detail is None


def test_failure_request_writes_fail_log_with_error_code(client, procurement_master, db_session):
    headers = procurement_master["admin"]
    resp = client.get("/api/v1/forecast-runs/999999", headers=headers)
    assert resp.status_code == 404
    body = resp.json()
    trace_id = body["trace_id"]

    rows = _logs_by_request(db_session, trace_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.result == "FAIL"
    assert row.error_code == str(body["code"])
    assert row.action == "get_forecast_run"
    assert row.module == "forecast"
    assert row.resource_type == "forecast-runs"
    assert row.resource_id == "999999"
    assert row.detail == {"status_code": 404}


def test_no_sensitive_payload_in_logs(client, procurement_master, db_session):
    headers = procurement_master["admin"]
    secret = "S3-SECRET-TOKEN-9f2c"
    resp = client.get("/api/v1/warehouses", headers=headers, params={"token": secret})
    assert resp.status_code == 200, resp.text

    rows = db_session.query(OperationLog).all()
    assert rows, "应至少有一条审计日志"
    blob = " ".join(
        " ".join(
            str(getattr(row, column))
            for column in (
                "username",
                "module",
                "action",
                "resource_type",
                "resource_id",
                "method",
                "path",
                "ip",
                "user_agent",
                "request_id",
                "error_code",
                "detail",
            )
        )
        for row in rows
    )
    assert secret not in blob
    assert "authorization" not in blob.lower()
    assert "bearer " not in blob.lower()
    # query string 不落 path
    assert all("?" not in (row.path or "") for row in rows)


def test_filters_pagination_and_time_range(client, login, log_viewer, db_session):
    headers = login(log_viewer["username"], log_viewer["password"])
    denied = client.get("/api/v1/materials", headers=headers)
    assert denied.status_code == 403

    # 冻结时间窗口：排除「查询操作日志」请求自身产生的日志，使结果集稳定
    cutoff = datetime.now(timezone.utc).isoformat()
    frozen = {"user_id": log_viewer["id"], "end_time": cutoff}

    listed = client.get(
        "/api/v1/operation-logs", headers=headers, params={**frozen, "page_size": 50}
    )
    assert listed.status_code == 200, listed.text
    data = listed.json()["data"]
    assert data["total"] == 2
    assert {item["action"] for item in data["items"]} == {"login", "list_material"}

    failed = client.get(
        "/api/v1/operation-logs", headers=headers, params={**frozen, "result": "FAIL"}
    ).json()["data"]
    assert failed["total"] == 1
    assert failed["items"][0]["action"] == "list_material"
    assert all(item["username"] == "logviewer" for item in failed["items"])

    login_rows = client.get(
        "/api/v1/operation-logs", headers=headers, params={"action": "login", "end_time": cutoff}
    ).json()["data"]
    assert login_rows["total"] == 1
    assert all(item["action"] == "login" for item in login_rows["items"])

    page1 = client.get(
        "/api/v1/operation-logs", headers=headers, params={**frozen, "page": 1, "page_size": 1}
    ).json()["data"]
    page2 = client.get(
        "/api/v1/operation-logs", headers=headers, params={**frozen, "page": 2, "page_size": 1}
    ).json()["data"]
    assert len(page1["items"]) == 1 and len(page2["items"]) == 1
    assert page1["items"][0]["id"] != page2["items"][0]["id"]

    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    empty = client.get(
        "/api/v1/operation-logs", headers=headers, params={"start_time": future}
    ).json()["data"]
    assert empty["total"] == 0


def test_permissions_anonymous_forbidden_admin(client, login, seeded):
    assert client.get("/api/v1/operation-logs").status_code == 401
    viewer = login("viewer", "viewer123")
    assert client.get("/api/v1/operation-logs", headers=viewer).status_code == 403
    admin = login("admin", "admin123")
    assert client.get("/api/v1/operation-logs", headers=admin).status_code == 200
