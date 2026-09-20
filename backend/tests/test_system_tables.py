"""S5 系统三表测试：dict 字典 CRUD/下拉、scheduled_task_log 记录/收尾、attachment 上传下载。

覆盖正常 / 边界 / 权限拒绝三类。
"""

from __future__ import annotations

import hashlib

import pytest

from app.core.dictionaries import DICT_SEED
from app.core.permissions import Perm
from app.core.security import hash_password
from app.core.state_machine import ALL_STATUSES
from app.model.user import Permission, Role, RolePermission, User, UserRole


@pytest.fixture()
def system_users(db_session, seeded):
    """系统组用户：viewer 只有读权限；manager 具备全部管理权限。"""
    db_session.add_all([
        Permission(code=Perm.DICT_VIEW, name="查看数据字典", type="API", sort_no=90),
        Permission(code=Perm.DICT_MANAGE, name="管理数据字典", type="API", sort_no=91),
        Permission(code=Perm.TASK_VIEW, name="查看任务日志", type="API", sort_no=92),
        Permission(code=Perm.TASK_MANAGE, name="记录任务日志", type="API", sort_no=93),
        Permission(code=Perm.ATTACHMENT_VIEW, name="查看附件", type="API", sort_no=94),
        Permission(code=Perm.ATTACHMENT_MANAGE, name="上传/删除附件", type="API", sort_no=95),
    ])
    db_session.flush()
    perms = {p.code: p for p in db_session.query(Permission).all()}

    viewer_role = Role(code="SYS_VIEW", name="系统查看")
    manager_role = Role(code="SYS_MANAGE", name="系统管理")
    db_session.add_all([viewer_role, manager_role])
    db_session.flush()
    view_codes = (Perm.DICT_VIEW, Perm.TASK_VIEW, Perm.ATTACHMENT_VIEW)
    manage_codes = view_codes + (Perm.DICT_MANAGE, Perm.TASK_MANAGE, Perm.ATTACHMENT_MANAGE)
    for code in view_codes:
        db_session.add(RolePermission(role_id=viewer_role.id, permission_id=perms[code].id))
    for code in manage_codes:
        db_session.add(RolePermission(role_id=manager_role.id, permission_id=perms[code].id))

    accounts = [
        ("sysviewer", viewer_role, "sysviewer123"),
        ("sysmanager", manager_role, "sysmanager123"),
    ]
    for username, role, password in accounts:
        user = User(
            username=username,
            password_hash=hash_password(password),
            real_name=username,
            status="ACTIVE",
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    return {u: p for u, _, p in accounts}


@pytest.fixture()
def attachment_dir(tmp_path, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    old = settings.attachment_dir
    settings.attachment_dir = str(tmp_path)
    yield tmp_path
    settings.attachment_dir = old


# ---------------- 预置字典口径 ----------------
def test_dict_seed_keys_are_unique_and_match_code_enums():
    keys = [(dict_type, dict_key) for dict_type, dict_key, _, _ in DICT_SEED]
    assert len(keys) == len(set(keys)), "预置字典 (dict_type, dict_key) 不得重复"
    doc_status = {key for dict_type, key, _, _ in DICT_SEED if dict_type == "doc_status"}
    assert doc_status == set(ALL_STATUSES)
    for dict_type, dict_key, dict_label, sort_no in DICT_SEED:
        assert dict_type and dict_key and dict_label and sort_no > 0


# ---------------- §13.1 dict ----------------
def test_dict_create_lookup_conflict_and_delete(client, login, system_users):
    headers = login("sysmanager", "sysmanager123")
    created = client.post(
        "/api/v1/dict-items",
        headers=headers,
        json={"dict_type": "priority", "dict_key": "VIP", "dict_label": "特急", "sort_no": 5},
    )
    assert created.status_code == 201, created.text
    item = created.json()["data"]
    assert item["dict_type"] == "priority" and item["is_active"] is True

    # 同 (dict_type, dict_key) 冲突
    dup = client.post(
        "/api/v1/dict-items",
        headers=headers,
        json={"dict_type": "priority", "dict_key": "VIP", "dict_label": "重复"},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == 60001

    # 下拉查询只返回启用项，按 sort_no 排序
    client.post(
        "/api/v1/dict-items",
        headers=headers,
        json={"dict_type": "priority", "dict_key": "OFF", "dict_label": "停用项", "sort_no": 9, "is_active": False},
    )
    lookup = client.get("/api/v1/dicts/priority", headers=headers)
    assert lookup.status_code == 200, lookup.text
    keys = [x["dict_key"] for x in lookup.json()["data"]]
    assert "VIP" in keys and "OFF" not in keys

    # 类型汇总
    types = client.get("/api/v1/dict-types", headers=headers)
    assert types.status_code == 200
    priority = [x for x in types.json()["data"] if x["dict_type"] == "priority"][0]
    assert priority["item_count"] == 2 and priority["active_count"] == 1

    # 关键字 + 启用筛选
    listed = client.get(
        "/api/v1/dict-items", headers=headers, params={"dict_type": "priority", "keyword": "特急"}
    )
    assert listed.json()["data"]["total"] == 1
    active_only = client.get("/api/v1/dict-items", headers=headers, params={"is_active": True})
    assert all(x["is_active"] for x in active_only.json()["data"]["items"])

    # 更新（dict_key 不可改：不在 Update 模型内）
    updated = client.put(
        "/api/v1/dict-items/%d" % item["id"], headers=headers, json={"dict_label": "特急(改)", "sort_no": 1}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["dict_label"] == "特急(改)"
    assert updated.json()["data"]["dict_key"] == "VIP"

    # 软删后查不到、下拉不含
    deleted = client.delete("/api/v1/dict-items/%d" % item["id"], headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/v1/dict-items/%d" % item["id"], headers=headers).status_code == 404
    assert "VIP" not in [x["dict_key"] for x in client.get("/api/v1/dicts/priority", headers=headers).json()["data"]]


def test_dict_permissions(client, login, system_users):
    assert client.get("/api/v1/dict-items").status_code == 401
    viewer = login("sysviewer", "sysviewer123")
    assert client.get("/api/v1/dict-items", headers=viewer).status_code == 200
    denied = client.post(
        "/api/v1/dict-items",
        headers=viewer,
        json={"dict_type": "priority", "dict_key": "X", "dict_label": "X"},
    )
    assert denied.status_code == 403
    admin = login("admin", "admin123")
    assert client.get("/api/v1/dict-types", headers=admin).status_code == 200


# ---------------- §13.2 scheduled_task_log ----------------
def test_task_log_append_finish_query_and_state_guard(client, login, system_users):
    headers = login("sysmanager", "sysmanager123")
    appended = client.post(
        "/api/v1/scheduled-task-logs",
        headers=headers,
        json={"task_name": "alert_scan", "task_type": "MAINTENANCE", "trace_id": "t-1"},
    )
    assert appended.status_code == 201, appended.text
    row = appended.json()["data"]
    assert row["status"] == "RUNNING" and row["finished_at"] is None

    finished = client.post(
        "/api/v1/scheduled-task-logs/%d/finish" % row["id"],
        headers=headers,
        json={"status": "SUCCESS", "affected_rows": 3, "result_summary": "扫描完成"},
    )
    assert finished.status_code == 200, finished.text
    done = finished.json()["data"]
    assert done["status"] == "SUCCESS"
    assert done["affected_rows"] == 3
    assert done["finished_at"] is not None and done["duration_ms"] is not None and done["duration_ms"] >= 0

    # 已终态不可再收尾
    again = client.post(
        "/api/v1/scheduled-task-logs/%d/finish" % row["id"],
        headers=headers,
        json={"status": "SUCCESS"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == 60002

    # 直接落 FAILED
    failed = client.post(
        "/api/v1/scheduled-task-logs",
        headers=headers,
        json={"task_name": "snapshot_daily", "status": "FAILED", "error_detail": "db down"},
    )
    assert failed.json()["data"]["status"] == "FAILED"

    detail = client.get("/api/v1/scheduled-task-logs/%d" % row["id"], headers=headers)
    assert detail.status_code == 200

    listed = client.get(
        "/api/v1/scheduled-task-logs", headers=headers, params={"task_name": "alert_scan", "status": "SUCCESS"}
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 1


def test_task_log_permissions(client, login, system_users):
    assert client.get("/api/v1/scheduled-task-logs").status_code == 401
    viewer = login("sysviewer", "sysviewer123")
    assert client.get("/api/v1/scheduled-task-logs", headers=viewer).status_code == 200
    denied = client.post(
        "/api/v1/scheduled-task-logs", headers=viewer, json={"task_name": "x"}
    )
    assert denied.status_code == 403


# ---------------- §13.3 attachment ----------------
def test_attachment_upload_download_list_delete(client, login, system_users, attachment_dir):
    headers = login("sysmanager", "sysmanager123")
    payload = "hello 附件".encode()
    uploaded = client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"biz_type": "purchase_order", "biz_id": "1"},
        files={"file": ("note.txt", payload, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    att = uploaded.json()["data"]
    assert att["file_name"] == "note.txt"
    assert att["file_size"] == len(payload)
    assert att["sha256"] == hashlib.sha256(payload).hexdigest()
    assert att["storage"] == "LOCAL"

    download = client.get("/api/v1/attachments/%d/download" % att["id"], headers=headers)
    assert download.status_code == 200, download.text
    assert download.content == payload

    listed = client.get(
        "/api/v1/attachments", headers=headers, params={"biz_type": "purchase_order", "biz_id": 1}
    )
    assert listed.json()["data"]["total"] == 1

    deleted = client.delete("/api/v1/attachments/%d" % att["id"], headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/v1/attachments/%d" % att["id"], headers=headers).status_code == 404
    # 软删后列表不含；文件本体保留可审计
    assert client.get("/api/v1/attachments", headers=headers).json()["data"]["total"] == 0
    assert list(attachment_dir.rglob("*.txt")), "软删不物理删除文件"


def test_attachment_rejects_bad_type_and_empty(client, login, system_users, attachment_dir):
    headers = login("sysmanager", "sysmanager123")
    bad = client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"biz_type": "purchase_order", "biz_id": "1"},
        files={"file": ("evil.exe", b"MZ...", "application/x-msdownload")},
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == 60003

    empty = client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"biz_type": "purchase_order", "biz_id": "1"},
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty.status_code == 500
    assert empty.json()["code"] == 60005


def test_attachment_rejects_oversize(client, login, system_users, attachment_dir):
    from app.core.config import get_settings

    get_settings().attachment_max_size_mb = 1
    headers = login("sysmanager", "sysmanager123")
    big = b"x" * (1024 * 1024 + 64)
    resp = client.post(
        "/api/v1/attachments",
        headers=headers,
        data={"biz_type": "purchase_order", "biz_id": "1"},
        files={"file": ("big.txt", big, "text/plain")},
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == 60004
    # 超限不留半截文件
    assert not list(attachment_dir.rglob("*")) or not any(p.is_file() for p in attachment_dir.rglob("*"))


def test_attachment_permissions(client, login, system_users, attachment_dir):
    assert client.get("/api/v1/attachments").status_code == 401
    viewer = login("sysviewer", "sysviewer123")
    assert client.get("/api/v1/attachments", headers=viewer).status_code == 200
    denied = client.post(
        "/api/v1/attachments",
        headers=viewer,
        data={"biz_type": "purchase_order", "biz_id": "1"},
        files={"file": ("x.txt", b"x", "text/plain")},
    )
    assert denied.status_code == 403
