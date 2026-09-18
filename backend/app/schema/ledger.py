"""台账与统计 DTO：库存预警 / 每日快照 / 供货价。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StockAlertOut(ORMBase):
    id: int
    material_id: int
    warehouse_id: int | None
    batch_id: int | None
    alert_type: str
    level: str
    status: str
    threshold: Decimal | None
    current_value: Decimal | None
    message: str | None
    triggered_at: datetime
    acked_by: int | None
    acked_at: datetime | None
    resolved_at: datetime | None
    remark: str | None


class ScanResult(BaseModel):
    scanned: int
    created: int


class InventorySnapshotOut(ORMBase):
    id: int
    snapshot_date: date
    material_id: int
    warehouse_id: int
    quantity: Decimal
    locked_qty: Decimal
    in_transit_qty: Decimal
    created_at: datetime


class SnapshotResult(BaseModel):
    snapshot_date: date
    created: int
    updated: int


class MaterialSupplierPriceCreate(BaseModel):
    material_id: int
    supplier_id: int
    unit_price: Decimal = Field(ge=0)
    currency: str = Field(default="CNY", max_length=8)
    min_order_qty: Decimal | None = Field(default=None, gt=0)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    is_preferred: bool = False
    valid_from: date | None = None
    valid_to: date | None = None
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE)$")
    remark: str | None = Field(default=None, max_length=255)


class MaterialSupplierPriceUpdate(BaseModel):
    unit_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    min_order_qty: Decimal | None = Field(default=None, gt=0)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    is_preferred: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")
    remark: str | None = Field(default=None, max_length=255)


class MaterialSupplierPriceOut(ORMBase):
    id: int
    material_id: int
    supplier_id: int
    unit_price: Decimal
    currency: str
    min_order_qty: Decimal | None
    lead_time_days: Decimal | None
    is_preferred: bool
    valid_from: date | None
    valid_to: date | None
    status: str
    remark: str | None
