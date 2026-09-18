from sqlalchemy import func, select

from app.model.master import Location, Material, MaterialCategory, Supplier, Unit, Warehouse


class BaseRepo:
    model = None

    def __init__(self, db) -> None:
        self.db = db

    def get(self, obj_id: int):
        return self.db.get(self.model, obj_id)

    def get_active(self, obj_id: int):
        obj = self.db.get(self.model, obj_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def _cond(self, field: str, value):
        column = getattr(self.model, field)
        return column.is_(None) if value is None else column == value

    def list(self, offset: int, limit: int) -> tuple[list, int]:
        stmt = select(self.model).where(self.model.deleted_at.is_(None))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(self.model.id).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def find_by(self, field: str, value, exclude_id: int | None = None):
        stmt = select(self.model).where(self._cond(field, value), self.model.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def find_by_pair(self, field_a: str, value_a, field_b: str, value_b, exclude_id: int | None = None):
        stmt = select(self.model).where(
            self._cond(field_a, value_a), self._cond(field_b, value_b), self.model.deleted_at.is_(None)
        )
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj


class MaterialCategoryRepo(BaseRepo):
    model = MaterialCategory


class UnitRepo(BaseRepo):
    model = Unit


class SupplierRepo(BaseRepo):
    model = Supplier


class WarehouseRepo(BaseRepo):
    model = Warehouse


class LocationRepo(BaseRepo):
    model = Location


class MaterialRepo(BaseRepo):
    model = Material
