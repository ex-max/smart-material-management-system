"""采购业务：请购单（提交/审批/转采购订单）、采购订单、到货验收单。

事务边界在本层：一个 usecase 一次 commit；状态迁移全部走 core.state_machine。
到货验收 -> 入库 -> 写 inventory_transaction 的联动放 M2-b，本层只登记到货与验收信息。
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotEditable, NotFound
from app.core.state_machine import Actions, DocStatus, DocTypes, apply_transition, require_transition
from app.model.base import utcnow
from app.model.purchase import (
    POItem,
    PRItem,
    PurchaseOrder,
    PurchaseRequisition,
    SupplierDelivery,
    SupplierDeliveryItem,
)
from app.repository.master import MaterialRepo, SupplierRepo, UnitRepo
from app.repository.purchase import (
    POItemRepo,
    PurchaseOrderRepo,
    PurchaseRequisitionRepo,
    SupplierDeliveryItemRepo,
    SupplierDeliveryRepo,
)
from app.repository.user import UserRepository

_MONEY = Decimal("0.0001")
_HUNDRED = Decimal("100")

_SNAPSHOT_FIELDS = ("material_id", "material_code", "material_name", "spec", "unit_name")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _require_user(db: Session, user_id: int | None, label: str) -> None:
    if user_id is not None and UserRepository(db).get(user_id) is None:
        raise BadRequest(label + "不存在")


def _snapshot(db: Session, material_id: int) -> dict:
    """取物资快照；物资必须处于 ACTIVE 且未软删。"""
    material = MaterialRepo(db).get_active(material_id)
    if material is None:
        raise BadRequest("物资不存在：" + str(material_id))
    unit = UnitRepo(db).get(material.unit_id)
    return {
        "material_id": material.id,
        "material_code": material.code,
        "material_name": material.name,
        "spec": material.spec,
        "unit_name": unit.name if unit is not None else "",
    }


def _check_dates(order_date: date, expected_date: date | None) -> None:
    if expected_date is not None and expected_date < order_date:
        raise BadRequest("交期不能早于下单日期")


class PurchaseRequisitionService:
    doc_type = DocTypes.PURCHASE_REQUISITION
    label = "请购单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PurchaseRequisitionRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, req_id: int) -> PurchaseRequisition:
        obj = self.repo.get_active(req_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def _build_item(self, data, line_no: int) -> PRItem:
        return PRItem(
            line_no=line_no,
            quantity=data.quantity,
            purpose=data.purpose,
            expected_date=data.expected_date,
            remark=data.remark,
            **_snapshot(self.db, data.material_id),
        )

    def create(self, payload, operator_id: int) -> PurchaseRequisition:
        obj = self.build(payload, operator_id)
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def build(self, payload, operator_id: int) -> PurchaseRequisition:
        """构造请购单对象但不提交（供 create 与补货建议转单复用，保证同一事务）。"""
        return PurchaseRequisition(
            doc_no=self.repo.next_doc_no(),
            title=payload.title,
            requester_id=operator_id,
            dept_name=payload.dept_name,
            status=DocStatus.DRAFT,
            priority=payload.priority,
            expected_date=payload.expected_date,
            reason=payload.reason,
            remark=payload.remark,
            total_amount=Decimal("0"),
            created_by=operator_id,
            items=[self._build_item(item, idx) for idx, item in enumerate(payload.items, start=1)],
        )

    def update(self, req_id: int, payload) -> PurchaseRequisition:
        obj = self.get(req_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的请购单可修改，当前：" + obj.status)
        data = payload.model_dump(exclude_unset=True, exclude={"items"})
        for key, value in data.items():
            setattr(obj, key, value)
        if "items" in payload.model_fields_set:
            items = payload.items or []
            if not items:
                raise BadRequest("请购单至少需要一行明细")
            obj.items.clear()
            for idx, item in enumerate(items, start=1):
                obj.items.append(self._build_item(item, idx))
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, req_id: int) -> None:
        obj = self.get(req_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的请购单可删除，当前：" + obj.status)
        obj.deleted_at = utcnow()
        self.db.commit()

    def submit(self, req_id: int) -> PurchaseRequisition:
        obj = self.get(req_id)
        apply_transition(obj, self.doc_type, Actions.SUBMIT)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def approve(self, req_id: int, operator_id: int) -> PurchaseRequisition:
        obj = self.get(req_id)
        apply_transition(obj, self.doc_type, Actions.APPROVE)
        obj.approved_by = operator_id
        obj.approved_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def cancel(self, req_id: int, operator_id: int, reason: str | None) -> PurchaseRequisition:
        obj = self.get(req_id)
        apply_transition(obj, self.doc_type, Actions.CANCEL)
        obj.cancelled_by = operator_id
        obj.cancelled_at = utcnow()
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def convert_to_po(self, req_id: int, payload, operator_id: int) -> PurchaseOrder:
        """已审请购单 → 采购订单：自动带出全部请购行，可选覆盖单价/税率。"""
        req = self.get(req_id)
        require_transition(self.doc_type, Actions.START, req.status)
        supplier = SupplierRepo(self.db).get_active(payload.supplier_id)
        if supplier is None:
            raise BadRequest("供应商不存在：" + str(payload.supplier_id))
        if not req.items:
            raise BadRequest("请购单没有可转明细")

        overrides = {item.pr_item_id: item for item in payload.items}
        valid_ids = {item.id for item in req.items}
        unknown = set(overrides) - valid_ids
        if unknown:
            raise BadRequest("请购行不属于该请购单：" + ",".join(str(x) for x in sorted(unknown)))

        order_date = date.today()
        expected_date = payload.expected_date or req.expected_date
        _check_dates(order_date, expected_date)

        po = PurchaseOrder(
            doc_no=PurchaseOrderRepo(self.db).next_doc_no(order_date),
            requisition_id=req.id,
            supplier_id=supplier.id,
            status=DocStatus.APPROVED,
            order_date=order_date,
            expected_date=expected_date,
            buyer_id=operator_id,
            delivery_address=payload.delivery_address,
            currency=payload.currency,
            payment_terms=payload.payment_terms or supplier.payment_terms,
            approved_by=operator_id,
            approved_at=utcnow(),
            remark=payload.remark,
            created_by=operator_id,
        )
        po.items = []
        for idx, pr_item in enumerate(req.items, start=1):
            override = overrides.get(pr_item.id)
            unit_price = override.unit_price if override else Decimal("0")
            tax_rate = override.tax_rate if override else Decimal("0")
            amount = _money(pr_item.quantity * unit_price)
            po.items.append(
                POItem(
                    line_no=idx,
                    quantity=pr_item.quantity,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    amount=amount,
                    expected_date=pr_item.expected_date,
                    source_pr_item_id=pr_item.id,
                    remark=pr_item.remark,
                    **{field: getattr(pr_item, field) for field in _SNAPSHOT_FIELDS},
                )
            )
        po.total_amount, po.tax_amount = _po_totals(po.items)
        PurchaseOrderRepo(self.db).add(po)
        apply_transition(req, self.doc_type, Actions.START)
        self.db.commit()
        self.db.refresh(po)
        return po


def _po_totals(items) -> tuple[Decimal, Decimal]:
    total = sum((item.amount for item in items), Decimal("0"))
    tax = sum((_money(item.amount * item.tax_rate / _HUNDRED) for item in items), Decimal("0"))
    return _money(total), _money(tax)


class PurchaseOrderService:
    doc_type = DocTypes.PURCHASE_ORDER
    label = "采购订单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PurchaseOrderRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, po_id: int) -> PurchaseOrder:
        obj = self.repo.get_active(po_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def _build_item(self, data, line_no: int) -> POItem:
        amount = _money(data.quantity * data.unit_price)
        return POItem(
            line_no=line_no,
            quantity=data.quantity,
            unit_price=data.unit_price,
            tax_rate=data.tax_rate,
            amount=amount,
            expected_date=data.expected_date,
            source_pr_item_id=data.source_pr_item_id,
            remark=data.remark,
            **_snapshot(self.db, data.material_id),
        )

    def create(self, payload, operator_id: int) -> PurchaseOrder:
        supplier = SupplierRepo(self.db).get_active(payload.supplier_id)
        if supplier is None:
            raise BadRequest("供应商不存在：" + str(payload.supplier_id))
        _require_user(self.db, payload.buyer_id, "采购员")

        req = None
        status = DocStatus.DRAFT
        approved_by = None
        approved_at = None
        if payload.requisition_id is not None:
            req = PurchaseRequisitionRepo(self.db).get_active(payload.requisition_id)
            if req is None:
                raise BadRequest("来源请购单不存在：" + str(payload.requisition_id))
            require_transition(DocTypes.PURCHASE_REQUISITION, Actions.START, req.status)
            status = DocStatus.APPROVED
            approved_by = operator_id
            approved_at = utcnow()
            pr_item_ids = {item.id for item in req.items}
            for item in payload.items:
                if item.source_pr_item_id is not None and item.source_pr_item_id not in pr_item_ids:
                    raise BadRequest("来源请购行不属于来源请购单")

        order_date = payload.order_date or date.today()
        _check_dates(order_date, payload.expected_date)

        po = PurchaseOrder(
            doc_no=self.repo.next_doc_no(order_date),
            requisition_id=payload.requisition_id,
            supplier_id=supplier.id,
            status=status,
            order_date=order_date,
            expected_date=payload.expected_date,
            buyer_id=payload.buyer_id,
            delivery_address=payload.delivery_address,
            currency=payload.currency,
            payment_terms=payload.payment_terms or supplier.payment_terms,
            approved_by=approved_by,
            approved_at=approved_at,
            remark=payload.remark,
            created_by=operator_id,
            items=[self._build_item(item, idx) for idx, item in enumerate(payload.items, start=1)],
        )
        po.total_amount, po.tax_amount = _po_totals(po.items)
        self.repo.add(po)
        if req is not None:
            apply_transition(req, DocTypes.PURCHASE_REQUISITION, Actions.START)
        self.db.commit()
        self.db.refresh(po)
        return po

    def update(self, po_id: int, payload) -> PurchaseOrder:
        obj = self.get(po_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的采购订单可修改，当前：" + obj.status)
        data = payload.model_dump(exclude_unset=True, exclude={"items"})
        if data.get("supplier_id") is not None and SupplierRepo(self.db).get_active(data["supplier_id"]) is None:
            raise BadRequest("供应商不存在：" + str(data["supplier_id"]))
        if "buyer_id" in data:
            _require_user(self.db, data["buyer_id"], "采购员")
        expected_date = data.get("expected_date", obj.expected_date)
        _check_dates(obj.order_date, expected_date)
        for key, value in data.items():
            setattr(obj, key, value)
        if "items" in payload.model_fields_set:
            items = payload.items or []
            if not items:
                raise BadRequest("采购订单至少需要一行明细")
            obj.items.clear()
            for idx, item in enumerate(items, start=1):
                obj.items.append(self._build_item(item, idx))
            obj.total_amount, obj.tax_amount = _po_totals(obj.items)
        else:
            obj.total_amount, obj.tax_amount = _po_totals(obj.items)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, po_id: int) -> None:
        obj = self.get(po_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的采购订单可删除，当前：" + obj.status)
        obj.deleted_at = utcnow()
        self.db.commit()

    def confirm(self, po_id: int, operator_id: int) -> PurchaseOrder:
        obj = self.get(po_id)
        apply_transition(obj, self.doc_type, Actions.CONFIRM)
        obj.approved_by = operator_id
        obj.approved_at = utcnow()
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def cancel(self, po_id: int, operator_id: int, reason: str | None) -> PurchaseOrder:
        obj = self.get(po_id)
        apply_transition(obj, self.doc_type, Actions.CANCEL)
        obj.cancelled_by = operator_id
        obj.cancelled_at = utcnow()
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj


class SupplierDeliveryService:
    doc_type = DocTypes.SUPPLIER_DELIVERY
    label = "到货单"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SupplierDeliveryRepo(db)
        self.items = SupplierDeliveryItemRepo(db)
        self.po_items = POItemRepo(db)

    def list(self, page: int, page_size: int, status: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, status=status)

    def get(self, delivery_id: int) -> SupplierDelivery:
        obj = self.repo.get_active(delivery_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def _build_item(self, data, line_no: int, po_item: POItem, exclude_delivery_id: int | None) -> SupplierDeliveryItem:
        delivered = self.items.delivered_qty(po_item.id, exclude_delivery_id=exclude_delivery_id)
        if delivered + data.quantity > po_item.quantity:
            raise BadRequest(
                "到货数量超过订单未交量：行 %s 订购 %s，已登记 %s" % (po_item.line_no, po_item.quantity, delivered)
            )
        if data.accepted_qty is not None and data.rejected_qty is not None:
            if data.accepted_qty + data.rejected_qty > data.quantity:
                raise BadRequest("合格数量 + 拒收数量不能超过到货数量")
        material = MaterialRepo(self.db).get(po_item.material_id)
        if material is not None and material.is_batch_managed and not data.batch_no:
            raise BadRequest("批次物资必须填写批次号：" + po_item.material_code)
        if material is not None and material.shelf_life_days and not data.expiry_date:
            raise BadRequest("有保质期的物资必须填写到期日期：" + po_item.material_code)
        return SupplierDeliveryItem(
            line_no=line_no,
            po_item_id=po_item.id,
            quantity=data.quantity,
            accepted_qty=data.accepted_qty,
            rejected_qty=data.rejected_qty,
            batch_no=data.batch_no,
            production_date=data.production_date,
            expiry_date=data.expiry_date,
            inspection_result=data.inspection_result,
            remark=data.remark,
            **{field: getattr(po_item, field) for field in _SNAPSHOT_FIELDS},
        )

    def _build_items(self, po: PurchaseOrder, items, exclude_delivery_id: int | None):
        po_item_map = {item.id: item for item in self.po_items.list_by_po(po.id)}
        built = []
        total = Decimal("0")
        for idx, data in enumerate(items, start=1):
            po_item = po_item_map.get(data.po_item_id)
            if po_item is None:
                raise BadRequest("采购订单行不存在或不属于该订单：" + str(data.po_item_id))
            built.append(self._build_item(data, idx, po_item, exclude_delivery_id))
            total += _money(data.quantity * po_item.unit_price)
        return built, _money(total)

    def create(self, payload, operator_id: int) -> SupplierDelivery:
        po = PurchaseOrderRepo(self.db).get_active(payload.po_id)
        if po is None:
            raise BadRequest("采购订单不存在：" + str(payload.po_id))
        if po.status not in (DocStatus.APPROVED, DocStatus.IN_PROGRESS):
            raise BadRequest("采购订单未确认或已作废，不能登记到货，当前：" + po.status)
        _require_user(self.db, payload.received_by, "收货人")
        items, total = self._build_items(po, payload.items, None)
        delivery = SupplierDelivery(
            doc_no=self.repo.next_doc_no(),
            po_id=po.id,
            supplier_id=po.supplier_id,
            delivery_date=payload.delivery_date,
            status=DocStatus.DRAFT,
            received_by=payload.received_by,
            total_amount=total,
            remark=payload.remark,
            created_by=operator_id,
            items=items,
        )
        self.repo.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def update(self, delivery_id: int, payload) -> SupplierDelivery:
        obj = self.get(delivery_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的到货单可修改，当前：" + obj.status)
        po = PurchaseOrderRepo(self.db).get_active(obj.po_id)
        data = payload.model_dump(exclude_unset=True, exclude={"items"})
        if "received_by" in data:
            _require_user(self.db, data["received_by"], "收货人")
        for key, value in data.items():
            setattr(obj, key, value)
        if "items" in payload.model_fields_set:
            items = payload.items or []
            if not items:
                raise BadRequest("到货单至少需要一行明细")
            built, total = self._build_items(po, items, exclude_delivery_id=obj.id)
            obj.items.clear()
            obj.items.extend(built)
            obj.total_amount = total
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, delivery_id: int) -> None:
        obj = self.get(delivery_id)
        if obj.status != DocStatus.DRAFT:
            raise NotEditable("仅草稿状态的到货单可删除，当前：" + obj.status)
        obj.deleted_at = utcnow()
        self.db.commit()

    def submit(self, delivery_id: int) -> SupplierDelivery:
        obj = self.get(delivery_id)
        apply_transition(obj, self.doc_type, Actions.SUBMIT)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def cancel(self, delivery_id: int, operator_id: int, reason: str | None) -> SupplierDelivery:
        obj = self.get(delivery_id)
        apply_transition(obj, self.doc_type, Actions.CANCEL)
        obj.cancel_reason = reason
        self.db.commit()
        self.db.refresh(obj)
        return obj
