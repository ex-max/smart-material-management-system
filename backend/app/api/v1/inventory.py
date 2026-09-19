from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.core.state_machine import Actions, DocTypes, get_transition
from app.model.user import User
from app.schema import inventory as ivs
from app.schema.common import ApiResponse, PageOut
from app.service.inventory import InboundService, InventoryService

router = APIRouter(tags=["库存"])

_VIEW = require_perm(Perm.INVENTORY_VIEW)
_INBOUND_POST = require_perm(get_transition(DocTypes.INBOUND_ORDER, Actions.START).permission)
_INBOUND_COMPLETE = require_perm(get_transition(DocTypes.INBOUND_ORDER, Actions.COMPLETE).permission)
_INBOUND_CANCEL = require_perm(get_transition(DocTypes.INBOUND_ORDER, Actions.CANCEL).permission)
_INBOUND_REVERSE = require_perm(get_transition(DocTypes.INBOUND_ORDER, Actions.REVERSE).permission)


# ---------------- 库存查询 ----------------
@router.get("/inventory", name="list_inventory", response_model=ApiResponse[PageOut[ivs.InventoryOut]])
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    material_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = InventoryService(db).list_inventory(page, page_size, material_id, warehouse_id)
    return ok({"total": total, "items": [ivs.InventoryOut.model_validate(x).model_dump() for x in items]})


@router.get(
    "/inventory/batches", name="list_inventory_batches", response_model=ApiResponse[PageOut[ivs.InventoryBatchOut]]
)
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    material_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = InventoryService(db).list_batches(page, page_size, material_id, warehouse_id)
    return ok({"total": total, "items": [ivs.InventoryBatchOut.model_validate(x).model_dump() for x in items]})


@router.get(
    "/inventory/transactions",
    name="list_inventory_transactions",
    response_model=ApiResponse[PageOut[ivs.InventoryTransactionOut]],
)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    material_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    source_type: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = InventoryService(db).list_transactions(page, page_size, material_id, warehouse_id, source_type)
    return ok({"total": total, "items": [ivs.InventoryTransactionOut.model_validate(x).model_dump() for x in items]})


@router.get("/inventory/reconcile", name="reconcile_inventory", response_model=ApiResponse[ivs.ReconcileOut])
def reconcile_inventory(user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(InventoryService(db).reconcile())


# ---------------- 入库单 ----------------
@router.get("/inbound-orders", name="list_inbound_orders", response_model=ApiResponse[PageOut[ivs.InboundOrderOut]])
def list_inbound_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = InboundService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ivs.InboundOrderOut.model_validate(x).model_dump() for x in items]})


@router.get("/inbound-orders/{inbound_id}", name="get_inbound_order", response_model=ApiResponse[ivs.InboundOrderOut])
def get_inbound_order(inbound_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ivs.InboundOrderOut.model_validate(InboundService(db).get(inbound_id)).model_dump())


@router.post("/inbound-orders/{inbound_id}/post", name="post_inbound_order", response_model=ApiResponse[ivs.InboundOrderOut])
def post_inbound_order(inbound_id: int, user: User = Depends(_INBOUND_POST), db: Session = Depends(get_db)):
    return ok(ivs.InboundOrderOut.model_validate(InboundService(db).post(inbound_id, user.id)).model_dump())


@router.post(
    "/inbound-orders/{inbound_id}/complete", name="complete_inbound_order", response_model=ApiResponse[ivs.InboundOrderOut]
)
def complete_inbound_order(inbound_id: int, user: User = Depends(_INBOUND_COMPLETE), db: Session = Depends(get_db)):
    return ok(ivs.InboundOrderOut.model_validate(InboundService(db).complete(inbound_id)).model_dump())


@router.post(
    "/inbound-orders/{inbound_id}/reverse", name="reverse_inbound_order", response_model=ApiResponse[ivs.InboundOrderOut]
)
def reverse_inbound_order(
    inbound_id: int,
    payload: dict | None = None,
    user: User = Depends(_INBOUND_REVERSE),
    db: Session = Depends(get_db),
):
    reason = payload.get("reason") if payload else None
    return ok(ivs.InboundOrderOut.model_validate(InboundService(db).reverse(inbound_id, user.id, reason)).model_dump())


@router.post(
    "/inbound-orders/{inbound_id}/cancel", name="cancel_inbound_order", response_model=ApiResponse[ivs.InboundOrderOut]
)
def cancel_inbound_order(
    inbound_id: int,
    payload: dict | None = None,
    user: User = Depends(_INBOUND_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.get("reason") if payload else None
    return ok(ivs.InboundOrderOut.model_validate(InboundService(db).cancel(inbound_id, reason)).model_dump())
