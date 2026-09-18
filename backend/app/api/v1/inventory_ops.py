from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.core.state_machine import Actions, DocTypes, get_transition
from app.model.user import User
from app.schema import inventory_ops as ops
from app.schema import purchase as ps
from app.service.inventory_ops import OutboundService, StocktakeService, TransferService

router = APIRouter(tags=["库存作业"])

_VIEW = require_perm(Perm.INVENTORY_VIEW)
_REVERSE_PERM = require_perm(get_transition(DocTypes.OUTBOUND_ORDER, Actions.REVERSE).permission)

_OUT_POST = require_perm(get_transition(DocTypes.OUTBOUND_ORDER, Actions.START).permission)
_OUT_COMPLETE = require_perm(get_transition(DocTypes.OUTBOUND_ORDER, Actions.COMPLETE).permission)
_OUT_CANCEL = require_perm(get_transition(DocTypes.OUTBOUND_ORDER, Actions.CANCEL).permission)
_TR_POST = require_perm(get_transition(DocTypes.TRANSFER_ORDER, Actions.START).permission)
_TR_COMPLETE = require_perm(get_transition(DocTypes.TRANSFER_ORDER, Actions.COMPLETE).permission)
_TR_CANCEL = require_perm(get_transition(DocTypes.TRANSFER_ORDER, Actions.CANCEL).permission)
_ST_CREATE = require_perm(Perm.INVENTORY_MANAGE)
_ST_START = require_perm(get_transition(DocTypes.STOCKTAKE_ORDER, Actions.START).permission)
_ST_COMPLETE = require_perm(get_transition(DocTypes.STOCKTAKE_ORDER, Actions.COMPLETE).permission)
_ST_CANCEL = require_perm(get_transition(DocTypes.STOCKTAKE_ORDER, Actions.CANCEL).permission)


# ---------------- 出库单 ----------------
@router.get("/outbound-orders", name="list_outbound_orders")
def list_outbound_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = OutboundService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ops.OutboundOrderOut.model_validate(x).model_dump() for x in items]})


@router.post("/outbound-orders", status_code=201, name="create_outbound_order")
def create_outbound_order(
    payload: ops.OutboundCreate, user: User = Depends(_ST_CREATE), db: Session = Depends(get_db)
):
    return ok(ops.OutboundOrderOut.model_validate(OutboundService(db).create(payload, user.id)).model_dump())


@router.get("/outbound-orders/{outbound_id}", name="get_outbound_order")
def get_outbound_order(outbound_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ops.OutboundOrderOut.model_validate(OutboundService(db).get(outbound_id)).model_dump())


@router.put("/outbound-orders/{outbound_id}", name="update_outbound_order")
def update_outbound_order(
    outbound_id: int,
    payload: ops.OutboundUpdate,
    user: User = Depends(_ST_CREATE),
    db: Session = Depends(get_db),
):
    return ok(ops.OutboundOrderOut.model_validate(OutboundService(db).update(outbound_id, payload)).model_dump())


@router.delete("/outbound-orders/{outbound_id}", name="delete_outbound_order")
def delete_outbound_order(outbound_id: int, user: User = Depends(_ST_CREATE), db: Session = Depends(get_db)):
    OutboundService(db).delete(outbound_id)
    return ok(None)


@router.post("/outbound-orders/{outbound_id}/post", name="post_outbound_order")
def post_outbound_order(outbound_id: int, user: User = Depends(_OUT_POST), db: Session = Depends(get_db)):
    return ok(ops.OutboundOrderOut.model_validate(OutboundService(db).post(outbound_id, user.id)).model_dump())


@router.post("/outbound-orders/{outbound_id}/complete", name="complete_outbound_order")
def complete_outbound_order(outbound_id: int, user: User = Depends(_OUT_COMPLETE), db: Session = Depends(get_db)):
    return ok(ops.OutboundOrderOut.model_validate(OutboundService(db).complete(outbound_id)).model_dump())


@router.post("/outbound-orders/{outbound_id}/cancel", name="cancel_outbound_order")
def cancel_outbound_order(
    outbound_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_OUT_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ops.OutboundOrderOut.model_validate(OutboundService(db).cancel(outbound_id, reason)).model_dump())


@router.post("/outbound-orders/{outbound_id}/reverse", name="reverse_outbound_order")
def reverse_outbound_order(
    outbound_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_REVERSE_PERM),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    obj = OutboundService(db).reverse(outbound_id, user.id, reason)
    return ok(ops.OutboundOrderOut.model_validate(obj).model_dump())


# ---------------- 调拨单 ----------------
@router.get("/transfer-orders", name="list_transfer_orders")
def list_transfer_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = TransferService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ops.TransferOrderOut.model_validate(x).model_dump() for x in items]})


@router.post("/transfer-orders", status_code=201, name="create_transfer_order")
def create_transfer_order(payload: ops.TransferCreate, user: User = Depends(_ST_CREATE), db: Session = Depends(get_db)):
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).create(payload, user.id)).model_dump())


@router.get("/transfer-orders/{transfer_id}", name="get_transfer_order")
def get_transfer_order(transfer_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).get(transfer_id)).model_dump())


@router.put("/transfer-orders/{transfer_id}", name="update_transfer_order")
def update_transfer_order(
    transfer_id: int,
    payload: ops.TransferUpdate,
    user: User = Depends(_ST_CREATE),
    db: Session = Depends(get_db),
):
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).update(transfer_id, payload)).model_dump())


@router.delete("/transfer-orders/{transfer_id}", name="delete_transfer_order")
def delete_transfer_order(transfer_id: int, user: User = Depends(_ST_CREATE), db: Session = Depends(get_db)):
    TransferService(db).delete(transfer_id)
    return ok(None)


@router.post("/transfer-orders/{transfer_id}/post", name="post_transfer_order")
def post_transfer_order(transfer_id: int, user: User = Depends(_TR_POST), db: Session = Depends(get_db)):
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).post(transfer_id, user.id)).model_dump())


@router.post("/transfer-orders/{transfer_id}/complete", name="complete_transfer_order")
def complete_transfer_order(transfer_id: int, user: User = Depends(_TR_COMPLETE), db: Session = Depends(get_db)):
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).complete(transfer_id)).model_dump())


@router.post("/transfer-orders/{transfer_id}/cancel", name="cancel_transfer_order")
def cancel_transfer_order(
    transfer_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_TR_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).cancel(transfer_id, reason)).model_dump())


@router.post("/transfer-orders/{transfer_id}/reverse", name="reverse_transfer_order")
def reverse_transfer_order(
    transfer_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_REVERSE_PERM),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ops.TransferOrderOut.model_validate(TransferService(db).reverse(transfer_id, user.id, reason)).model_dump())


# ---------------- 盘点单 ----------------
@router.get("/stocktake-orders", name="list_stocktake_orders")
def list_stocktake_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = StocktakeService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ops.StocktakeOrderOut.model_validate(x).model_dump() for x in items]})


@router.post("/stocktake-orders", status_code=201, name="create_stocktake_order")
def create_stocktake_order(
    payload: ops.StocktakeCreate, user: User = Depends(_ST_CREATE), db: Session = Depends(get_db)
):
    return ok(ops.StocktakeOrderOut.model_validate(StocktakeService(db).create(payload, user.id)).model_dump())


@router.get("/stocktake-orders/{stocktake_id}", name="get_stocktake_order")
def get_stocktake_order(stocktake_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ops.StocktakeOrderOut.model_validate(StocktakeService(db).get(stocktake_id)).model_dump())


@router.put("/stocktake-orders/{stocktake_id}", name="update_stocktake_order")
def update_stocktake_order(
    stocktake_id: int,
    payload: ops.StocktakeUpdate,
    user: User = Depends(_ST_CREATE),
    db: Session = Depends(get_db),
):
    return ok(ops.StocktakeOrderOut.model_validate(StocktakeService(db).update(stocktake_id, payload)).model_dump())


@router.delete("/stocktake-orders/{stocktake_id}", name="delete_stocktake_order")
def delete_stocktake_order(stocktake_id: int, user: User = Depends(_ST_CREATE), db: Session = Depends(get_db)):
    StocktakeService(db).delete(stocktake_id)
    return ok(None)


@router.post("/stocktake-orders/{stocktake_id}/start", name="start_stocktake_order")
def start_stocktake_order(stocktake_id: int, user: User = Depends(_ST_START), db: Session = Depends(get_db)):
    return ok(ops.StocktakeOrderOut.model_validate(StocktakeService(db).start(stocktake_id, user.id)).model_dump())


@router.post("/stocktake-orders/{stocktake_id}/counts", name="count_stocktake_order")
def count_stocktake_order(
    stocktake_id: int,
    payload: ops.StocktakeCountIn,
    user: User = Depends(_ST_CREATE),
    db: Session = Depends(get_db),
):
    return ok(ops.StocktakeOrderOut.model_validate(StocktakeService(db).set_counts(stocktake_id, payload)).model_dump())


@router.post("/stocktake-orders/{stocktake_id}/complete", name="complete_stocktake_order")
def complete_stocktake_order(stocktake_id: int, user: User = Depends(_ST_COMPLETE), db: Session = Depends(get_db)):
    return ok(
        ops.StocktakeOrderOut.model_validate(StocktakeService(db).complete(stocktake_id, user.id)).model_dump()
    )


@router.post("/stocktake-orders/{stocktake_id}/cancel", name="cancel_stocktake_order")
def cancel_stocktake_order(
    stocktake_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_ST_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ops.StocktakeOrderOut.model_validate(StocktakeService(db).cancel(stocktake_id, reason)).model_dump())


@router.post("/stocktake-orders/{stocktake_id}/reverse", name="reverse_stocktake_order")
def reverse_stocktake_order(
    stocktake_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_REVERSE_PERM),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(
        ops.StocktakeOrderOut.model_validate(StocktakeService(db).reverse(stocktake_id, user.id, reason)).model_dump()
    )
