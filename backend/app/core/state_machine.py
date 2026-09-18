"""单据状态机（单一事实来源）。

全局 6 态（docs/db-schema.md §1.6）：

    DRAFT ──提交──▶ PENDING ──审批──▶ APPROVED ──执行──▶ IN_PROGRESS ──完成──▶ COMPLETED
      └──────────────┴────────────────┴──────────────── 作废 ────────────────▶ CANCELLED

设计约定：
- 所有迁移边集中在 DOC_FLOWS，禁止在 service 里散落 if-else。
- 每条迁移边都绑定权限码（API 层用 require_perm 强制）与前置状态。
- 唯一允许写 doc.status 的入口是 apply_transition()。
- 各单据允许的状态子集见 docs/db-schema.md §1.6；库存四单为 M2-b 预留。
"""

from dataclasses import dataclass

from app.core.errors import InvalidState


class DocStatus:
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


ALL_STATUSES: tuple[str, ...] = (
    DocStatus.DRAFT,
    DocStatus.PENDING,
    DocStatus.APPROVED,
    DocStatus.IN_PROGRESS,
    DocStatus.COMPLETED,
    DocStatus.CANCELLED,
)

TERMINAL_STATUSES: frozenset[str] = frozenset({DocStatus.COMPLETED, DocStatus.CANCELLED})


class DocTypes:
    PURCHASE_REQUISITION = "purchase_requisition"
    PURCHASE_ORDER = "purchase_order"
    SUPPLIER_DELIVERY = "supplier_delivery"
    INBOUND_ORDER = "inbound_order"
    OUTBOUND_ORDER = "outbound_order"
    TRANSFER_ORDER = "transfer_order"
    STOCKTAKE_ORDER = "stocktake_order"


class Actions:
    SUBMIT = "submit"
    APPROVE = "approve"
    ACCEPT = "accept"
    CONFIRM = "confirm"
    START = "start"
    COMPLETE = "complete"
    CANCEL = "cancel"


@dataclass(frozen=True)
class Transition:
    """一条状态迁移边：动作 + 目标态 + 允许的来源态 + 权限码 + 中文标签。"""

    action: str
    to_state: str
    from_states: tuple[str, ...]
    permission: str
    label: str


def _t(action: str, to_state: str, from_states, permission: str, label: str) -> Transition:
    return Transition(action, to_state, tuple(from_states), permission, label)


# 权限码以字符串写在这里，避免 core.permissions 与 core.errors 之间的循环导入；
# tests/test_state_machine.py 会断言它们与 Perm 常量一致。
_REQ_MANAGE = "purchase:manage"
_REQ_APPROVE = "purchase:approve"
_INV_MANAGE = "inventory:manage"

# 采购单据可作废的来源态（已完成的单据不可回退）；库存单据仅草稿可作废。
_PURCHASE_CANCELLABLE = (
    DocStatus.DRAFT,
    DocStatus.PENDING,
    DocStatus.APPROVED,
    DocStatus.IN_PROGRESS,
)
_DRAFT_ONLY = (DocStatus.DRAFT,)


DOC_FLOWS: dict[str, dict[str, Transition]] = {
    DocTypes.PURCHASE_REQUISITION: {
        Actions.SUBMIT: _t(Actions.SUBMIT, DocStatus.PENDING, _DRAFT_ONLY, _REQ_MANAGE, "提交"),
        Actions.APPROVE: _t(Actions.APPROVE, DocStatus.APPROVED, (DocStatus.PENDING,), _REQ_APPROVE, "审批"),
        Actions.START: _t(Actions.START, DocStatus.IN_PROGRESS, (DocStatus.APPROVED,), _REQ_MANAGE, "转采购订单"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.IN_PROGRESS,), _REQ_MANAGE, "完成"),
        Actions.CANCEL: _t(Actions.CANCEL, DocStatus.CANCELLED, _PURCHASE_CANCELLABLE, _REQ_MANAGE, "作废"),
    },
    DocTypes.PURCHASE_ORDER: {
        Actions.CONFIRM: _t(Actions.CONFIRM, DocStatus.APPROVED, _DRAFT_ONLY, _REQ_MANAGE, "确认下单"),
        Actions.START: _t(Actions.START, DocStatus.IN_PROGRESS, (DocStatus.APPROVED,), _REQ_MANAGE, "开始到货"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.IN_PROGRESS,), _REQ_MANAGE, "完成"),
        Actions.CANCEL: _t(Actions.CANCEL, DocStatus.CANCELLED, _PURCHASE_CANCELLABLE, _REQ_MANAGE, "作废"),
    },
    DocTypes.SUPPLIER_DELIVERY: {
        Actions.SUBMIT: _t(Actions.SUBMIT, DocStatus.PENDING, _DRAFT_ONLY, _REQ_MANAGE, "提交待验收"),
        Actions.ACCEPT: _t(Actions.ACCEPT, DocStatus.APPROVED, (DocStatus.PENDING,), _REQ_MANAGE, "验收通过"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.APPROVED,), _REQ_MANAGE, "已入库"),
        Actions.CANCEL: _t(
            Actions.CANCEL,
            DocStatus.CANCELLED,
            (DocStatus.DRAFT, DocStatus.PENDING, DocStatus.APPROVED),
            _REQ_MANAGE,
            "拒收/作废",
        ),
    },
    DocTypes.INBOUND_ORDER: {
        Actions.START: _t(Actions.START, DocStatus.IN_PROGRESS, _DRAFT_ONLY, _INV_MANAGE, "执行过账"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.IN_PROGRESS,), _INV_MANAGE, "完成"),
        Actions.CANCEL: _t(Actions.CANCEL, DocStatus.CANCELLED, _DRAFT_ONLY, _INV_MANAGE, "作废"),
    },
    DocTypes.OUTBOUND_ORDER: {
        Actions.START: _t(Actions.START, DocStatus.IN_PROGRESS, _DRAFT_ONLY, _INV_MANAGE, "执行过账"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.IN_PROGRESS,), _INV_MANAGE, "完成"),
        Actions.CANCEL: _t(Actions.CANCEL, DocStatus.CANCELLED, _DRAFT_ONLY, _INV_MANAGE, "作废"),
    },
    DocTypes.TRANSFER_ORDER: {
        Actions.START: _t(Actions.START, DocStatus.IN_PROGRESS, _DRAFT_ONLY, _INV_MANAGE, "执行过账"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.IN_PROGRESS,), _INV_MANAGE, "完成"),
        Actions.CANCEL: _t(Actions.CANCEL, DocStatus.CANCELLED, _DRAFT_ONLY, _INV_MANAGE, "作废"),
    },
    DocTypes.STOCKTAKE_ORDER: {
        Actions.START: _t(Actions.START, DocStatus.IN_PROGRESS, _DRAFT_ONLY, _INV_MANAGE, "执行过账"),
        Actions.COMPLETE: _t(Actions.COMPLETE, DocStatus.COMPLETED, (DocStatus.IN_PROGRESS,), _INV_MANAGE, "完成"),
        Actions.CANCEL: _t(Actions.CANCEL, DocStatus.CANCELLED, _DRAFT_ONLY, _INV_MANAGE, "作废"),
    },
}


def flow_for(doc_type: str) -> dict[str, Transition]:
    try:
        return DOC_FLOWS[doc_type]
    except KeyError as exc:  # pragma: no cover - 防御性分支
        raise InvalidState("未知单据类型：" + str(doc_type)) from exc


def get_transition(doc_type: str, action: str) -> Transition:
    flow = flow_for(doc_type)
    if action not in flow:
        raise InvalidState("单据 %s 不支持动作 %s" % (doc_type, action))
    return flow[action]


def can(doc_type: str, action: str, state: str) -> bool:
    flow = DOC_FLOWS.get(doc_type)
    if not flow or action not in flow:
        return False
    return state in flow[action].from_states


def require_transition(doc_type: str, action: str, state: str) -> Transition:
    """校验来源态并返回迁移边；不合法时抛 InvalidState（业务码 30001，HTTP 409）。"""
    transition = get_transition(doc_type, action)
    if state not in transition.from_states:
        raise InvalidState(
            "当前状态 %s 不允许执行「%s」（允许来源态：%s）"
            % (state, transition.label, "/".join(transition.from_states))
        )
    return transition


def apply_transition(doc, doc_type: str, action: str) -> str:
    """按状态机推进单据状态；这是唯一允许写 doc.status 的入口。"""
    transition = require_transition(doc_type, action, doc.status)
    doc.status = transition.to_state
    return transition.to_state


def allowed_actions(doc_type: str, state: str) -> list[str]:
    flow = DOC_FLOWS.get(doc_type, {})
    return [action for action, transition in flow.items() if state in transition.from_states]


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATUSES
