"""出库 / 调拨 / 盘点 DTO。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- 出库单 ----------------
class OutboundItemIn(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0)
    batch_id: int | None = None
    location_id: int | None = None
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    remark: str | None = Field(default=None, max_length=255)


class OutboundCreate(BaseModel):
    warehouse_id: int
    source_type: str = Field(default="REQUISITION_ISSUE", pattern="^(REQUISITION_ISSUE|TRANSFER|SCRAP|OTHER)$")
    receiver_id: int | None = None
    dept_name: str | None = Field(default=None, max_length=64)
    remark: str | None = None
    items: list[OutboundItemIn] = Field(min_length=1)


class OutboundUpdate(BaseModel):
    receiver_id: int | None = None
    dept_name: str | None = Field(default=None, max_length=64)
    remark: str | None = None
    items: list[OutboundItemIn] | None = None


class OutboundItemOut(ORMBase):
    id: int
    outbound_id: int
    line_no: int
    material_id: int
    material_code: str
    material_name: str
    spec: str | None
    unit_name: str
    quantity: Decimal
    batch_id: int | None
    location_id: int | None
    unit_price: Decimal
    amount: Decimal
    remark: str | None


class OutboundOrderOut(ORMBase):
    id: int
    doc_no: str
    source_type: str
    source_id: int | None
    transfer_order_id: int | None
    warehouse_id: int
    receiver_id: int | None
    dept_name: str | None
    status: str
    outbound_by: int | None
    outbound_at: datetime | None
    total_amount: Decimal
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[OutboundItemOut] = []


# ---------------- 调拨单 ----------------
class TransferItemIn(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0)
    batch_id: int | None = None
    batch_no: str | None = Field(default=None, max_length=64)
    from_location_id: int | None = None
    to_location_id: int | None = None
    remark: str | None = Field(default=None, max_length=255)


class TransferCreate(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    applicant_id: int | None = None
    transfer_date: date | None = None
    remark: str | None = None
    items: list[TransferItemIn] = Field(min_length=1)


class TransferUpdate(BaseModel):
    applicant_id: int | None = None
    transfer_date: date | None = None
    remark: str | None = None
    items: list[TransferItemIn] | None = None


class TransferItemOut(ORMBase):
    id: int
    transfer_id: int
    line_no: int
    material_id: int
    material_code: str
    material_name: str
    spec: str | None
    unit_name: str
    quantity: Decimal
    batch_id: int | None
    from_location_id: int | None
    to_location_id: int | None
    outbound_item_id: int | None
    inbound_item_id: int | None
    remark: str | None


class TransferOrderOut(ORMBase):
    id: int
    doc_no: str
    from_warehouse_id: int
    to_warehouse_id: int
    status: str
    applicant_id: int | None
    transfer_date: date
    completed_at: datetime | None
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[TransferItemOut] = []


# ---------------- 盘点单 ----------------
class StocktakeItemIn(BaseModel):
    material_id: int
    batch_id: int | None = None
    location_id: int | None = None
    book_qty: Decimal = Field(default=Decimal("0"), ge=0)
    reason: str | None = Field(default=None, max_length=255)
    remark: str | None = Field(default=None, max_length=255)


class StocktakeCreate(BaseModel):
    warehouse_id: int
    scope: str = Field(default="PARTIAL", pattern="^(FULL|PARTIAL)$")
    planned_date: date | None = None
    remark: str | None = None
    items: list[StocktakeItemIn] = Field(min_length=1)


class StocktakeUpdate(BaseModel):
    planned_date: date | None = None
    remark: str | None = None
    items: list[StocktakeItemIn] | None = None


class StocktakeCountItemIn(BaseModel):
    stocktake_item_id: int
    actual_qty: Decimal = Field(ge=0)
    reason: str | None = Field(default=None, max_length=255)


class StocktakeCountIn(BaseModel):
    items: list[StocktakeCountItemIn] = Field(min_length=1)


class StocktakeItemOut(ORMBase):
    id: int
    stocktake_id: int
    line_no: int
    material_id: int
    batch_id: int | None
    location_id: int | None
    book_qty: Decimal
    actual_qty: Decimal | None
    diff_qty: Decimal | None
    reason: str | None
    remark: str | None


class StocktakeOrderOut(ORMBase):
    id: int
    doc_no: str
    warehouse_id: int
    scope: str
    status: str
    planned_date: date | None
    started_at: datetime | None
    finished_at: datetime | None
    posted_by: int | None
    posted_at: datetime | None
    cancel_reason: str | None
    remark: str | None
    created_at: datetime
    items: list[StocktakeItemOut] = []
