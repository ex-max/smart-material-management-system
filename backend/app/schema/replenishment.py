"""补货策略与建议 DTO。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReplenishmentPolicyCreate(BaseModel):
    policy_code: str = Field(min_length=1, max_length=32)
    policy_name: str | None = Field(default=None, max_length=64)
    material_id: int | None = None
    warehouse_id: int | None = None
    strategy: str = Field(pattern="^(FIXED|FORECAST|EOQ|MIN_MAX)$")
    service_level_type: str | None = Field(default="CSL", pattern="^(CSL|FILL_RATE)$")
    service_level: Decimal | None = Field(default=Decimal("0.95"), gt=0, lt=1)
    z_value: Decimal | None = Field(default=None, ge=0)
    review_period_days: int | None = Field(default=7, gt=0)
    order_cost: Decimal | None = Field(default=None, ge=0)
    holding_cost_rate: Decimal | None = Field(default=None, ge=0)
    min_order_qty: Decimal | None = Field(default=None, gt=0)
    pack_size: Decimal | None = Field(default=None, gt=0)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    safety_stock_override: Decimal | None = Field(default=None, ge=0)
    rop_override: Decimal | None = Field(default=None, ge=0)
    is_active: bool = True
    effective_from: date | None = None
    remark: str | None = Field(default=None, max_length=255)


class ReplenishmentPolicyUpdate(BaseModel):
    policy_name: str | None = Field(default=None, max_length=64)
    material_id: int | None = None
    warehouse_id: int | None = None
    strategy: str | None = Field(default=None, pattern="^(FIXED|FORECAST|EOQ|MIN_MAX)$")
    service_level_type: str | None = Field(default=None, pattern="^(CSL|FILL_RATE)$")
    service_level: Decimal | None = Field(default=None, gt=0, lt=1)
    z_value: Decimal | None = Field(default=None, ge=0)
    review_period_days: int | None = Field(default=None, gt=0)
    order_cost: Decimal | None = Field(default=None, ge=0)
    holding_cost_rate: Decimal | None = Field(default=None, ge=0)
    min_order_qty: Decimal | None = Field(default=None, gt=0)
    pack_size: Decimal | None = Field(default=None, gt=0)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    safety_stock_override: Decimal | None = Field(default=None, ge=0)
    rop_override: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    effective_from: date | None = None
    remark: str | None = Field(default=None, max_length=255)


class ReplenishmentPolicyOut(ORMBase):
    id: int
    policy_code: str
    policy_name: str | None
    material_id: int | None
    warehouse_id: int | None
    strategy: str
    service_level_type: str | None
    service_level: Decimal | None
    z_value: Decimal | None
    review_period_days: int | None
    order_cost: Decimal | None
    holding_cost_rate: Decimal | None
    min_order_qty: Decimal | None
    pack_size: Decimal | None
    lead_time_days: Decimal | None
    safety_stock_override: Decimal | None
    rop_override: Decimal | None
    is_active: bool
    effective_from: date | None
    remark: str | None


class ReplenishmentSuggestionOut(ORMBase):
    id: int
    suggestion_no: str
    material_id: int
    warehouse_id: int
    policy_id: int | None
    forecast_run_id: int | None
    trigger_type: str
    status: str
    current_qty: Decimal
    locked_qty: Decimal
    in_transit_qty: Decimal
    available_qty: Decimal
    daily_demand_hat: Decimal | None
    lead_time_days: Decimal | None
    sigma_d: Decimal | None
    sigma_lt: Decimal | None
    safety_stock: Decimal | None
    rop: Decimal | None
    eoq: Decimal | None
    suggested_qty: Decimal
    final_qty: Decimal | None
    reason: str | None
    generated_at: datetime
    expires_at: datetime | None
    converted_pr_id: int | None
    converted_at: datetime | None
    handled_by: int | None
    remark: str | None


class GenerateResult(BaseModel):
    scanned: int
    created: int
    updated: int
    closed: int
    skipped_no_policy: int


class SuggestionConfirmIn(BaseModel):
    final_qty: Decimal | None = Field(default=None, gt=0)
    remark: str | None = Field(default=None, max_length=255)


class SuggestionRejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class BatchConvertIn(BaseModel):
    suggestion_ids: list[int] = Field(min_length=1)


class ConvertResult(BaseModel):
    suggestion_id: int
    suggestion_no: str
    status: str
    converted_pr_id: int | None
    pr_doc_no: str | None
