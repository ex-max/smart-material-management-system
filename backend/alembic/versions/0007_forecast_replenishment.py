"""预测与决策：demand_series_meta / model_registry / forecast_run / forecast_result /
replenishment_policy / replenishment_suggestion（docs/db-schema.md §12）。

Revision ID: 0007_forecast_replenishment
Revises: 0006_ledger
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_forecast_replenishment"
down_revision = "0006_ledger"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
_RS_OPEN_WHERE = "status IN ('OPEN','SUGGESTED') AND deleted_at IS NULL"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "demand_series_meta",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("series_key", sa.String(64), nullable=False, comment="序列键 material_id:warehouse_id"),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT")),
        sa.Column("data_start_date", sa.Date()),
        sa.Column("data_end_date", sa.Date()),
        sa.Column("obs_days", sa.Integer()),
        sa.Column("non_zero_days", sa.Integer()),
        sa.Column("adi", sa.Numeric(10, 4)),
        sa.Column("cv2", sa.Numeric(10, 4)),
        sa.Column("demand_class", sa.String(16)),
        sa.Column("abc_class", sa.String(1)),
        sa.Column("mean_daily", sa.Numeric(18, 4)),
        sa.Column("std_daily", sa.Numeric(18, 4)),
        sa.Column("last_calc_at", sa.DateTime(timezone=True)),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint(
            "demand_class IS NULL OR demand_class IN ('SMOOTH','ERRATIC','INTERMITTENT','LUMPY')",
            name="ck_demand_series_meta_demand_class",
        ),
        sa.CheckConstraint("abc_class IS NULL OR abc_class IN ('A','B','C')", name="ck_demand_series_meta_abc_class"),
        sa.CheckConstraint("obs_days IS NULL OR obs_days >= 0", name="ck_demand_series_meta_obs_days"),
        sa.CheckConstraint("non_zero_days IS NULL OR non_zero_days >= 0", name="ck_demand_series_meta_non_zero_days"),
        sa.CheckConstraint("mean_daily IS NULL OR mean_daily >= 0", name="ck_dsm_mean_daily"),
        sa.CheckConstraint("std_daily IS NULL OR std_daily >= 0", name="ck_dsm_std_daily"),
        comment="需求序列元数据",
    )
    op.create_index("uq_demand_series_meta_series_key", "demand_series_meta", ["series_key"], unique=True)
    op.create_index("ix_dsm_material_warehouse", "demand_series_meta", ["material_id", "warehouse_id"])
    op.create_index("ix_dsm_demand_class", "demand_series_meta", ["demand_class"])

    op.create_table(
        "model_registry",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("model_code", sa.String(64), nullable=False, comment="模型编码"),
        sa.Column("model_type", sa.String(32), nullable=False, comment="模型类别"),
        sa.Column("version", sa.String(32), nullable=False, comment="版本"),
        sa.Column("params", _JSON, comment="超参快照"),
        sa.Column("feature_config", _JSON, comment="特征配置快照"),
        sa.Column("metrics", _JSON, comment="验证指标快照"),
        sa.Column("artifact_path", sa.String(255), comment="模型文件相对路径（不入 git）"),
        sa.Column("trained_at", sa.DateTime(timezone=True)),
        sa.Column("trained_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(16), nullable=False, server_default="READY"),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint(
            "model_type IN ('NAIVE','SEASONAL_NAIVE','MA','ETS','ARIMA','SARIMA','RIDGE','RF',"
            "'LIGHTGBM','XGBOOST','CROSTON','TSB','LSTM','TCN')",
            name="ck_model_registry_model_type",
        ),
        sa.CheckConstraint("status IN ('TRAINING','READY','ARCHIVED','FAILED')", name="ck_model_registry_status"),
        comment="模型注册表",
    )
    op.create_index("uq_model_registry_code_version", "model_registry", ["model_code", "version"], unique=True)
    op.create_index("ix_model_registry_type_active", "model_registry", ["model_type", "is_active"])

    op.create_table(
        "forecast_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("run_no", sa.String(32), nullable=False, comment="批次号 FR-YYYYMMDD-####"),
        sa.Column("trigger_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="RUNNING"),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("train_start_date", sa.Date()),
        sa.Column("train_end_date", sa.Date()),
        sa.Column("forecast_start_date", sa.Date()),
        sa.Column("series_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("trigger_type IN ('MANUAL','SCHEDULED','BACKTEST')", name="ck_forecast_run_trigger_type"),
        sa.CheckConstraint("status IN ('RUNNING','SUCCESS','PARTIAL','FAILED')", name="ck_forecast_run_status"),
        sa.CheckConstraint("horizon_days > 0", name="ck_forecast_run_horizon_days"),
        sa.CheckConstraint("series_count >= 0", name="ck_forecast_run_series_count"),
        sa.CheckConstraint("success_count >= 0", name="ck_forecast_run_success_count"),
        sa.CheckConstraint("failed_count >= 0", name="ck_forecast_run_failed_count"),
        comment="预测批次",
    )
    op.create_index("uq_forecast_run_run_no", "forecast_run", ["run_no"], unique=True)
    op.create_index("ix_forecast_run_status_started", "forecast_run", ["status", "started_at"])

    op.create_table(
        "forecast_result",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("forecast_run.id", ondelete="CASCADE"),
            nullable=False,
            comment="预测批次",
        ),
        sa.Column("series_key", sa.String(64), nullable=False),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT")),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("horizon_step", sa.Integer(), nullable=False),
        sa.Column("y_hat", sa.Numeric(18, 4), nullable=False),
        sa.Column("y_lower", sa.Numeric(18, 4)),
        sa.Column("y_upper", sa.Numeric(18, 4)),
        sa.Column("model_code", sa.String(64)),
        sa.Column("model_version", sa.String(32)),
        sa.Column("demand_class", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("horizon_step > 0", name="ck_forecast_result_horizon_step"),
        sa.CheckConstraint("y_hat >= 0", name="ck_forecast_result_y_hat"),
        sa.CheckConstraint("y_lower IS NULL OR y_lower >= 0", name="ck_forecast_result_y_lower"),
        sa.CheckConstraint("y_upper IS NULL OR y_upper >= 0", name="ck_forecast_result_y_upper"),
        sa.CheckConstraint(
            "y_lower IS NULL OR y_upper IS NULL OR (y_lower <= y_hat AND y_hat <= y_upper)",
            name="ck_forecast_result_interval",
        ),
        comment="预测结果（只 INSERT）",
    )
    op.create_index(
        "uq_forecast_result_run_series_date",
        "forecast_result",
        ["run_id", "series_key", "forecast_date"],
        unique=True,
    )
    op.create_index("ix_forecast_result_material_date", "forecast_result", ["material_id", "forecast_date"])
    op.create_index("ix_forecast_result_run_id", "forecast_result", ["run_id"])

    op.create_table(
        "replenishment_policy",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("policy_code", sa.String(32), nullable=False, comment="策略编码"),
        sa.Column("policy_name", sa.String(64)),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT")),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT")),
        sa.Column("strategy", sa.String(16), nullable=False, comment="FIXED/FORECAST/EOQ/MIN_MAX"),
        sa.Column("service_level_type", sa.String(16), comment="CSL/FILL_RATE"),
        sa.Column("service_level", sa.Numeric(5, 2), comment="小数口径 0<x<1（如 0.95）"),
        sa.Column("z_value", sa.Numeric(6, 3), comment="正态分位数"),
        sa.Column("review_period_days", sa.Integer()),
        sa.Column("order_cost", sa.Numeric(18, 4)),
        sa.Column("holding_cost_rate", sa.Numeric(9, 6)),
        sa.Column("min_order_qty", sa.Numeric(18, 4)),
        sa.Column("pack_size", sa.Numeric(18, 4)),
        sa.Column("lead_time_days", sa.Numeric(8, 2)),
        sa.Column("safety_stock_override", sa.Numeric(18, 4)),
        sa.Column("rop_override", sa.Numeric(18, 4)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.Date()),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint("strategy IN ('FIXED','FORECAST','EOQ','MIN_MAX')", name="ck_replenishment_policy_strategy"),
        sa.CheckConstraint(
            "service_level_type IS NULL OR service_level_type IN ('CSL','FILL_RATE')",
            name="ck_replenishment_policy_service_level_type",
        ),
        sa.CheckConstraint(
            "service_level IS NULL OR (service_level > 0 AND service_level < 1)",
            name="ck_replenishment_policy_service_level",
        ),
        sa.CheckConstraint("z_value IS NULL OR z_value >= 0", name="ck_replenishment_policy_z_value"),
        sa.CheckConstraint(
            "review_period_days IS NULL OR review_period_days > 0", name="ck_replenishment_policy_review_period"
        ),
        sa.CheckConstraint("order_cost IS NULL OR order_cost >= 0", name="ck_replenishment_policy_order_cost"),
        sa.CheckConstraint(
            "holding_cost_rate IS NULL OR holding_cost_rate >= 0", name="ck_replenishment_policy_holding_cost"
        ),
        sa.CheckConstraint("min_order_qty IS NULL OR min_order_qty > 0", name="ck_replenishment_policy_min_order_qty"),
        sa.CheckConstraint("pack_size IS NULL OR pack_size > 0", name="ck_replenishment_policy_pack_size"),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days > 0", name="ck_replenishment_policy_lead_time"),
        sa.CheckConstraint(
            "safety_stock_override IS NULL OR safety_stock_override >= 0",
            name="ck_replenishment_policy_ss_override",
        ),
        sa.CheckConstraint("rop_override IS NULL OR rop_override >= 0", name="ck_replenishment_policy_rop_override"),
        comment="补货策略参数",
    )
    op.create_index(
        "uq_replenishment_policy_code",
        "replenishment_policy",
        ["policy_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_replenishment_policy_material_warehouse", "replenishment_policy", ["material_id", "warehouse_id"]
    )

    op.create_table(
        "replenishment_suggestion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, comment="主键"),
        sa.Column("suggestion_no", sa.String(32), nullable=False, comment="建议号 RS-YYYYMMDD-####"),
        sa.Column("material_id", sa.BigInteger(), sa.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), sa.ForeignKey("replenishment_policy.id", ondelete="RESTRICT")),
        sa.Column("forecast_run_id", sa.BigInteger(), sa.ForeignKey("forecast_run.id", ondelete="RESTRICT")),
        sa.Column("trigger_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("current_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("locked_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("in_transit_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("available_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("daily_demand_hat", sa.Numeric(18, 4)),
        sa.Column("lead_time_days", sa.Numeric(8, 2)),
        sa.Column("sigma_d", sa.Numeric(18, 4)),
        sa.Column("sigma_lt", sa.Numeric(8, 2)),
        sa.Column("safety_stock", sa.Numeric(18, 4)),
        sa.Column("rop", sa.Numeric(18, 4)),
        sa.Column("eoq", sa.Numeric(18, 4)),
        sa.Column("suggested_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("final_qty", sa.Numeric(18, 4)),
        sa.Column("reason", sa.Text(), comment="触发依据（可解释性）"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("converted_pr_id", sa.BigInteger(), sa.ForeignKey("purchase_requisition.id", ondelete="RESTRICT")),
        sa.Column("converted_at", sa.DateTime(timezone=True)),
        sa.Column("handled_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("remark", sa.String(255)),
        *_audit_columns(),
        sa.CheckConstraint(
            "trigger_type IN ('BELOW_ROP','FORECAST','SAFETY','MANUAL')",
            name="ck_replenishment_suggestion_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','SUGGESTED','CONVERTED','REJECTED','EXPIRED','CLOSED')",
            name="ck_replenishment_suggestion_status",
        ),
        sa.CheckConstraint("suggested_qty >= 0", name="ck_replenishment_suggestion_suggested_qty"),
        sa.CheckConstraint("final_qty IS NULL OR final_qty >= 0", name="ck_replenishment_suggestion_final_qty"),
        comment="补货建议（可解释）",
    )
    op.create_index(
        "uq_replenishment_suggestion_no", "replenishment_suggestion", ["suggestion_no"], unique=True
    )
    op.create_index(
        "uq_rs_open",
        "replenishment_suggestion",
        ["material_id", "warehouse_id"],
        unique=True,
        postgresql_where=sa.text(_RS_OPEN_WHERE),
    )
    op.create_index("ix_rs_status_generated", "replenishment_suggestion", ["status", "generated_at"])
    op.create_index("ix_rs_material_warehouse", "replenishment_suggestion", ["material_id", "warehouse_id"])


def downgrade() -> None:
    op.drop_index("ix_rs_material_warehouse", table_name="replenishment_suggestion")
    op.drop_index("ix_rs_status_generated", table_name="replenishment_suggestion")
    op.drop_index("uq_rs_open", table_name="replenishment_suggestion")
    op.drop_index("uq_replenishment_suggestion_no", table_name="replenishment_suggestion")
    op.drop_table("replenishment_suggestion")

    op.drop_index("ix_replenishment_policy_material_warehouse", table_name="replenishment_policy")
    op.drop_index("uq_replenishment_policy_code", table_name="replenishment_policy")
    op.drop_table("replenishment_policy")

    op.drop_index("ix_forecast_result_run_id", table_name="forecast_result")
    op.drop_index("ix_forecast_result_material_date", table_name="forecast_result")
    op.drop_index("uq_forecast_result_run_series_date", table_name="forecast_result")
    op.drop_table("forecast_result")

    op.drop_index("ix_forecast_run_status_started", table_name="forecast_run")
    op.drop_index("uq_forecast_run_run_no", table_name="forecast_run")
    op.drop_table("forecast_run")

    op.drop_index("ix_model_registry_type_active", table_name="model_registry")
    op.drop_index("uq_model_registry_code_version", table_name="model_registry")
    op.drop_table("model_registry")

    op.drop_index("ix_dsm_demand_class", table_name="demand_series_meta")
    op.drop_index("ix_dsm_material_warehouse", table_name="demand_series_meta")
    op.drop_index("uq_demand_series_meta_series_key", table_name="demand_series_meta")
    op.drop_table("demand_series_meta")
