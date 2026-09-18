#!/usr/bin/env python3
"""领域不变量自检（make verify 第 6 项）。

1. 状态机结构性检查：全局 6 态、迁移边状态合法、终态无出边、
   只有请购单有审批动作、迁移边权限码与 core.permissions.Perm 一致。
2. 单据 service 不得直接赋值 status（必须走 state_machine.apply_transition）。

只用标准库 + backend 源码路径，避免依赖 venv。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.permissions import Perm  # noqa: E402
from app.core.state_machine import (  # noqa: E402
    ALL_STATUSES,
    DOC_FLOWS,
    TERMINAL_STATUSES,
    Actions,
    DocStatus,
    DocTypes,
    is_terminal,
)

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


check(len(ALL_STATUSES) == 6, "全局状态应为 6 个，实际 %d" % len(ALL_STATUSES))
check(
    TERMINAL_STATUSES == frozenset({DocStatus.COMPLETED, DocStatus.CANCELLED}),
    "终态应为 COMPLETED / CANCELLED",
)

perm_values = {getattr(Perm, name) for name in dir(Perm) if not name.startswith("_")}
approve_owners: list[str] = []
for doc_type, flow in DOC_FLOWS.items():
    if Actions.APPROVE in flow:
        approve_owners.append(doc_type)
    for transition in flow.values():
        check(
            transition.permission in perm_values,
            "%s/%s 的权限码不在 Perm：%s" % (doc_type, transition.action, transition.permission),
        )
        check(transition.to_state in ALL_STATUSES, "%s 目标态非法：%s" % (doc_type, transition.to_state))
        check(bool(transition.from_states), "%s/%s 缺少来源态" % (doc_type, transition.action))
        for state in transition.from_states:
            check(state in ALL_STATUSES, "%s 来源态非法：%s" % (doc_type, state))
            check(
                not is_terminal(state),
                "%s/%s 从终态 %s 出发（终态不可迁移）" % (doc_type, transition.action, state),
            )
check(
    set(approve_owners) == {DocTypes.PURCHASE_REQUISITION},
    "只有请购单应有审批动作，实际：%s" % sorted(approve_owners),
)

# 单据 service 不得直写 status（含 == 比较的误报用负向先行排除）
STATUS_ASSIGN = re.compile(r"\.status\s*=(?!=)")
for name in ("purchase.py", "inventory.py"):
    path = ROOT / "backend" / "app" / "service" / name
    if not path.exists():
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if STATUS_ASSIGN.search(line):
            FAILURES.append("%s:%d 直接赋值 status：%s" % (name, lineno, line.strip()))

if FAILURES:
    print("领域不变量检查失败：")
    for item in FAILURES:
        print("  - " + item)
    sys.exit(1)

print("领域不变量检查通过：6 态 / %d 类单据 / 仅请购单审批 / service 未直改 status" % len(DOC_FLOWS))
