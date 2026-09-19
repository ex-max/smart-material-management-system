from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.schema import ledger as ls
from app.schema import purchase as ps
from app.schema.common import ApiResponse, PageOut
from app.service.ledger import InventorySnapshotService, MaterialSupplierPriceService, StockAlertService

router = APIRouter(tags=["台账"])

_ALERT_VIEW = require_perm(Perm.INVENTORY_VIEW)
_ALERT_MANAGE = require_perm(Perm.INVENTORY_MANAGE)
_PRICE_VIEW = require_perm(Perm.PURCHASE_VIEW)
_PRICE_MANAGE = require_perm(Perm.PURCHASE_MANAGE)


# ---------------- 库存预警 ----------------
@router.get("/stock-alerts", name="list_stock_alerts", response_model=ApiResponse[PageOut[ls.StockAlertOut]])
def list_stock_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    alert_type: str | None = Query(None),
    material_id: int | None = Query(None),
    user: User = Depends(_ALERT_VIEW),
    db: Session = Depends(get_db),
):
    items, total = StockAlertService(db).list(page, page_size, status, alert_type, material_id)
    return ok({"total": total, "items": [ls.StockAlertOut.model_validate(x).model_dump() for x in items]})


@router.post("/stock-alerts/scan", name="scan_stock_alerts", response_model=ApiResponse[ls.ScanResult])
def scan_stock_alerts(user: User = Depends(_ALERT_MANAGE), db: Session = Depends(get_db)):
    return ok(StockAlertService(db).scan(user.id))


@router.get("/stock-alerts/{alert_id}", name="get_stock_alert", response_model=ApiResponse[ls.StockAlertOut])
def get_stock_alert(alert_id: int, user: User = Depends(_ALERT_VIEW), db: Session = Depends(get_db)):
    return ok(ls.StockAlertOut.model_validate(StockAlertService(db).get(alert_id)).model_dump())


@router.post("/stock-alerts/{alert_id}/ack", name="ack_stock_alert", response_model=ApiResponse[ls.StockAlertOut])
def ack_stock_alert(alert_id: int, user: User = Depends(_ALERT_MANAGE), db: Session = Depends(get_db)):
    return ok(ls.StockAlertOut.model_validate(StockAlertService(db).ack(alert_id, user.id)).model_dump())


@router.post("/stock-alerts/{alert_id}/resolve", name="resolve_stock_alert", response_model=ApiResponse[ls.StockAlertOut])
def resolve_stock_alert(alert_id: int, user: User = Depends(_ALERT_MANAGE), db: Session = Depends(get_db)):
    return ok(ls.StockAlertOut.model_validate(StockAlertService(db).resolve(alert_id)).model_dump())


@router.post("/stock-alerts/{alert_id}/ignore", name="ignore_stock_alert", response_model=ApiResponse[ls.StockAlertOut])
def ignore_stock_alert(
    alert_id: int,
    payload: ps.CancelIn | None = None,
    user: User = Depends(_ALERT_MANAGE),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(ls.StockAlertOut.model_validate(StockAlertService(db).ignore(alert_id, reason)).model_dump())


# ---------------- 每日结存快照 ----------------
@router.get(
    "/inventory-snapshots",
    name="list_inventory_snapshots",
    response_model=ApiResponse[PageOut[ls.InventorySnapshotOut]],
)
def list_inventory_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    snapshot_date: str | None = Query(None),
    material_id: int | None = Query(None),
    user: User = Depends(_ALERT_VIEW),
    db: Session = Depends(get_db),
):
    parsed = None
    if snapshot_date is not None:
        try:
            parsed = __import__("datetime").date.fromisoformat(snapshot_date)
        except ValueError as exc:
            from app.core.errors import BadRequest

            raise BadRequest("snapshot_date 需为 YYYY-MM-DD") from exc
    items, total = InventorySnapshotService(db).list(page, page_size, parsed, material_id)
    return ok({"total": total, "items": [ls.InventorySnapshotOut.model_validate(x).model_dump() for x in items]})


@router.post("/inventory-snapshots/generate", name="generate_inventory_snapshots", response_model=ApiResponse[ls.SnapshotResult])
def generate_inventory_snapshots(
    snapshot_date: str | None = Query(None),
    user: User = Depends(_ALERT_MANAGE),
    db: Session = Depends(get_db),
):
    from datetime import date as _date

    parsed = _date.fromisoformat(snapshot_date) if snapshot_date else None
    result = InventorySnapshotService(db).generate(parsed)
    return ok(ls.SnapshotResult.model_validate(result).model_dump())


# ---------------- 供货价 ----------------
@router.get(
    "/material-supplier-prices",
    name="list_material_supplier_prices",
    response_model=ApiResponse[PageOut[ls.MaterialSupplierPriceOut]],
)
def list_material_supplier_prices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    material_id: int | None = Query(None),
    supplier_id: int | None = Query(None),
    user: User = Depends(_PRICE_VIEW),
    db: Session = Depends(get_db),
):
    items, total = MaterialSupplierPriceService(db).list(page, page_size, material_id, supplier_id)
    return ok({"total": total, "items": [ls.MaterialSupplierPriceOut.model_validate(x).model_dump() for x in items]})


@router.post(
    "/material-supplier-prices",
    status_code=201,
    name="create_material_supplier_price",
    response_model=ApiResponse[ls.MaterialSupplierPriceOut],
)
def create_material_supplier_price(
    payload: ls.MaterialSupplierPriceCreate, user: User = Depends(_PRICE_MANAGE), db: Session = Depends(get_db)
):
    return ok(ls.MaterialSupplierPriceOut.model_validate(MaterialSupplierPriceService(db).create(payload, user.id)).model_dump())


@router.get(
    "/material-supplier-prices/{price_id}",
    name="get_material_supplier_price",
    response_model=ApiResponse[ls.MaterialSupplierPriceOut],
)
def get_material_supplier_price(price_id: int, user: User = Depends(_PRICE_VIEW), db: Session = Depends(get_db)):
    return ok(ls.MaterialSupplierPriceOut.model_validate(MaterialSupplierPriceService(db).get(price_id)).model_dump())


@router.put(
    "/material-supplier-prices/{price_id}",
    name="update_material_supplier_price",
    response_model=ApiResponse[ls.MaterialSupplierPriceOut],
)
def update_material_supplier_price(
    price_id: int,
    payload: ls.MaterialSupplierPriceUpdate,
    user: User = Depends(_PRICE_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ls.MaterialSupplierPriceOut.model_validate(MaterialSupplierPriceService(db).update(price_id, payload)).model_dump())


@router.delete("/material-supplier-prices/{price_id}", name="delete_material_supplier_price")
def delete_material_supplier_price(price_id: int, user: User = Depends(_PRICE_MANAGE), db: Session = Depends(get_db)):
    MaterialSupplierPriceService(db).delete(price_id)
    return ok(None)
