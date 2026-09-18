"""台账与统计业务：库存预警扫描/处置、每日结存快照、供货价维护。"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.model.base import utcnow
from app.model.ledger import InventorySnapshotDaily, MaterialSupplierPrice, StockAlert
from app.repository.inventory import InventoryBatchRepo, InventoryRepo
from app.repository.ledger import InventorySnapshotRepo, MaterialSupplierPriceRepo, StockAlertRepo
from app.repository.master import MaterialRepo, SupplierRepo
from app.repository.purchase import POItemRepo

_NEAR_EXPIRY_DAYS = 30


class StockAlertService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = StockAlertRepo(db)

    def list(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        alert_type: str | None = None,
        material_id: int | None = None,
    ):
        return self.repo.list((page - 1) * page_size, page_size, status, alert_type, material_id)

    def get(self, alert_id: int) -> StockAlert:
        obj = self.repo.get_active(alert_id)
        if obj is None:
            raise NotFound("预警不存在")
        return obj

    def scan(self, operator_id: int | None = None) -> dict:
        """扫描生成预警；同物料/仓库/批次/类型未关闭（OPEN/ACKED）不重复。"""
        existing = self.repo.open_keys()
        created = 0
        scanned = 0

        materials = {m.id: m for m in MaterialRepo(self.db).list(0, 1_000_000)[0]}
        inventory_rows = InventoryRepo(self.db).list(0, 1_000_000)[0]
        for inv in inventory_rows:
            scanned += 1
            material = materials.get(inv.material_id)
            if material is None:
                continue
            available = inv.quantity - inv.locked_qty
            stock_alert = None
            if inv.quantity <= 0:
                stock_alert = ("OUT_OF_STOCK", "CRITICAL", material.safety_stock, inv.quantity, "库存为 0")
            elif material.safety_stock and available < material.safety_stock:
                stock_alert = (
                    "LOW_STOCK",
                    "WARN",
                    material.safety_stock,
                    available,
                    "可用量低于安全库存",
                )
            elif material.max_stock is not None and inv.quantity > material.max_stock:
                stock_alert = ("OVER_STOCK", "INFO", material.max_stock, inv.quantity, "库存超过上限")
            if stock_alert is None:
                continue
            alert_type, level, threshold, current, message = stock_alert
            key = (inv.material_id, inv.warehouse_id, 0, alert_type)
            if key in existing:
                continue
            self.repo.add(
                self._build(
                    material.id, inv.warehouse_id, None, alert_type, level, threshold, current, message, operator_id
                )
            )
            existing.add(key)
            created += 1

        today = date.today()
        for batch in InventoryBatchRepo(self.db).list(0, 1_000_000)[0]:
            if batch.expiry_date is None or batch.quantity <= 0:
                continue
            scanned += 1
            if batch.expiry_date < today:
                alert_type, level = "EXPIRED", "CRITICAL"
            elif (batch.expiry_date - today).days <= _NEAR_EXPIRY_DAYS:
                alert_type, level = "NEAR_EXPIRY", "WARN"
            else:
                continue
            key = (batch.material_id, batch.warehouse_id, batch.id, alert_type)
            if key in existing:
                continue
            message = "批次 %s %s（到期 %s）" % (batch.batch_no, alert_type, batch.expiry_date.isoformat())
            self.repo.add(
                self._build(
                    batch.material_id,
                    batch.warehouse_id,
                    batch.id,
                    alert_type,
                    level,
                    Decimal(_NEAR_EXPIRY_DAYS),
                    batch.quantity,
                    message,
                    operator_id,
                )
            )
            existing.add(key)
            created += 1

        self.db.commit()
        return {"scanned": scanned, "created": created}

    def _build(self, material_id, warehouse_id, batch_id, alert_type, level, threshold, current, message, operator_id):
        return StockAlert(
            material_id=material_id,
            warehouse_id=warehouse_id,
            batch_id=batch_id,
            alert_type=alert_type,
            level=level,
            status="OPEN",
            threshold=threshold,
            current_value=current,
            message=message,
            created_by=operator_id,
        )

    def ack(self, alert_id: int, operator_id: int) -> StockAlert:
        obj = self.get(alert_id)
        obj.status = "ACKED"
        obj.acked_by = operator_id
        obj.acked_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def resolve(self, alert_id: int) -> StockAlert:
        obj = self.get(alert_id)
        obj.status = "RESOLVED"
        obj.resolved_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def ignore(self, alert_id: int, reason: str | None = None) -> StockAlert:
        obj = self.get(alert_id)
        obj.status = "IGNORED"
        if reason:
            obj.remark = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj


class InventorySnapshotService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventorySnapshotRepo(db)

    def list(self, page: int, page_size: int, snapshot_date: date | None = None, material_id: int | None = None):
        return self.repo.list((page - 1) * page_size, page_size, snapshot_date, material_id)

    def generate(self, snapshot_date: date | None = None) -> dict:
        """生成/重算某日结存快照（物资×仓库×日），当日可重复执行（upsert）。"""
        day = snapshot_date or date.today()
        inventory_rows = InventoryRepo(self.db).list(0, 1_000_000)[0]
        in_transit = POItemRepo(self.db).in_transit_by_material()
        created = 0
        updated = 0
        for inv in inventory_rows:
            row = self.repo.get(day, inv.material_id, inv.warehouse_id)
            if row is None:
                row = InventorySnapshotDaily(
                    snapshot_date=day,
                    material_id=inv.material_id,
                    warehouse_id=inv.warehouse_id,
                )
                self.repo.add(row)
                created += 1
            else:
                updated += 1
            row.quantity = inv.quantity
            row.locked_qty = inv.locked_qty
            row.in_transit_qty = Decimal(str(in_transit.get(inv.material_id, 0)))
        self.db.commit()
        return {"snapshot_date": day, "created": created, "updated": updated}


class MaterialSupplierPriceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MaterialSupplierPriceRepo(db)

    def list(self, page: int, page_size: int, material_id: int | None = None, supplier_id: int | None = None):
        return self.repo.list((page - 1) * page_size, page_size, material_id, supplier_id)

    def get(self, price_id: int) -> MaterialSupplierPrice:
        obj = self.repo.get_active(price_id)
        if obj is None:
            raise NotFound("供货价不存在")
        return obj

    def create(self, payload, operator_id: int) -> MaterialSupplierPrice:
        self._require_refs(payload.material_id, payload.supplier_id)
        if self.repo.find_pair(payload.material_id, payload.supplier_id) is not None:
            raise Conflict("该物资+供应商的供货价已存在")
        obj = MaterialSupplierPrice(**payload.model_dump(), created_by=operator_id)
        if payload.is_preferred:
            self._clear_preferred(payload.material_id, None)
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, price_id: int, payload) -> MaterialSupplierPrice:
        obj = self.get(price_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("is_preferred") is True:
            self._clear_preferred(obj.material_id, obj.id)
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, price_id: int) -> None:
        obj = self.get(price_id)
        obj.deleted_at = utcnow()
        self.db.commit()

    def _require_refs(self, material_id: int, supplier_id: int) -> None:
        if MaterialRepo(self.db).get_active(material_id) is None:
            raise BadRequest("物资不存在：" + str(material_id))
        if SupplierRepo(self.db).get_active(supplier_id) is None:
            raise BadRequest("供应商不存在：" + str(supplier_id))

    def _clear_preferred(self, material_id: int, exclude_id: int | None) -> None:
        for row in self.repo.list_preferred(material_id, exclude_id):
            row.is_preferred = False
        self.db.flush()
