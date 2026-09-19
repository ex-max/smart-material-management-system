"""预测与决策组（一）——预测基础 ORM（docs/db-schema.md §12.1–§12.4）。

demand_series_meta / model_registry / forecast_run / forecast_result。
边界（AGENTS 不变量 4）：本组只读业务表，只写 forecast_* 表；预测失败不得影响业务单据。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.model.base import PK, AuditMixin, utcnow

# PG 用 jsonb，SQLite（测试）退化为通用 JSON
JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")

_DEMAND_CLASS_CHECK = "demand_class IN ('SMOOTH','ERRATIC','INTERMITTENT','LUMPY')"
_ABC_CHECK = "abc_class IN ('A','B','C')"
_MODEL_TYPE_CHECK = (
    "model_type IN ('NAIVE','SEASONAL_NAIVE','MA','ETS','ARIMA','SARIMA','RIDGE','RF',"
    "'LIGHTGBM','XGBOOST','CROSTON','TSB','LSTM','TCN')"
)
_MODEL_STATUS_CHECK = "status IN ('TRAINING','READY','ARCHIVED','FAILED')"
_TRIGGER_TYPE_CHECK = "trigger_type IN ('MANUAL','SCHEDULED','BACKTEST')"
_RUN_STATUS_CHECK = "status IN ('RUNNING','SUCCESS','PARTIAL','FAILED')"


class DemandSeriesMeta(Base, AuditMixin):
    """需求序列元数据：ADI/CV² 分层、ABC、均值/波动（供决策服务读取 σD）。"""

    __tablename__ = "demand_series_meta"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    series_key: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"))
    data_start_date: Mapped[date | None] = mapped_column(Date)
    data_end_date: Mapped[date | None] = mapped_column(Date)
    obs_days: Mapped[int | None] = mapped_column(Integer)
    non_zero_days: Mapped[int | None] = mapped_column(Integer)
    adi: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    cv2: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    demand_class: Mapped[str | None] = mapped_column(String(16))
    abc_class: Mapped[str | None] = mapped_column(String(1))
    mean_daily: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    std_daily: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    last_calc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("uq_demand_series_meta_series_key", "series_key", unique=True),
        CheckConstraint(
            "demand_class IS NULL OR " + _DEMAND_CLASS_CHECK, name="ck_demand_series_meta_demand_class"
        ),
        CheckConstraint("abc_class IS NULL OR " + _ABC_CHECK, name="ck_demand_series_meta_abc_class"),
        CheckConstraint("obs_days IS NULL OR obs_days >= 0", name="ck_demand_series_meta_obs_days"),
        CheckConstraint(
            "non_zero_days IS NULL OR non_zero_days >= 0", name="ck_demand_series_meta_non_zero_days"
        ),
        CheckConstraint("mean_daily IS NULL OR mean_daily >= 0", name="ck_dsm_mean_daily"),
        CheckConstraint("std_daily IS NULL OR std_daily >= 0", name="ck_dsm_std_daily"),
        Index("ix_dsm_material_warehouse", "material_id", "warehouse_id"),
        Index("ix_dsm_demand_class", "demand_class"),
    )


class ModelRegistry(Base, AuditMixin):
    """模型注册表：版本、超参/特征/指标快照与产物路径（不入 git）。"""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    model_code: Mapped[str] = mapped_column(String(64), nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON_VARIANT)
    feature_config: Mapped[dict | None] = mapped_column(JSON_VARIANT)
    metrics: Mapped[dict | None] = mapped_column(JSON_VARIANT)
    artifact_path: Mapped[str | None] = mapped_column(String(255))
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trained_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="READY", nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("uq_model_registry_code_version", "model_code", "version", unique=True),
        CheckConstraint(_MODEL_TYPE_CHECK, name="ck_model_registry_model_type"),
        CheckConstraint(_MODEL_STATUS_CHECK, name="ck_model_registry_status"),
        Index("ix_model_registry_type_active", "model_type", "is_active"),
    )


class ForecastRun(Base, AuditMixin):
    """预测批次：一次批量预测 = 一个 run。"""

    __tablename__ = "forecast_run"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    run_no: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING", nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    train_start_date: Mapped[date | None] = mapped_column(Date)
    train_end_date: Mapped[date | None] = mapped_column(Date)
    forecast_start_date: Mapped[date | None] = mapped_column(Date)
    series_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(String(255))

    results: Mapped[list["ForecastResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("uq_forecast_run_run_no", "run_no", unique=True),
        CheckConstraint(_TRIGGER_TYPE_CHECK, name="ck_forecast_run_trigger_type"),
        CheckConstraint(_RUN_STATUS_CHECK, name="ck_forecast_run_status"),
        CheckConstraint("horizon_days > 0", name="ck_forecast_run_horizon_days"),
        CheckConstraint("series_count >= 0", name="ck_forecast_run_series_count"),
        CheckConstraint("success_count >= 0", name="ck_forecast_run_success_count"),
        CheckConstraint("failed_count >= 0", name="ck_forecast_run_failed_count"),
        Index("ix_forecast_run_status_started", "status", "started_at"),
    )


class ForecastResult(Base):
    """预测结果：追加写（只 INSERT），按 (run_id, series_key, forecast_date) 唯一。"""

    __tablename__ = "forecast_result"

    id: Mapped[int] = mapped_column(PK, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("forecast_run.id", ondelete="CASCADE"), nullable=False
    )
    series_key: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouse.id", ondelete="RESTRICT"))
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_step: Mapped[int] = mapped_column(Integer, nullable=False)
    y_hat: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    y_lower: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    y_upper: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    model_code: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(32))
    demand_class: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    run: Mapped["ForecastRun"] = relationship(back_populates="results")

    __table_args__ = (
        Index("uq_forecast_result_run_series_date", "run_id", "series_key", "forecast_date", unique=True),
        CheckConstraint("horizon_step > 0", name="ck_forecast_result_horizon_step"),
        CheckConstraint("y_hat >= 0", name="ck_forecast_result_y_hat"),
        CheckConstraint("y_lower IS NULL OR y_lower >= 0", name="ck_forecast_result_y_lower"),
        CheckConstraint("y_upper IS NULL OR y_upper >= 0", name="ck_forecast_result_y_upper"),
        CheckConstraint(
            "y_lower IS NULL OR y_upper IS NULL OR (y_lower <= y_hat AND y_hat <= y_upper)",
            name="ck_forecast_result_interval",
        ),
        Index("ix_forecast_result_material_date", "material_id", "forecast_date"),
        Index("ix_forecast_result_run_id", "run_id"),
    )
