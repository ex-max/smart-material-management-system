"""库存与入库 DTO。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InventoryOut(ORMBase):
    id: int
    material_id: int
    warehouse_id: int
    quantity: Decimal
    locked_qty: Decimal
    version: int
    last_txn_at: datetime | None
    remark: str | None


class InventoryBatchOut(ORMBase):
    id: int
    material_id: int
    warehouse_id: int
    batch_no: str
    is_default: bool
    production_date: date | None
    expiry_date: date | None
    inbound_date: date | None
    quantity: Decimal
    locked_qty: Decimal
    status: str
    remark: str | None


class InventoryTransactionOut(ORMBase):
    id: int
    idem_key: str | None
    material_id: int
    warehouse_id: int
    batch_id: int
    quantity: Decimal
    txn_type: str
    source_type: str
    source_id: int | None
    source_no: str | None
    source_line_id: int | None
    balance_after: Decimal | None
    unit_price: Decimal | None
    amount: Decimal | None
    occurred_at: datetime
    created_by: int | None
    remark: str | None


class InboundItemOut(ORMBase):
    id: int
    inbound_id: int
    line_no: int
    material_id: int
    material_code: str
    material_name: str
    spec: str | None
    unit_name: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    batch_id: int | None
    batch_no: str | None
    production_date: date | None
    expiry_date: date | None
    location_id: int | None
    po_item_id: int | None
    remark: str | None


class InboundOrderOut(ORMBase):
    id: int
    doc_no: str
    source_type: str
    source_id: int | None
    delivery_id: int | None
    warehouse_id: int
    status: str
    inbound_by: int | None
    inbound_at: datetime | None
    total_amount: Decimal
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[InboundItemOut] = []


class DeliveryAcceptItemIn(BaseModel):
    delivery_item_id: int
    accepted_qty: Decimal | None = Field(default=None, ge=0)
    rejected_qty: Decimal | None = Field(default=None, ge=0)
    inspection_result: str | None = Field(default=None, pattern="^(PASS|CONCESSION|REJECT)$")
    remark: str | None = Field(default=None, max_length=255)


class DeliveryAcceptIn(BaseModel):
    warehouse_id: int
    location_id: int | None = None
    remark: str | None = None
    items: list[DeliveryAcceptItemIn] = []


class ReconcileOut(BaseModel):
    inventory_vs_batch: list[dict]
    inventory_vs_txn: list[dict]
    batch_vs_txn: list[dict]
    negative_or_locked: list[dict]
    ok: bool
