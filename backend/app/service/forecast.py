"""预测业务：需求序列元数据、模型注册、预测批次与结果入库。

边界（AGENTS 不变量 4）：本模块只写 forecast_* 表，绝不回写业务表。
"""

from datetime import timezone

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.model.base import utcnow
from app.model.forecast import DemandSeriesMeta, ForecastResult, ForecastRun, ModelRegistry
from app.repository.forecast import (
    DemandSeriesMetaRepo,
    ForecastResultRepo,
    ForecastRunRepo,
    ModelRegistryRepo,
)
from app.repository.master import MaterialRepo, WarehouseRepo


def series_key_for(material_id: int, warehouse_id: int | None) -> str:
    return "%d:%d" % (material_id, warehouse_id or 0)


class ForecastService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.runs = ForecastRunRepo(db)
        self.results = ForecastResultRepo(db)

    def list_runs(self, page: int, page_size: int, status: str | None = None):
        return self.runs.list((page - 1) * page_size, page_size, status)

    def get_run(self, run_id: int) -> ForecastRun:
        obj = self.runs.get_active(run_id)
        if obj is None:
            raise NotFound("预测批次不存在")
        return obj

    def create_run(self, payload, operator_id: int) -> ForecastRun:
        obj = ForecastRun(
            run_no=self.runs.next_run_no(),
            trigger_type=payload.trigger_type,
            status="RUNNING",
            horizon_days=payload.horizon_days,
            train_start_date=payload.train_start_date,
            train_end_date=payload.train_end_date,
            forecast_start_date=payload.forecast_start_date,
            series_count=payload.series_count,
            created_by=operator_id,
            remark=payload.remark,
        )
        self.runs.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def add_results(self, run_id: int, payload) -> dict:
        run = self.get_run(run_id)
        if run.status != "RUNNING":
            raise Conflict("仅 RUNNING 批次可写入预测结果，当前：" + run.status)
        inserted = 0
        updated = 0
        for item in payload.items:
            self._require_refs(item.material_id, item.warehouse_id)
            if item.y_lower is not None and item.y_upper is not None and not (item.y_lower <= item.y_hat <= item.y_upper):
                raise BadRequest("预测区间必须满足 y_lower <= y_hat <= y_upper")
            key = item.series_key or series_key_for(item.material_id, item.warehouse_id)
            row = self.results.find(run.id, key, item.forecast_date)
            values = {
                "horizon_step": item.horizon_step,
                "y_hat": item.y_hat,
                "y_lower": item.y_lower,
                "y_upper": item.y_upper,
                "model_code": item.model_code,
                "model_version": item.model_version,
                "demand_class": item.demand_class,
            }
            if row is None:
                row = ForecastResult(
                    run_id=run.id,
                    series_key=key,
                    material_id=item.material_id,
                    warehouse_id=item.warehouse_id,
                    forecast_date=item.forecast_date,
                    **values,
                )
                self.results.add(row)
                inserted += 1
            else:
                for field, value in values.items():
                    setattr(row, field, value)
                updated += 1
        series_count = self.results.distinct_series_count(run.id)
        run.series_count = max(run.series_count, series_count)
        run.success_count = max(run.success_count, series_count)
        self.db.commit()
        return {"inserted": inserted, "updated": updated, "series_count": series_count}

    def list_results(self, run_id: int, page: int, page_size: int):
        self.get_run(run_id)
        return self.results.list_by_run(run_id, (page - 1) * page_size, page_size)

    def finish_run(self, run_id: int, payload) -> ForecastRun:
        run = self.get_run(run_id)
        if run.status != "RUNNING":
            raise Conflict("批次已结束，当前：" + run.status)
        run.status = payload.status
        started_at = run.started_at
        if started_at.tzinfo is None:  # SQLite 不保留时区
            started_at = started_at.replace(tzinfo=timezone.utc)
        run.finished_at = utcnow()
        delta = run.finished_at - started_at
        run.duration_ms = max(int(delta.total_seconds() * 1000), 0)
        if payload.error_summary is not None:
            run.error_summary = payload.error_summary
        if payload.status == "FAILED":
            run.failed_count = max(run.series_count - run.success_count, 0)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _require_refs(self, material_id: int, warehouse_id: int | None) -> None:
        if MaterialRepo(self.db).get_active(material_id) is None:
            raise BadRequest("物资不存在：" + str(material_id))
        if warehouse_id is not None and WarehouseRepo(self.db).get_active(warehouse_id) is None:
            raise BadRequest("仓库不存在：" + str(warehouse_id))


class DemandSeriesMetaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DemandSeriesMetaRepo(db)

    def list(self, page: int, page_size: int, material_id: int | None = None):
        return self.repo.list((page - 1) * page_size, page_size, material_id)

    def upsert(self, payload, operator_id: int) -> DemandSeriesMeta:
        key = payload.series_key or series_key_for(payload.material_id, payload.warehouse_id)
        if MaterialRepo(self.db).get_active(payload.material_id) is None:
            raise BadRequest("物资不存在：" + str(payload.material_id))
        if payload.warehouse_id is not None and WarehouseRepo(self.db).get_active(payload.warehouse_id) is None:
            raise BadRequest("仓库不存在：" + str(payload.warehouse_id))
        row = self.repo.get_by_key(key)
        data = payload.model_dump(exclude={"series_key"})
        if row is None:
            row = DemandSeriesMeta(series_key=key, created_by=operator_id, **data)
            self.repo.add(row)
        else:
            for field, value in data.items():
                setattr(row, field, value)
        row.last_calc_at = payload.last_calc_at or utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row


class ModelRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ModelRegistryRepo(db)

    def list(self, page: int, page_size: int, model_type: str | None = None):
        return self.repo.list((page - 1) * page_size, page_size, model_type)

    def get(self, model_id: int) -> ModelRegistry:
        obj = self.repo.get_active(model_id)
        if obj is None:
            raise NotFound("模型不存在")
        return obj

    def create(self, payload, operator_id: int) -> ModelRegistry:
        if self.repo.find_by_code_version(payload.model_code, payload.version) is not None:
            raise Conflict("模型编码+版本已存在：" + payload.model_code + "/" + payload.version)
        obj = ModelRegistry(**payload.model_dump(), created_by=operator_id)
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
