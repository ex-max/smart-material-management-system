from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.core.state_machine import Actions, DocTypes, get_transition
from app.model.user import User
from app.schema import inventory as ivs
from app.schema import purchase as ps
from app.schema.common import ApiResponse, PageOut
from app.service.inventory import InboundService
from app.service.purchase import PurchaseOrderService, PurchaseRequisitionService, SupplierDeliveryService

router = APIRouter(tags=["采购"])

_VIEW = require_perm(Perm.PURCHASE_VIEW)
_REQ = DocTypes.PURCHASE_REQUISITION
_PO = DocTypes.PURCHASE_ORDER
_RCV = DocTypes.SUPPLIER_DELIVERY

# 动作权限码从状态机迁移边读取（单一事实来源）
_REQ_MANAGE = require_perm(Perm.PURCHASE_MANAGE)
_REQ_SUBMIT = require_perm(get_transition(_REQ, Actions.SUBMIT).permission)
_REQ_APPROVE = require_perm(get_transition(_REQ, Actions.APPROVE).permission)
_REQ_CANCEL = require_perm(get_transition(_REQ, Actions.CANCEL).permission)
_REQ_START = require_perm(get_transition(_REQ, Actions.START).permission)

_PO_MANAGE = require_perm(Perm.PURCHASE_MANAGE)
_PO_CONFIRM = require_perm(get_transition(_PO, Actions.CONFIRM).permission)
_PO_CANCEL = require_perm(get_transition(_PO, Actions.CANCEL).permission)

_RCV_MANAGE = require_perm(Perm.PURCHASE_MANAGE)
_RCV_SUBMIT = require_perm(get_transition(_RCV, Actions.SUBMIT).permission)
_RCV_CANCEL = require_perm(get_transition(_RCV, Actions.CANCEL).permission)
_RCV_ACCEPT = require_perm(get_transition(_RCV, Actions.ACCEPT).permission)


# ---------------- 请购单 ----------------
@router.get(
    "/purchase-requisitions",
    name="list_purchase_requisitions",
    response_model=ApiResponse[PageOut[ps.PROut]],
)
def list_requisitions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = PurchaseRequisitionService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ps.PROut.model_validate(x).model_dump() for x in items]})


@router.post(
    "/purchase-requisitions",
    status_code=201,
    name="create_purchase_requisition",
    response_model=ApiResponse[ps.PROut],
)
def create_requisition(
    payload: ps.PRCreate,
    user: User = Depends(_REQ_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ps.PROut.model_validate(PurchaseRequisitionService(db).create(payload, user.id)).model_dump())


@router.get("/purchase-requisitions/{req_id}", name="get_purchase_requisition", response_model=ApiResponse[ps.PROut])
def get_requisition(req_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ps.PROut.model_validate(PurchaseRequisitionService(db).get(req_id)).model_dump())


@router.put(
    "/purchase-requisitions/{req_id}", name="update_purchase_requisition", response_model=ApiResponse[ps.PROut]
)
def update_requisition(
    req_id: int,
    payload: ps.PRUpdate,
    user: User = Depends(_REQ_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ps.PROut.model_validate(PurchaseRequisitionService(db).update(req_id, payload)).model_dump())


@router.delete("/purchase-requisitions/{req_id}", name="delete_purchase_requisition")
def delete_requisition(req_id: int, user: User = Depends(_REQ_MANAGE), db: Session = Depends(get_db)):
    PurchaseRequisitionService(db).delete(req_id)
    return ok(None)


@router.post(
    "/purchase-requisitions/{req_id}/submit",
    name="submit_purchase_requisition",
    response_model=ApiResponse[ps.PROut],
)
def submit_requisition(req_id: int, user: User = Depends(_REQ_SUBMIT), db: Session = Depends(get_db)):
    return ok(ps.PROut.model_validate(PurchaseRequisitionService(db).submit(req_id)).model_dump())


@router.post(
    "/purchase-requisitions/{req_id}/approve",
    name="approve_purchase_requisition",
    response_model=ApiResponse[ps.PROut],
)
def approve_requisition(req_id: int, user: User = Depends(_REQ_APPROVE), db: Session = Depends(get_db)):
    return ok(ps.PROut.model_validate(PurchaseRequisitionService(db).approve(req_id, user.id)).model_dump())


@router.post(
    "/purchase-requisitions/{req_id}/cancel",
    name="cancel_purchase_requisition",
    response_model=ApiResponse[ps.PROut],
)
def cancel_requisition(
    req_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_REQ_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ps.PROut.model_validate(PurchaseRequisitionService(db).cancel(req_id, user.id, reason)).model_dump())


@router.post(
    "/purchase-requisitions/{req_id}/convert-to-po",
    name="convert_purchase_requisition",
    response_model=ApiResponse[ps.POOut],
)
def convert_requisition(
    req_id: int,
    payload: ps.PRConvertIn,
    user: User = Depends(_REQ_START),
    db: Session = Depends(get_db),
):
    po = PurchaseRequisitionService(db).convert_to_po(req_id, payload, user.id)
    return ok(ps.POOut.model_validate(po).model_dump())


# ---------------- 采购订单 ----------------
@router.get("/purchase-orders", name="list_purchase_orders", response_model=ApiResponse[PageOut[ps.POOut]])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = PurchaseOrderService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ps.POOut.model_validate(x).model_dump() for x in items]})


@router.post("/purchase-orders", status_code=201, name="create_purchase_order", response_model=ApiResponse[ps.POOut])
def create_order(payload: ps.POCreate, user: User = Depends(_PO_MANAGE), db: Session = Depends(get_db)):
    return ok(ps.POOut.model_validate(PurchaseOrderService(db).create(payload, user.id)).model_dump())


@router.get("/purchase-orders/{po_id}", name="get_purchase_order", response_model=ApiResponse[ps.POOut])
def get_order(po_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ps.POOut.model_validate(PurchaseOrderService(db).get(po_id)).model_dump())


@router.put("/purchase-orders/{po_id}", name="update_purchase_order", response_model=ApiResponse[ps.POOut])
def update_order(
    po_id: int,
    payload: ps.POUpdate,
    user: User = Depends(_PO_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ps.POOut.model_validate(PurchaseOrderService(db).update(po_id, payload)).model_dump())


@router.delete("/purchase-orders/{po_id}", name="delete_purchase_order")
def delete_order(po_id: int, user: User = Depends(_PO_MANAGE), db: Session = Depends(get_db)):
    PurchaseOrderService(db).delete(po_id)
    return ok(None)


@router.post("/purchase-orders/{po_id}/confirm", name="confirm_purchase_order", response_model=ApiResponse[ps.POOut])
def confirm_order(po_id: int, user: User = Depends(_PO_CONFIRM), db: Session = Depends(get_db)):
    return ok(ps.POOut.model_validate(PurchaseOrderService(db).confirm(po_id, user.id)).model_dump())


@router.post("/purchase-orders/{po_id}/cancel", name="cancel_purchase_order", response_model=ApiResponse[ps.POOut])
def cancel_order(
    po_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_PO_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ps.POOut.model_validate(PurchaseOrderService(db).cancel(po_id, user.id, reason)).model_dump())


# ---------------- 到货/验收单 ----------------
@router.get(
    "/supplier-deliveries", name="list_supplier_deliveries", response_model=ApiResponse[PageOut[ps.DeliveryOut]]
)
def list_deliveries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = SupplierDeliveryService(db).list(page, page_size, status=status)
    return ok({"total": total, "items": [ps.DeliveryOut.model_validate(x).model_dump() for x in items]})


@router.post(
    "/supplier-deliveries", status_code=201, name="create_supplier_delivery", response_model=ApiResponse[ps.DeliveryOut]
)
def create_delivery(payload: ps.DeliveryCreate, user: User = Depends(_RCV_MANAGE), db: Session = Depends(get_db)):
    return ok(ps.DeliveryOut.model_validate(SupplierDeliveryService(db).create(payload, user.id)).model_dump())


@router.get(
    "/supplier-deliveries/{delivery_id}", name="get_supplier_delivery", response_model=ApiResponse[ps.DeliveryOut]
)
def get_delivery(delivery_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(ps.DeliveryOut.model_validate(SupplierDeliveryService(db).get(delivery_id)).model_dump())


@router.put(
    "/supplier-deliveries/{delivery_id}", name="update_supplier_delivery", response_model=ApiResponse[ps.DeliveryOut]
)
def update_delivery(
    delivery_id: int,
    payload: ps.DeliveryUpdate,
    user: User = Depends(_RCV_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ps.DeliveryOut.model_validate(SupplierDeliveryService(db).update(delivery_id, payload)).model_dump())


@router.delete("/supplier-deliveries/{delivery_id}", name="delete_supplier_delivery")
def delete_delivery(delivery_id: int, user: User = Depends(_RCV_MANAGE), db: Session = Depends(get_db)):
    SupplierDeliveryService(db).delete(delivery_id)
    return ok(None)


@router.post(
    "/supplier-deliveries/{delivery_id}/submit",
    name="submit_supplier_delivery",
    response_model=ApiResponse[ps.DeliveryOut],
)
def submit_delivery(delivery_id: int, user: User = Depends(_RCV_SUBMIT), db: Session = Depends(get_db)):
    return ok(ps.DeliveryOut.model_validate(SupplierDeliveryService(db).submit(delivery_id)).model_dump())


@router.post(
    "/supplier-deliveries/{delivery_id}/accept",
    name="accept_supplier_delivery",
    response_model=ApiResponse[ivs.InboundOrderOut],
)
def accept_delivery(
    delivery_id: int,
    payload: ivs.DeliveryAcceptIn,
    user: User = Depends(_RCV_ACCEPT),
    db: Session = Depends(get_db),
):
    inbound = InboundService(db).accept_delivery(delivery_id, payload, user.id)
    return ok(ivs.InboundOrderOut.model_validate(inbound).model_dump())


@router.post(
    "/supplier-deliveries/{delivery_id}/cancel",
    name="cancel_supplier_delivery",
    response_model=ApiResponse[ps.DeliveryOut],
)
def cancel_delivery(
    delivery_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_RCV_CANCEL),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(
        ps.DeliveryOut.model_validate(SupplierDeliveryService(db).cancel(delivery_id, user.id, reason)).model_dump()
    )
