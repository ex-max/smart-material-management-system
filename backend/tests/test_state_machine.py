import pytest

from app.core.errors import InvalidState
from app.core.permissions import Perm
from app.core.state_machine import (
    ALL_STATUSES,
    DOC_FLOWS,
    TERMINAL_STATUSES,
    Actions,
    DocStatus,
    DocTypes,
    allowed_actions,
    apply_transition,
    can,
    is_terminal,
    require_transition,
)


class _Doc:
    def __init__(self, status: str) -> None:
        self.status = status


def test_global_states_and_terminal():
    assert len(ALL_STATUSES) == 6
    assert TERMINAL_STATUSES == {DocStatus.COMPLETED, DocStatus.CANCELLED}
    assert is_terminal(DocStatus.COMPLETED)
    assert not is_terminal(DocStatus.DRAFT)


def test_only_requisition_has_approval_edge():
    for doc_type, flow in DOC_FLOWS.items():
        assert (Actions.APPROVE in flow) == (doc_type == DocTypes.PURCHASE_REQUISITION)


def test_every_edge_has_permission_and_valid_states():
    perm_values = {getattr(Perm, name) for name in dir(Perm) if not name.startswith("_")}
    for flow in DOC_FLOWS.values():
        for transition in flow.values():
            assert transition.permission in perm_values, transition.permission
            assert transition.to_state in ALL_STATUSES
            assert transition.from_states
            for state in transition.from_states:
                assert state in ALL_STATUSES
                # 终态不可作为任何迁移的来源态
                assert not is_terminal(state), state


def test_apply_transition_advances_and_rejects_invalid():
    doc = _Doc(DocStatus.DRAFT)
    assert apply_transition(doc, DocTypes.PURCHASE_REQUISITION, Actions.SUBMIT) == DocStatus.PENDING
    with pytest.raises(InvalidState) as exc:
        apply_transition(doc, DocTypes.PURCHASE_REQUISITION, Actions.SUBMIT)
    assert exc.value.code == 30001
    assert doc.status == DocStatus.PENDING


def test_allowed_actions_and_can():
    assert Actions.APPROVE in allowed_actions(DocTypes.PURCHASE_REQUISITION, DocStatus.PENDING)
    assert not can(DocTypes.PURCHASE_REQUISITION, Actions.APPROVE, DocStatus.DRAFT)
    assert can(DocTypes.PURCHASE_ORDER, Actions.CONFIRM, DocStatus.DRAFT)
    # 请购单非终态可作废，但已完成不可
    assert can(DocTypes.PURCHASE_REQUISITION, Actions.CANCEL, DocStatus.IN_PROGRESS)
    assert not can(DocTypes.PURCHASE_REQUISITION, Actions.CANCEL, DocStatus.COMPLETED)


def test_completed_is_terminal_no_outgoing():
    doc = _Doc(DocStatus.COMPLETED)
    assert allowed_actions(DocTypes.PURCHASE_REQUISITION, DocStatus.COMPLETED) == []
    with pytest.raises(InvalidState):
        require_transition(DocTypes.PURCHASE_REQUISITION, Actions.CANCEL, DocStatus.COMPLETED)
    with pytest.raises(InvalidState):
        apply_transition(doc, DocTypes.PURCHASE_REQUISITION, Actions.START)
