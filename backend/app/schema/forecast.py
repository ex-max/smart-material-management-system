"""预测模块 DTO：需求序列元数据 / 模型注册 / 预测批次 / 预测结果。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DemandSeriesMetaIn(BaseModel):
    series_key: str | None = Field(default=None, max_length=64)
    material_id: int
    warehouse_id: int | None = None
    data_start_date: date | None = None
    data_end_date: date | None = None
    obs_days: int | None = Field(default=None, ge=0)
    non_zero_days: int | None = Field(default=None, ge=0)
    adi: Decimal | None = Field(default=None, ge=0)
    cv2: Decimal | None = Field(default=None, ge=0)
    demand_class: str | None = Field(default=None, pattern="^(SMOOTH|ERRATIC|INTERMITTENT|LUMPY)$")
    abc_class: str | None = Field(default=None, pattern="^[ABC]$")
    mean_daily: Decimal | None = Field(default=None, ge=0)
    std_daily: Decimal | None = Field(default=None, ge=0)
    last_calc_at: datetime | None = None
    remark: str | None = Field(default=None, max_length=255)


class DemandSeriesMetaOut(ORMBase):
    id: int
    series_key: str
    material_id: int
    warehouse_id: int | None
    data_start_date: date | None
    data_end_date: date | None
    obs_days: int | None
    non_zero_days: int | None
    adi: Decimal | None
    cv2: Decimal | None
    demand_class: str | None
    abc_class: str | None
    mean_daily: Decimal | None
    std_daily: Decimal | None
    last_calc_at: datetime | None
    remark: str | None


_MODEL_TYPE_PATTERN = (
    "^(NAIVE|SEASONAL_NAIVE|MA|ETS|ARIMA|SARIMA|RIDGE|RF|LIGHTGBM|XGBOOST|CROSTON|TSB|LSTM|TCN)$"
)


class ModelRegistryCreate(BaseModel):
    model_code: str = Field(min_length=1, max_length=64)
    model_type: str = Field(pattern=_MODEL_TYPE_PATTERN)
    version: str = Field(min_length=1, max_length=32)
    params: dict | None = None
    feature_config: dict | None = None
    metrics: dict | None = None
    artifact_path: str | None = Field(default=None, max_length=255)
    trained_at: datetime | None = None
    trained_by: int | None = None
    is_active: bool = False
    status: str = Field(default="READY", pattern="^(TRAINING|READY|ARCHIVED|FAILED)$")
    remark: str | None = Field(default=None, max_length=255)


class ModelRegistryOut(ORMBase):
    id: int
    model_code: str
    model_type: str
    version: str
    params: dict | None
    feature_config: dict | None
    metrics: dict | None
    artifact_path: str | None
    trained_at: datetime | None
    trained_by: int | None
    is_active: bool
    status: str
    remark: str | None


class ForecastRunCreate(BaseModel):
    trigger_type: str = Field(default="MANUAL", pattern="^(MANUAL|SCHEDULED|BACKTEST)$")
    horizon_days: int = Field(gt=0)
    train_start_date: date | None = None
    train_end_date: date | None = None
    forecast_start_date: date | None = None
    series_count: int = Field(default=0, ge=0)
    remark: str | None = Field(default=None, max_length=255)


class ForecastRunFinishIn(BaseModel):
    status: str = Field(pattern="^(SUCCESS|PARTIAL|FAILED)$")
    error_summary: str | None = None


class ForecastRunOut(ORMBase):
    id: int
    run_no: str
    trigger_type: str
    status: str
    horizon_days: int
    train_start_date: date | None
    train_end_date: date | None
    forecast_start_date: date | None
    series_count: int
    success_count: int
    failed_count: int
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error_summary: str | None
    remark: str | None


class ForecastResultIn(BaseModel):
    series_key: str | None = Field(default=None, max_length=64)
    material_id: int
    warehouse_id: int | None = None
    forecast_date: date
    horizon_step: int = Field(gt=0)
    y_hat: Decimal = Field(ge=0)
    y_lower: Decimal | None = Field(default=None, ge=0)
    y_upper: Decimal | None = Field(default=None, ge=0)
    model_code: str | None = Field(default=None, max_length=64)
    model_version: str | None = Field(default=None, max_length=32)
    demand_class: str | None = Field(default=None, pattern="^(SMOOTH|ERRATIC|INTERMITTENT|LUMPY)$")


class ForecastResultBulkIn(BaseModel):
    items: list[ForecastResultIn] = Field(min_length=1)


class ForecastResultOut(ORMBase):
    id: int
    run_id: int
    series_key: str
    material_id: int
    warehouse_id: int | None
    forecast_date: date
    horizon_step: int
    y_hat: Decimal
    y_lower: Decimal | None
    y_upper: Decimal | None
    model_code: str | None
    model_version: str | None
    demand_class: str | None
    created_at: datetime


class IngestResult(BaseModel):
    inserted: int
    updated: int
    series_count: int
