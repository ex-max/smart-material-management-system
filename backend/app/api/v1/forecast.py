"""预测模块 API：批次/结果/需求元数据/模型注册。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.model.user import User
from app.schema import forecast as fs
from app.service.forecast import DemandSeriesMetaService, ForecastService, ModelRegistryService

router = APIRouter(tags=["预测"])

_VIEW = require_perm(Perm.FORECAST_VIEW)
_MANAGE = require_perm(Perm.FORECAST_MANAGE)


# ---------------- 预测批次 ----------------
@router.post("/forecast-runs", status_code=201, name="create_forecast_run")
def create_forecast_run(
    payload: fs.ForecastRunCreate, user: User = Depends(_MANAGE), db: Session = Depends(get_db)
):
    return ok(fs.ForecastRunOut.model_validate(ForecastService(db).create_run(payload, user.id)).model_dump())


@router.get("/forecast-runs", name="list_forecast_runs")
def list_forecast_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = ForecastService(db).list_runs(page, page_size, status)
    return ok({"total": total, "items": [fs.ForecastRunOut.model_validate(x).model_dump() for x in items]})


@router.get("/forecast-runs/{run_id}", name="get_forecast_run")
def get_forecast_run(run_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(fs.ForecastRunOut.model_validate(ForecastService(db).get_run(run_id)).model_dump())


@router.post("/forecast-runs/{run_id}/results", name="add_forecast_results")
def add_forecast_results(
    run_id: int,
    payload: fs.ForecastResultBulkIn,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(ForecastService(db).add_results(run_id, payload))


@router.get("/forecast-runs/{run_id}/results", name="list_forecast_results")
def list_forecast_results(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = ForecastService(db).list_results(run_id, page, page_size)
    return ok({"total": total, "items": [fs.ForecastResultOut.model_validate(x).model_dump() for x in items]})


@router.post("/forecast-runs/{run_id}/finish", name="finish_forecast_run")
def finish_forecast_run(
    run_id: int,
    payload: fs.ForecastRunFinishIn,
    user: User = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    return ok(fs.ForecastRunOut.model_validate(ForecastService(db).finish_run(run_id, payload)).model_dump())


# ---------------- 需求序列元数据 ----------------
@router.get("/demand-series-meta", name="list_demand_series_meta")
def list_demand_series_meta(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    material_id: int | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = DemandSeriesMetaService(db).list(page, page_size, material_id)
    return ok({"total": total, "items": [fs.DemandSeriesMetaOut.model_validate(x).model_dump() for x in items]})


@router.post("/demand-series-meta", name="upsert_demand_series_meta")
def upsert_demand_series_meta(
    payload: fs.DemandSeriesMetaIn, user: User = Depends(_MANAGE), db: Session = Depends(get_db)
):
    row = DemandSeriesMetaService(db).upsert(payload, user.id)
    return ok(fs.DemandSeriesMetaOut.model_validate(row).model_dump())


# ---------------- 模型注册 ----------------
@router.get("/model-registry", name="list_model_registry")
def list_model_registry(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    model_type: str | None = Query(None),
    user: User = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    items, total = ModelRegistryService(db).list(page, page_size, model_type)
    return ok({"total": total, "items": [fs.ModelRegistryOut.model_validate(x).model_dump() for x in items]})


@router.post("/model-registry", status_code=201, name="create_model_registry")
def create_model_registry(
    payload: fs.ModelRegistryCreate, user: User = Depends(_MANAGE), db: Session = Depends(get_db)
):
    return ok(fs.ModelRegistryOut.model_validate(ModelRegistryService(db).create(payload, user.id)).model_dump())


@router.get("/model-registry/{model_id}", name="get_model_registry")
def get_model_registry(model_id: int, user: User = Depends(_VIEW), db: Session = Depends(get_db)):
    return ok(fs.ModelRegistryOut.model_validate(ModelRegistryService(db).get(model_id)).model_dump())
