"""预测与决策数据访问：需求序列元数据 / 模型注册 / 预测批次 / 预测结果。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.model.forecast import DemandSeriesMeta, ForecastResult, ForecastRun, ModelRegistry


class DemandSeriesMetaRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_by_key(self, series_key: str):
        stmt = select(DemandSeriesMeta).where(
            DemandSeriesMeta.series_key == series_key, DemandSeriesMeta.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_pair(self, material_id: int, warehouse_id: int | None):
        stmt = select(DemandSeriesMeta).where(
            DemandSeriesMeta.material_id == material_id,
            DemandSeriesMeta.warehouse_id.is_(warehouse_id)
            if warehouse_id is None
            else DemandSeriesMeta.warehouse_id == warehouse_id,
            DemandSeriesMeta.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list(self, offset: int, limit: int, material_id: int | None = None):
        stmt = select(DemandSeriesMeta).where(DemandSeriesMeta.deleted_at.is_(None))
        if material_id is not None:
            stmt = stmt.where(DemandSeriesMeta.material_id == material_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(DemandSeriesMeta.id).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def by_pairs(self) -> dict[tuple[int, int | None], DemandSeriesMeta]:
        stmt = select(DemandSeriesMeta).where(DemandSeriesMeta.deleted_at.is_(None))
        return {(row.material_id, row.warehouse_id): row for row in self.db.execute(stmt).scalars().all()}


class ModelRegistryRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, model_id: int):
        obj = self.db.get(ModelRegistry, model_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def find_by_code_version(self, model_code: str, version: str):
        stmt = select(ModelRegistry).where(
            ModelRegistry.model_code == model_code,
            ModelRegistry.version == version,
            ModelRegistry.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, offset: int, limit: int, model_type: str | None = None):
        stmt = select(ModelRegistry).where(ModelRegistry.deleted_at.is_(None))
        if model_type:
            stmt = stmt.where(ModelRegistry.model_type == model_type)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(ModelRegistry.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)


class ForecastRunRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, run_id: int):
        obj = self.db.get(ForecastRun, run_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def list(self, offset: int, limit: int, status: str | None = None):
        stmt = select(ForecastRun).where(ForecastRun.deleted_at.is_(None))
        if status:
            stmt = stmt.where(ForecastRun.status == status)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(ForecastRun.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def next_run_no(self, day: date | None = None) -> str:
        day = day or date.today()
        prefix = "FR-%s-" % day.strftime("%Y%m%d")
        latest = self.db.execute(
            select(func.max(ForecastRun.run_no)).where(ForecastRun.run_no.like(prefix + "%"))
        ).scalar_one_or_none()
        seq = 1
        if latest:
            tail = latest.rsplit("-", 1)[-1]
            if tail.isdigit():
                seq = int(tail) + 1
        return "%s%04d" % (prefix, seq)


class ForecastResultRepo:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def find(self, run_id: int, series_key: str, forecast_date: date):
        stmt = select(ForecastResult).where(
            ForecastResult.run_id == run_id,
            ForecastResult.series_key == series_key,
            ForecastResult.forecast_date == forecast_date,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_run(self, run_id: int, offset: int, limit: int):
        stmt = select(ForecastResult).where(ForecastResult.run_id == run_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = (
            self.db.execute(
                stmt.order_by(ForecastResult.series_key, ForecastResult.forecast_date)
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    def distinct_series_count(self, run_id: int) -> int:
        stmt = select(func.count(func.distinct(ForecastResult.series_key))).where(ForecastResult.run_id == run_id)
        return int(self.db.execute(stmt).scalar_one())

    def latest_by_pair(self) -> dict[tuple[int, int | None], dict]:
        """每个 (material_id, warehouse_id) 取最新成功批次的结果均值，供决策服务计算 D̂。"""
        pairs = self.db.execute(
            select(
                ForecastResult.material_id,
                ForecastResult.warehouse_id,
                func.max(ForecastResult.run_id),
            )
            .join(ForecastRun, ForecastRun.id == ForecastResult.run_id)
            .where(ForecastRun.status.in_(("SUCCESS", "PARTIAL")))
            .group_by(ForecastResult.material_id, ForecastResult.warehouse_id)
        ).all()
        latest = {(m, w): rid for m, w, rid in pairs}
        if not latest:
            return {}
        run_ids = set(latest.values())
        rows = self.db.execute(
            select(
                ForecastResult.material_id,
                ForecastResult.warehouse_id,
                ForecastResult.run_id,
                func.avg(ForecastResult.y_hat),
                func.max(ForecastResult.model_code),
            )
            .where(ForecastResult.run_id.in_(run_ids))
            .group_by(ForecastResult.material_id, ForecastResult.warehouse_id, ForecastResult.run_id)
        ).all()
        result: dict[tuple[int, int | None], dict] = {}
        for material_id, warehouse_id, run_id, avg, model_code in rows:
            if latest.get((material_id, warehouse_id)) == run_id:
                result[(material_id, warehouse_id)] = {
                    "avg": Decimal(str(avg)) if avg is not None else Decimal("0"),
                    "run_id": int(run_id),
                    "model_code": model_code,
                }
        return result
