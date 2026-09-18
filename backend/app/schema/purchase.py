"""采购模块 DTO（入参/出参分开，出参从 ORM 校验）。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- 请购单 ----------------
class PRItemIn(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0)
    purpose: str | None = Field(default=None, max_length=255)
    expected_date: date | None = None
    remark: str | None = Field(default=None, max_length=255)


class PRCreate(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    dept_name: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=3, ge=1, le=5)
    expected_date: date | None = None
    reason: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    items: list[PRItemIn] = Field(min_length=1)


class PRUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    dept_name: str | None = Field(default=None, max_length=64)
    priority: int | None = Field(default=None, ge=1, le=5)
    expected_date: date | None = None
    reason: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    items: list[PRItemIn] | None = None


class PRItemOut(ORMBase):
    id: int
    requisition_id: int
    line_no: int
    material_id: int
    material_code: str
    material_name: str
    spec: str | None
    unit_name: str
    quantity: Decimal
    purpose: str | None
    expected_date: date | None
    remark: str | None


class PROut(ORMBase):
    id: int
    doc_no: str
    title: str | None
    requester_id: int
    dept_name: str | None
    status: str
    priority: int
    expected_date: date | None
    reason: str | None
    total_amount: Decimal
    approved_by: int | None
    approved_at: datetime | None
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[PRItemOut] = []


class PRConvertItemIn(BaseModel):
    pr_item_id: int
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class PRConvertIn(BaseModel):
    """已审请购单转采购订单：items 为空时按请购行全额自动带出。"""

    supplier_id: int
    delivery_address: str | None = Field(default=None, max_length=255)
    currency: str = Field(default="CNY", max_length=8)
    payment_terms: str | None = Field(default=None, max_length=64)
    expected_date: date | None = None
    remark: str | None = None
    items: list[PRConvertItemIn] = []


# ---------------- 采购订单 ----------------
class POItemIn(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    expected_date: date | None = None
    source_pr_item_id: int | None = None
    remark: str | None = Field(default=None, max_length=255)


class POCreate(BaseModel):
    supplier_id: int
    requisition_id: int | None = None
    order_date: date | None = None
    expected_date: date | None = None
    buyer_id: int | None = None
    delivery_address: str | None = Field(default=None, max_length=255)
    currency: str = Field(default="CNY", max_length=8)
    payment_terms: str | None = Field(default=None, max_length=64)
    remark: str | None = None
    items: list[POItemIn] = Field(min_length=1)


class POUpdate(BaseModel):
    supplier_id: int | None = None
    expected_date: date | None = None
    buyer_id: int | None = None
    delivery_address: str | None = Field(default=None, max_length=255)
    currency: str | None = Field(default=None, max_length=8)
    payment_terms: str | None = Field(default=None, max_length=64)
    remark: str | None = None
    items: list[POItemIn] | None = None


class POItemOut(ORMBase):
    id: int
    po_id: int
    line_no: int
    material_id: int
    material_code: str
    material_name: str
    spec: str | None
    unit_name: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    amount: Decimal
    received_qty: Decimal
    expected_date: date | None
    source_pr_item_id: int | None
    remark: str | None


class POOut(ORMBase):
    id: int
    doc_no: str
    requisition_id: int | None
    supplier_id: int
    status: str
    order_date: date
    expected_date: date | None
    buyer_id: int | None
    delivery_address: str | None
    currency: str
    total_amount: Decimal
    tax_amount: Decimal
    payment_terms: str | None
    approved_by: int | None
    approved_at: datetime | None
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[POItemOut] = []


# ---------------- 到货/验收单 ----------------
class DeliveryItemIn(BaseModel):
    po_item_id: int
    quantity: Decimal = Field(gt=0)
    accepted_qty: Decimal | None = Field(default=None, ge=0)
    rejected_qty: Decimal | None = Field(default=None, ge=0)
    batch_no: str | None = Field(default=None, max_length=64)
    production_date: date | None = None
    expiry_date: date | None = None
    inspection_result: str | None = Field(default=None, pattern="^(PASS|CONCESSION|REJECT)$")
    remark: str | None = Field(default=None, max_length=255)


class DeliveryCreate(BaseModel):
    po_id: int
    delivery_date: date
    received_by: int | None = None
    remark: str | None = None
    items: list[DeliveryItemIn] = Field(min_length=1)


class DeliveryUpdate(BaseModel):
    delivery_date: date | None = None
    received_by: int | None = None
    remark: str | None = None
    items: list[DeliveryItemIn] | None = None


class DeliveryItemOut(ORMBase):
    id: int
    delivery_id: int
    line_no: int
    po_item_id: int
    material_id: int
    material_code: str
    material_name: str
    spec: str | None
    unit_name: str
    quantity: Decimal
    accepted_qty: Decimal | None
    rejected_qty: Decimal | None
    batch_no: str | None
    production_date: date | None
    expiry_date: date | None
    inspection_result: str | None
    remark: str | None


class DeliveryOut(ORMBase):
    id: int
    doc_no: str
    po_id: int
    supplier_id: int
    delivery_date: date
    status: str
    received_by: int | None
    inspected_by: int | None
    inspected_at: datetime | None
    total_amount: Decimal
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[DeliveryItemOut] = []


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
