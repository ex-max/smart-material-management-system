"""库存作业业务：出库 / 调拨 / 盘点 的建单、过账与红冲。

余额变更一律走 StockLedger（唯一入口）；出库校验可用量、调拨两仓各写一条流水、
盘点按差异写盘盈/盘亏，红冲用 REVERSAL 反向流水，不改/删历史流水。
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotEditable, NotFound
from app.core.state_machine import Actions, DocStatus, DocTypes, apply_transition, can, require_transition
from app.model.base import utcnow
from app.model.inventory import BATCH_DEFAULT_NO, InboundItem, InboundOrder, InventoryBatch
from app.model.inventory_ops import (
    OutboundItem,
    OutboundOrder,
    StocktakeItem,
    StocktakeOrder,
    TransferItem,
    TransferOrder,
)
from app.repository.inventory import InboundOrderRepo, InventoryBatchRepo
from app.repository.inventory_ops import (
    OutboundOrderRepo,
    StocktakeItemRepo,
    StocktakeOrderRepo,
    TransferOrderRepo,
)
from app.repository.master import MaterialRepo, UnitRepo, WarehouseRepo
from app.repository.user import UserRepository
from app.service.stock_ledger import StockLedger

_MONEY = Decimal("0.0001")
_SNAPSHOT_FIELDS = ("material_id", "material_code", "material_name", "spec", "unit_name")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _load_material(db: Session, material_id: int):
    material = MaterialRepo(db).get_active(material_id)
    if material is None:
        raise BadRequest("物资不存在：" + str(material_id))
    return material


def _snapshot(db: Session, material_id: int) -> dict:
    material = _load_material(db, material_id)
    unit = UnitRepo(db).get(material.unit_id)
    return {
        "material_id": material.id,
        "material_code": material.code,
        "material_name": material.name,
        "spec": material.spec,
        "unit_name": unit.name if unit is not None else "",
    }


def _require_user(db: Session, user_id: int | None, label: str) -> None:
    if user_id is not None and UserRepository(db).get(user_id) is None:
        raise BadRequest(label + "不存在")


def _require_warehouse(db: Session, warehouse_id: int) -> None:
    if WarehouseRepo(db).get_active(warehouse_id) is None:
        raise BadRequest("仓库不存在：" + str(warehouse_id))


def _resolve_batch(db: Session, material, warehouse_id: int, batch_id, batch_no):
    """返回 (batch_id, batch_no, production_date, expiry_date)；批次物资必须能定位批次。"""
    if batch_id is not None:
        batch = db.get(InventoryBatch, batch_id)
        if batch is None or batch.deleted_at is not None:
            raise BadRequest("批次不存在：" + str(batch_id))
        if batch.material_id != material.id or batch.warehouse_id != warehouse_id:
            raise BadRequest("批次不属于该物资/仓库：" + str(batch_id))
        return batch.id, batch.batch_no, batch.production_date, batch.expiry_date
    if batch_no:
        batch = InventoryBatchRepo(db).get_grain(material.id, warehouse_id, batch_no)
        if batch is not None:
            return batch.id, batch.batch_no, batch.production_date, batch.expiry_date
        if material.is_batch_managed:
            raise BadRequest("批次不存在（批次物资）：" + batch_no)
    if material.is_batch_managed:
        raise BadRequest("批次物资必须指定 batch_id 或 batch_no：" + material.code)
    return None, BATCH_DEFAULT_NO, None, None


# ---------------- 出库单 ----------------
class OutboundService:
    doc_type = DocTypes.OUTBOUND_ORDER
    label = "出库单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OutboundOrderRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, outbound_id: int) -> OutboundOrder:
        obj = self.repo.get_active(outbound_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def _build_item(self, data, line_no: int) -> OutboundItem:
        return OutboundItem(
            line_no=line_no,
            quantity=data.quantity,
            batch_id=data.batch_id,
            location_id=data.location_id,
            unit_price=data.unit_price,
            amount=_money(data.quantity * data.unit_price),
            remark=data.remark,
            **_snapshot(self.db, data.material_id),
        )

    def create(self, payload, operator_id: int) -> OutboundOrder:
        _require_warehouse(self.db, payload.warehouse_id)
        if payload.source_type == "TRANSFER":
            raise BadRequest("调拨出库请通过调拨单生成")
        _require_user(self.db, payload.receiver_id, "领用人")
        obj = OutboundOrder(
            doc_no=self.repo.next_doc_no(),
            source_type=payload.source_type,
            warehouse_id=payload.warehouse_id,
            receiver_id=payload.receiver_id,
            dept_name=payload.dept_name,
            status=DocStatus.DRAFT,
            remark=payload.remark,
            created_by=operator_id,
            items=[self._build_item(item, idx) for idx, item in enumerate(payload.items, start=1)],
        )
        obj.total_amount = _money(sum((item.amount for item in obj.items), Decimal("0")))
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, outbound_id: int, payload) -> OutboundOrder:
        obj = self.get(outbound_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的出库单可修改，当前：" + obj.status)
        data = payload.model_dump(exclude_unset=True, exclude={"items"})
        if "receiver_id" in data:
            _require_user(self.db, data["receiver_id"], "领用人")
        for key, value in data.items():
            setattr(obj, key, value)
        if "items" in payload.model_fields_set:
            items = payload.items or []
            if not items:
                raise BadRequest("出库单至少需要一行明细")
            obj.items.clear()
            for idx, item in enumerate(items, start=1):
                obj.items.append(self._build_item(item, idx))
        obj.total_amount = _money(sum((item.amount for item in obj.items), Decimal("0")))
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, outbound_id: int) -> None:
        obj = self.get(outbound_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的出库单可删除，当前：" + obj.status)
        obj.deleted_at = utcnow()
        self.db.commit()

    def post(self, outbound_id: int, operator_id: int) -> OutboundOrder:
        obj = self.get(outbound_id)
        require_transition(self.doc_type, Actions.START, obj.status)
        if not obj.items:
            raise BadRequest("出库单没有明细")
        ledger = StockLedger(self.db)
        for item in obj.items:
            material = _load_material(self.db, item.material_id)
            batch_id, batch_no, _, _ = _resolve_batch(self.db, material, obj.warehouse_id, item.batch_id, None)
            batch = ledger.change(
                key="OUTBOUND:%d:%d" % (obj.id, item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.warehouse_id,
                delta=-item.quantity,
                txn_type="OUTBOUND",
                source_type="OUTBOUND",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=item.id,
                operator_id=operator_id,
                unit_price=item.unit_price,
                amount=item.amount,
                batch_id=batch_id,
                batch_no=None if batch_id else batch_no,
            )
            item.batch_id = batch.id
        apply_transition(obj, self.doc_type, Actions.START)
        obj.outbound_by = operator_id
        obj.outbound_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def complete(self, outbound_id: int) -> OutboundOrder:
        obj = self.get(outbound_id)
        apply_transition(obj, self.doc_type, Actions.COMPLETE)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def cancel(self, outbound_id: int, reason: str | None) -> OutboundOrder:
        obj = self.get(outbound_id)
        apply_transition(obj, self.doc_type, Actions.CANCEL)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def reverse(self, outbound_id: int, operator_id: int, reason: str | None) -> OutboundOrder:
        obj = self.get(outbound_id)
        if obj.transfer_order_id is not None:
            raise BadRequest("调拨生成的出库单请通过调拨单红冲")
        require_transition(self.doc_type, Actions.REVERSE, obj.status)
        ledger = StockLedger(self.db)
        for item in obj.items:
            material = _load_material(self.db, item.material_id)
            batch_id, batch_no, _, _ = _resolve_batch(self.db, material, obj.warehouse_id, item.batch_id, None)
            ledger.change(
                key="OUTBOUND_REV:%d:%d" % (obj.id, item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.warehouse_id,
                delta=item.quantity,
                txn_type="REVERSAL",
                source_type="OUTBOUND",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=item.id,
                operator_id=operator_id,
                unit_price=item.unit_price,
                amount=item.amount,
                batch_id=batch_id,
                batch_no=None if batch_id else batch_no,
            )
        apply_transition(obj, self.doc_type, Actions.REVERSE)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ---------------- 调拨单 ----------------
class TransferService:
    doc_type = DocTypes.TRANSFER_ORDER
    label = "调拨单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TransferOrderRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, transfer_id: int) -> TransferOrder:
        obj = self.repo.get_active(transfer_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def _build_item(self, data, line_no: int, from_warehouse_id: int) -> TransferItem:
        material = _load_material(self.db, data.material_id)
        batch_id, _, _, _ = _resolve_batch(self.db, material, from_warehouse_id, data.batch_id, data.batch_no)
        return TransferItem(
            line_no=line_no,
            quantity=data.quantity,
            batch_id=batch_id,
            from_location_id=data.from_location_id,
            to_location_id=data.to_location_id,
            remark=data.remark,
            **_snapshot(self.db, data.material_id),
        )

    def create(self, payload, operator_id: int) -> TransferOrder:
        _require_warehouse(self.db, payload.from_warehouse_id)
        _require_warehouse(self.db, payload.to_warehouse_id)
        if payload.from_warehouse_id == payload.to_warehouse_id:
            raise BadRequest("调出仓库与调入仓库不能相同")
        _require_user(self.db, payload.applicant_id, "申请人")
        obj = TransferOrder(
            doc_no=self.repo.next_doc_no(),
            from_warehouse_id=payload.from_warehouse_id,
            to_warehouse_id=payload.to_warehouse_id,
            status=DocStatus.DRAFT,
            applicant_id=payload.applicant_id or operator_id,
            transfer_date=payload.transfer_date or date.today(),
            remark=payload.remark,
            created_by=operator_id,
            items=[
                self._build_item(item, idx, payload.from_warehouse_id)
                for idx, item in enumerate(payload.items, start=1)
            ],
        )
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, transfer_id: int, payload) -> TransferOrder:
        obj = self.get(transfer_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的调拨单可修改，当前：" + obj.status)
        data = payload.model_dump(exclude_unset=True, exclude={"items"})
        if "applicant_id" in data:
            _require_user(self.db, data["applicant_id"], "申请人")
        for key, value in data.items():
            setattr(obj, key, value)
        if "items" in payload.model_fields_set:
            items = payload.items or []
            if not items:
                raise BadRequest("调拨单至少需要一行明细")
            obj.items.clear()
            for idx, item in enumerate(items, start=1):
                obj.items.append(self._build_item(item, idx, obj.from_warehouse_id))
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, transfer_id: int) -> None:
        obj = self.get(transfer_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的调拨单可删除，当前：" + obj.status)
        obj.deleted_at = utcnow()
        self.db.commit()

    def post(self, transfer_id: int, operator_id: int) -> TransferOrder:
        obj = self.get(transfer_id)
        require_transition(self.doc_type, Actions.START, obj.status)
        if not obj.items:
            raise BadRequest("调拨单没有明细")

        out_order = OutboundOrder(
            doc_no=OutboundOrderRepo(self.db).next_doc_no(),
            source_type="TRANSFER",
            source_id=obj.id,
            transfer_order_id=obj.id,
            warehouse_id=obj.from_warehouse_id,
            status=DocStatus.DRAFT,
            remark="调拨生成出库",
            created_by=operator_id,
        )
        in_order = InboundOrder(
            doc_no=InboundOrderRepo(self.db).next_doc_no(),
            source_type="TRANSFER",
            source_id=obj.id,
            transfer_order_id=obj.id,
            warehouse_id=obj.to_warehouse_id,
            status=DocStatus.DRAFT,
            remark="调拨生成入库",
            created_by=operator_id,
        )
        out_order.items = []
        in_order.items = []
        pairs = []
        for idx, item in enumerate(obj.items, start=1):
            material = _load_material(self.db, item.material_id)
            batch_id, batch_no, production_date, expiry_date = _resolve_batch(
                self.db, material, obj.from_warehouse_id, item.batch_id, None
            )
            snap = {field: getattr(item, field) for field in _SNAPSHOT_FIELDS}
            out_item = OutboundItem(
                line_no=idx, quantity=item.quantity, batch_id=batch_id, unit_price=Decimal("0"), amount=Decimal("0"), **snap
            )
            in_item = InboundItem(
                line_no=idx,
                quantity=item.quantity,
                unit_price=Decimal("0"),
                amount=Decimal("0"),
                batch_id=None,
                batch_no=batch_no,
                production_date=production_date,
                expiry_date=expiry_date,
                **snap,
            )
            out_order.items.append(out_item)
            in_order.items.append(in_item)
            pairs.append((item, out_item, in_item, batch_no))
        OutboundOrderRepo(self.db).add(out_order)
        InboundOrderRepo(self.db).add(in_order)

        ledger = StockLedger(self.db)
        for item, out_item, in_item, batch_no in pairs:
            source_batch = ledger.change(
                key="TRANSFER_OUT:%d:%d" % (obj.id, out_item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.from_warehouse_id,
                delta=-item.quantity,
                txn_type="TRANSFER_OUT",
                source_type="TRANSFER",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=out_item.id,
                operator_id=operator_id,
                batch_id=out_item.batch_id,
                batch_no=None if out_item.batch_id else batch_no,
            )
            out_item.batch_id = source_batch.id
            target_batch = ledger.change(
                key="TRANSFER_IN:%d:%d" % (obj.id, in_item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.to_warehouse_id,
                delta=item.quantity,
                txn_type="TRANSFER_IN",
                source_type="TRANSFER",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=in_item.id,
                operator_id=operator_id,
                batch_no=source_batch.batch_no,
                production_date=source_batch.production_date,
                expiry_date=source_batch.expiry_date,
            )
            in_item.batch_id = target_batch.id
            item.batch_id = source_batch.id
            item.outbound_item_id = out_item.id
            item.inbound_item_id = in_item.id

        apply_transition(out_order, DocTypes.OUTBOUND_ORDER, Actions.START)
        apply_transition(in_order, DocTypes.INBOUND_ORDER, Actions.START)
        out_order.outbound_by = operator_id
        out_order.outbound_at = utcnow()
        in_order.inbound_by = operator_id
        in_order.inbound_at = utcnow()
        apply_transition(obj, self.doc_type, Actions.START)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def complete(self, transfer_id: int) -> TransferOrder:
        obj = self.get(transfer_id)
        apply_transition(obj, self.doc_type, Actions.COMPLETE)
        obj.completed_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def cancel(self, transfer_id: int, reason: str | None) -> TransferOrder:
        obj = self.get(transfer_id)
        apply_transition(obj, self.doc_type, Actions.CANCEL)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def reverse(self, transfer_id: int, operator_id: int, reason: str | None) -> TransferOrder:
        obj = self.get(transfer_id)
        require_transition(self.doc_type, Actions.REVERSE, obj.status)
        ledger = StockLedger(self.db)
        for item in obj.items:
            in_item = self.db.get(InboundItem, item.inbound_item_id) if item.inbound_item_id else None
            if in_item is not None and in_item.batch_id is not None:
                ledger.change(
                    key="TRANSFER_REV_IN:%d:%d" % (obj.id, item.line_no),
                    material_id=item.material_id,
                    warehouse_id=obj.to_warehouse_id,
                    delta=-item.quantity,
                    txn_type="REVERSAL",
                    source_type="TRANSFER",
                    source_id=obj.id,
                    source_no=obj.doc_no,
                    source_line_id=in_item.id,
                    operator_id=operator_id,
                    batch_id=in_item.batch_id,
                )
            ledger.change(
                key="TRANSFER_REV_OUT:%d:%d" % (obj.id, item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.from_warehouse_id,
                delta=item.quantity,
                txn_type="REVERSAL",
                source_type="TRANSFER",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=item.outbound_item_id,
                operator_id=operator_id,
                batch_id=item.batch_id,
                batch_no=None if item.batch_id else BATCH_DEFAULT_NO,
            )
        out_order = OutboundOrderRepo(self.db).find_by_transfer(obj.id)
        if out_order is not None and can(DocTypes.OUTBOUND_ORDER, Actions.REVERSE, out_order.status):
            apply_transition(out_order, DocTypes.OUTBOUND_ORDER, Actions.REVERSE)
            out_order.cancel_reason = reason
        in_order = InboundOrderRepo(self.db).find_by_transfer(obj.id)
        if in_order is not None and can(DocTypes.INBOUND_ORDER, Actions.REVERSE, in_order.status):
            apply_transition(in_order, DocTypes.INBOUND_ORDER, Actions.REVERSE)
            in_order.cancel_reason = reason
        apply_transition(obj, self.doc_type, Actions.REVERSE)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj


# ---------------- 盘点单 ----------------
class StocktakeService:
    doc_type = DocTypes.STOCKTAKE_ORDER
    label = "盘点单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = StocktakeOrderRepo(db)
        self.item_repo = StocktakeItemRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, stocktake_id: int) -> StocktakeOrder:
        obj = self.repo.get_active(stocktake_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def _build_item(self, data, line_no: int) -> StocktakeItem:
        _load_material(self.db, data.material_id)
        return StocktakeItem(
            line_no=line_no,
            material_id=data.material_id,
            batch_id=data.batch_id,
            location_id=data.location_id,
            book_qty=data.book_qty,
            reason=data.reason,
            remark=data.remark,
        )

    def create(self, payload, operator_id: int) -> StocktakeOrder:
        _require_warehouse(self.db, payload.warehouse_id)
        obj = StocktakeOrder(
            doc_no=self.repo.next_doc_no(),
            warehouse_id=payload.warehouse_id,
            scope=payload.scope,
            status=DocStatus.DRAFT,
            planned_date=payload.planned_date,
            remark=payload.remark,
            created_by=operator_id,
            items=[self._build_item(item, idx) for idx, item in enumerate(payload.items, start=1)],
        )
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, stocktake_id: int, payload) -> StocktakeOrder:
        obj = self.get(stocktake_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的盘点单可修改，当前：" + obj.status)
        data = payload.model_dump(exclude_unset=True, exclude={"items"})
        for key, value in data.items():
            setattr(obj, key, value)
        if "items" in payload.model_fields_set:
            items = payload.items or []
            if not items:
                raise BadRequest("盘点单至少需要一行明细")
            obj.items.clear()
            for idx, item in enumerate(items, start=1):
                obj.items.append(self._build_item(item, idx))
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, stocktake_id: int) -> None:
        obj = self.get(stocktake_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的盘点单可删除，当前：" + obj.status)
        obj.deleted_at = utcnow()
        self.db.commit()

    def start(self, stocktake_id: int, operator_id: int) -> StocktakeOrder:
        """开始盘点：快照账面数量（book_qty）。"""
        obj = self.get(stocktake_id)
        require_transition(self.doc_type, Actions.START, obj.status)
        for item in obj.items:
            material = _load_material(self.db, item.material_id)
            if item.batch_id is not None:
                batch = self.db.get(InventoryBatch, item.batch_id)
                if batch is None or batch.material_id != item.material_id or batch.warehouse_id != obj.warehouse_id:
                    raise BadRequest("盘点批次不属于该物资/仓库：" + str(item.batch_id))
                item.book_qty = batch.quantity
            elif material.is_batch_managed:
                raise BadRequest("批次物资盘点行必须指定 batch_id：" + material.code)
            else:
                batch = InventoryBatchRepo(self.db).get_grain(item.material_id, obj.warehouse_id, BATCH_DEFAULT_NO)
                if batch is not None:
                    item.batch_id = batch.id
                item.book_qty = batch.quantity if batch is not None else Decimal("0")
        apply_transition(obj, self.doc_type, Actions.START)
        obj.started_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def set_counts(self, stocktake_id: int, payload) -> StocktakeOrder:
        obj = self.get(stocktake_id)
        if obj.status not in (DocStatus.DRAFT, DocStatus.IN_PROGRESS):
            raise NotEditable("仅草稿/盘点中的盘点单可录入实盘数，当前：" + obj.status)
        item_map = {item.id: item for item in obj.items}
        for row in payload.items:
            item = item_map.get(row.stocktake_item_id)
            if item is None:
                raise BadRequest("盘点行不存在或不属于该盘点单：" + str(row.stocktake_item_id))
            item.actual_qty = row.actual_qty
            item.diff_qty = row.actual_qty - item.book_qty
            if row.reason is not None:
                item.reason = row.reason
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def complete(self, stocktake_id: int, operator_id: int) -> StocktakeOrder:
        obj = self.get(stocktake_id)
        require_transition(self.doc_type, Actions.COMPLETE, obj.status)
        ledger = StockLedger(self.db)
        for item in obj.items:
            if item.actual_qty is None:
                raise BadRequest("盘点行 %d 未录入实盘数量" % item.line_no)
            diff = item.actual_qty - item.book_qty
            item.diff_qty = diff
            if diff == 0:
                continue
            material = _load_material(self.db, item.material_id)
            if item.batch_id is None and material.is_batch_managed:
                raise BadRequest("批次物资盘点行必须指定 batch_id：" + material.code)
            ledger.change(
                key="STOCKTAKE:%d:%d" % (obj.id, item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.warehouse_id,
                delta=diff,
                txn_type="STOCKTAKE_GAIN" if diff > 0 else "STOCKTAKE_LOSS",
                source_type="STOCKTAKE",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=item.id,
                operator_id=operator_id,
                batch_id=item.batch_id,
                batch_no=None if item.batch_id else BATCH_DEFAULT_NO,
            )
        apply_transition(obj, self.doc_type, Actions.COMPLETE)
        obj.finished_at = utcnow()
        obj.posted_by = operator_id
        obj.posted_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def cancel(self, stocktake_id: int, reason: str | None) -> StocktakeOrder:
        obj = self.get(stocktake_id)
        apply_transition(obj, self.doc_type, Actions.CANCEL)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def reverse(self, stocktake_id: int, operator_id: int, reason: str | None) -> StocktakeOrder:
        obj = self.get(stocktake_id)
        require_transition(self.doc_type, Actions.REVERSE, obj.status)
        ledger = StockLedger(self.db)
        for item in obj.items:
            diff = item.diff_qty or Decimal("0")
            if diff == 0:
                continue
            ledger.change(
                key="STOCKTAKE_REV:%d:%d" % (obj.id, item.line_no),
                material_id=item.material_id,
                warehouse_id=obj.warehouse_id,
                delta=-diff,
                txn_type="REVERSAL",
                source_type="STOCKTAKE",
                source_id=obj.id,
                source_no=obj.doc_no,
                source_line_id=item.id,
                operator_id=operator_id,
                batch_id=item.batch_id,
                batch_no=None if item.batch_id else BATCH_DEFAULT_NO,
            )
        apply_transition(obj, self.doc_type, Actions.REVERSE)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj
