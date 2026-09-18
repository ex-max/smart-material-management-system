"""库存业务：到货验收 → 生成入库单 → 过账（流水 + 结存）→ 回写采购订单；库存查询与对账。

领域不变量 1：余额只能由流水推导。本模块是唯一允许写 inventory / inventory_batch.quantity
的地方，且每条结存变更都必须在同一事务内写一条 inventory_transaction。
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotFound
from app.core.state_machine import Actions, DocStatus, DocTypes, apply_transition, can, require_transition
from app.model.base import utcnow
from app.model.inventory import (
    BATCH_DEFAULT_NO,
    InboundItem,
    InboundOrder,
    Inventory,
    InventoryBatch,
    InventoryTransaction,
)
from app.model.purchase import POItem
from app.repository.inventory import (
    InboundItemRepo,
    InboundOrderRepo,
    InventoryBatchRepo,
    InventoryBatchSumRepo,
    InventoryRepo,
    InventoryTransactionRepo,
)
from app.repository.master import LocationRepo, MaterialRepo, WarehouseRepo
from app.repository.purchase import POItemRepo, PurchaseOrderRepo, SupplierDeliveryItemRepo, SupplierDeliveryRepo

_MONEY = Decimal("0.0001")
_SNAPSHOT_FIELDS = ("material_id", "material_code", "material_name", "spec", "unit_name")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _dec(value) -> Decimal:
    return Decimal("0") if value is None else Decimal(str(value))


class InboundService:
    doc_type = DocTypes.INBOUND_ORDER
    label = "入库单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InboundOrderRepo(db)
        self.item_repo = InboundItemRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, inbound_id: int) -> InboundOrder:
        obj = self.repo.get_active(inbound_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def accept_delivery(self, delivery_id: int, payload, operator_id: int) -> InboundOrder:
        """到货单验收通过：记录验收结论并生成入库单（草稿，待过账）。"""
        delivery = SupplierDeliveryRepo(self.db).get_active(delivery_id)
        if delivery is None:
            raise NotFound("到货单不存在")
        require_transition(DocTypes.SUPPLIER_DELIVERY, Actions.ACCEPT, delivery.status)
        warehouse = WarehouseRepo(self.db).get_active(payload.warehouse_id)
        if warehouse is None:
            raise BadRequest("入库仓库不存在：" + str(payload.warehouse_id))
        if payload.location_id is not None:
            location = LocationRepo(self.db).get_active(payload.location_id)
            if location is None or location.warehouse_id != warehouse.id:
                raise BadRequest("入库库位不存在或不属于该仓库")
        delivery_items = SupplierDeliveryItemRepo(self.db).list_by_delivery(delivery.id)
        if not delivery_items:
            raise BadRequest("到货单没有明细")

        overrides = {row.delivery_item_id: row for row in payload.items}
        unknown = set(overrides) - {row.id for row in delivery_items}
        if unknown:
            raise BadRequest("到货行不属于该到货单：" + ",".join(str(x) for x in sorted(unknown)))

        inbound = InboundOrder(
            doc_no=self.repo.next_doc_no(),
            source_type="PURCHASE",
            source_id=delivery.id,
            delivery_id=delivery.id,
            warehouse_id=warehouse.id,
            status=DocStatus.DRAFT,
            remark=payload.remark,
            created_by=operator_id,
        )
        inbound.items = []
        total = Decimal("0")
        line_no = 0
        for row in delivery_items:
            override = overrides.get(row.id)
            rejected = _override(override, "rejected_qty", row.rejected_qty)
            if rejected is None:
                rejected = Decimal("0")
            accepted = _override(override, "accepted_qty", row.accepted_qty)
            if accepted is None:
                accepted = row.quantity - rejected
            if accepted < 0 or rejected < 0 or accepted + rejected > row.quantity:
                raise BadRequest("到货行 %d 的合格数量 + 拒收数量超过到货数量" % row.line_no)
            inspection = (override.inspection_result if override and override.inspection_result else row.inspection_result)
            row.accepted_qty = accepted
            row.rejected_qty = rejected
            row.inspection_result = inspection or ("PASS" if accepted == row.quantity else "CONCESSION")
            if accepted == 0:
                continue
            po_item = self.db.get(POItem, row.po_item_id)
            unit_price = po_item.unit_price if po_item is not None else Decimal("0")
            amount = _money(accepted * unit_price)
            line_no += 1
            inbound.items.append(
                InboundItem(
                    line_no=line_no,
                    quantity=accepted,
                    unit_price=unit_price,
                    amount=amount,
                    batch_no=row.batch_no or BATCH_DEFAULT_NO,
                    production_date=row.production_date,
                    expiry_date=row.expiry_date,
                    location_id=payload.location_id,
                    po_item_id=row.po_item_id,
                    remark=(override.remark if override and override.remark else row.remark),
                    **{field: getattr(row, field) for field in _SNAPSHOT_FIELDS},
                )
            )
            total += amount
        if not inbound.items:
            raise BadRequest("验收合格数量为 0，无需生成入库单（请作废到货单）")
        inbound.total_amount = _money(total)
        self.repo.add(inbound)

        apply_transition(delivery, DocTypes.SUPPLIER_DELIVERY, Actions.ACCEPT)
        delivery.inspected_by = operator_id
        delivery.inspected_at = utcnow()
        self.db.commit()
        self.db.refresh(inbound)
        return inbound

    def post(self, inbound_id: int, operator_id: int) -> InboundOrder:
        """过账：写库存流水 + 同事务更新结存，回写 po_item.received_qty 与采购订单状态。"""
        inbound = self.get(inbound_id)
        require_transition(self.doc_type, Actions.START, inbound.status)
        if not inbound.items:
            raise BadRequest("入库单没有明细")

        po_ids: set[int] = set()
        for item in inbound.items:
            self._stock_in(inbound, item, operator_id)
            if item.po_item_id is not None:
                po_item = self.db.get(POItem, item.po_item_id)
                if po_item is None:
                    raise BadRequest("来源采购订单行不存在：" + str(item.po_item_id))
                if po_item.received_qty + item.quantity > po_item.quantity:
                    raise BadRequest("入库数量超过采购订单行未交量：" + str(po_item.id))
                po_item.received_qty = po_item.received_qty + item.quantity
                po_ids.add(po_item.po_id)

        apply_transition(inbound, self.doc_type, Actions.START)
        inbound.inbound_by = operator_id
        inbound.inbound_at = utcnow()
        for po_id in po_ids:
            self._sync_po_status(po_id)
        if inbound.delivery_id is not None:
            delivery = SupplierDeliveryRepo(self.db).get_active(inbound.delivery_id)
            if delivery is not None and can(DocTypes.SUPPLIER_DELIVERY, Actions.COMPLETE, delivery.status):
                apply_transition(delivery, DocTypes.SUPPLIER_DELIVERY, Actions.COMPLETE)
        self.db.commit()
        self.db.refresh(inbound)
        return inbound

    def complete(self, inbound_id: int) -> InboundOrder:
        inbound = self.get(inbound_id)
        apply_transition(inbound, self.doc_type, Actions.COMPLETE)
        self.db.commit()
        self.db.refresh(inbound)
        return inbound

    def cancel(self, inbound_id: int, reason: str | None) -> InboundOrder:
        inbound = self.get(inbound_id)
        apply_transition(inbound, self.doc_type, Actions.CANCEL)
        inbound.cancel_reason = reason
        self.db.commit()
        self.db.refresh(inbound)
        return inbound

    def _stock_in(self, inbound: InboundOrder, item: InboundItem, operator_id: int) -> None:
        material_id = item.material_id
        warehouse_id = inbound.warehouse_id
        batch_no = item.batch_no or BATCH_DEFAULT_NO
        qty = item.quantity

        batch_repo = InventoryBatchRepo(self.db)
        batch = batch_repo.get_grain(material_id, warehouse_id, batch_no, for_update=True)
        if batch is None:
            MaterialRepo(self.db).get(material_id)  # 外键校验（缺失时 DB 会报错，这里提前 400）
            batch = InventoryBatch(
                material_id=material_id,
                warehouse_id=warehouse_id,
                batch_no=batch_no,
                is_default=batch_no == BATCH_DEFAULT_NO,
                production_date=item.production_date,
                expiry_date=item.expiry_date,
                inbound_date=date.today(),
                quantity=Decimal("0"),
                status="NORMAL",
                created_by=operator_id,
            )
            batch_repo.add(batch)
        batch.quantity = batch.quantity + qty
        if batch.inbound_date is None:
            batch.inbound_date = date.today()
        item.batch_id = batch.id

        inventory_repo = InventoryRepo(self.db)
        inventory = inventory_repo.get_grain(material_id, warehouse_id, for_update=True)
        if inventory is None:
            inventory = Inventory(
                material_id=material_id,
                warehouse_id=warehouse_id,
                quantity=Decimal("0"),
                locked_qty=Decimal("0"),
                version=0,
                created_by=operator_id,
            )
            inventory_repo.add(inventory)
        inventory.quantity = inventory.quantity + qty
        inventory.version = inventory.version + 1
        inventory.last_txn_at = utcnow()

        InventoryTransactionRepo(self.db).add(
            InventoryTransaction(
                idem_key="INBOUND:%d:%d" % (inbound.id, item.line_no),
                material_id=material_id,
                warehouse_id=warehouse_id,
                batch_id=batch.id,
                quantity=qty,
                txn_type="INBOUND",
                source_type="INBOUND",
                source_id=inbound.id,
                source_no=inbound.doc_no,
                source_line_id=item.id,
                balance_after=batch.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
                created_by=operator_id,
            )
        )

    def _sync_po_status(self, po_id: int) -> None:
        po = PurchaseOrderRepo(self.db).get_active(po_id)
        if po is None:
            return
        items = POItemRepo(self.db).list_by_po(po_id)
        if not items:
            return
        if any(i.received_qty > 0 for i in items) and can(DocTypes.PURCHASE_ORDER, Actions.START, po.status):
            apply_transition(po, DocTypes.PURCHASE_ORDER, Actions.START)
        if all(i.received_qty >= i.quantity for i in items) and can(
            DocTypes.PURCHASE_ORDER, Actions.COMPLETE, po.status
        ):
            apply_transition(po, DocTypes.PURCHASE_ORDER, Actions.COMPLETE)


def _override(override, field, fallback):
    if override is not None:
        value = getattr(override, field)
        if value is not None:
            return value
    return fallback


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_inventory(self, page: int, page_size: int, material_id: int | None = None, warehouse_id: int | None = None):
        return InventoryRepo(self.db).list((page - 1) * page_size, page_size, material_id, warehouse_id)

    def list_batches(self, page: int, page_size: int, material_id: int | None = None, warehouse_id: int | None = None):
        return InventoryBatchRepo(self.db).list((page - 1) * page_size, page_size, material_id, warehouse_id)

    def list_transactions(
        self,
        page: int,
        page_size: int,
        material_id: int | None = None,
        warehouse_id: int | None = None,
        source_type: str | None = None,
    ):
        return InventoryTransactionRepo(self.db).list(
            (page - 1) * page_size, page_size, material_id, warehouse_id, source_type
        )

    def reconcile(self) -> dict:
        """库存对账（docs/db-schema.md §14.3 四条检查），差异用于告警/阻断。"""
        rows = InventoryRepo(self.db).list(0, 1_000_000)[0]
        batch_sum = InventoryBatchSumRepo(self.db).sum_by_material_warehouse()
        txn_sum = InventoryTransactionRepo(self.db).sum_by_material_warehouse()
        batch_txn = InventoryBatchSumRepo(self.db).sum_by_batch()
        batches = InventoryBatchRepo(self.db).list(0, 1_000_000)[0]

        inventory_vs_batch: list[dict] = []
        inventory_vs_txn: list[dict] = []
        for inv in rows:
            key = (inv.material_id, inv.warehouse_id)
            batch_qty = _dec(batch_sum.get(key))
            txn_qty = _dec(txn_sum.get(key))
            if inv.quantity != batch_qty:
                inventory_vs_batch.append(
                    {
                        "material_id": inv.material_id,
                        "warehouse_id": inv.warehouse_id,
                        "inventory_qty": str(inv.quantity),
                        "batch_sum": str(batch_qty),
                    }
                )
            if inv.quantity != txn_qty:
                inventory_vs_txn.append(
                    {
                        "material_id": inv.material_id,
                        "warehouse_id": inv.warehouse_id,
                        "inventory_qty": str(inv.quantity),
                        "txn_sum": str(txn_qty),
                    }
                )
        batch_vs_txn: list[dict] = []
        for batch in batches:
            txn_qty = _dec(batch_txn.get(batch.id))
            if batch.quantity != txn_qty:
                batch_vs_txn.append(
                    {
                        "material_id": batch.material_id,
                        "warehouse_id": batch.warehouse_id,
                        "batch_no": batch.batch_no,
                        "batch_qty": str(batch.quantity),
                        "txn_sum": str(txn_qty),
                    }
                )
        negative_or_locked = [
            {"material_id": i.material_id, "warehouse_id": i.warehouse_id, "quantity": str(i.quantity)}
            for i in rows
            if i.quantity < 0 or i.quantity < i.locked_qty
        ]
        return {
            "inventory_vs_batch": inventory_vs_batch,
            "inventory_vs_txn": inventory_vs_txn,
            "batch_vs_txn": batch_vs_txn,
            "negative_or_locked": negative_or_locked,
            "ok": not (inventory_vs_batch or inventory_vs_txn or batch_vs_txn or negative_or_locked),
        }
