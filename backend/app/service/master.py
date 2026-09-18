from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.model.base import utcnow
from app.repository.master import (
    BaseRepo,
    LocationRepo,
    MaterialCategoryRepo,
    MaterialRepo,
    SupplierRepo,
    UnitRepo,
    WarehouseRepo,
)
from app.repository.user import UserRepository


class CrudService:
    repo_cls: type[BaseRepo]
    label = "记录"
    unique_fields: tuple[str, ...] = ()

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = self.repo_cls(db)

    def list(self, page: int, page_size: int):
        return self.repo.list((page - 1) * page_size, page_size)

    def get(self, item_id: int):
        obj = self.repo.get_active(item_id)
        if obj is None:
            raise NotFound(self.label + "不存在")
        return obj

    def create(self, payload, operator_id: int | None = None):
        data = payload.model_dump(exclude_unset=True)
        self.validate(data)
        self.check_unique(data)
        obj = self.repo.model(**data)
        obj.created_by = operator_id
        self.repo.add(obj)
        self.after_create(obj, data)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, item_id: int, payload):
        obj = self.get(item_id)
        data = payload.model_dump(exclude_unset=True)
        self.validate(data, obj)
        self.check_unique(data, exclude_id=item_id)
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, item_id: int) -> None:
        obj = self.get(item_id)
        obj.deleted_at = utcnow()
        self.db.commit()

    def validate(self, data: dict, obj=None) -> None:
        return None

    def after_create(self, obj, data: dict) -> None:
        return None

    def check_unique(self, data: dict, exclude_id: int | None = None) -> None:
        for field in self.unique_fields:
            if field in data:
                found = self.repo.find_by(field, data[field], exclude_id=exclude_id)
                if found is not None:
                    raise Conflict(self.label + "编码已存在：" + str(data[field]))


class MaterialCategoryService(CrudService):
    repo_cls = MaterialCategoryRepo
    label = "物资分类"

    def check_unique(self, data: dict, exclude_id: int | None = None) -> None:
        if "code" not in data:
            return
        found = self.repo.find_by_pair(
            "parent_id", data.get("parent_id"), "code", data["code"], exclude_id=exclude_id
        )
        if found is not None:
            raise Conflict("同级分类编码已存在：" + str(data["code"]))

    def create(self, payload, operator_id: int | None = None):
        data = payload.model_dump(exclude_unset=True)
        parent = None
        if data.get("parent_id") is not None:
            parent = self.repo.get_active(data["parent_id"])
            if parent is None:
                raise BadRequest("父分类不存在")
        self.check_unique(data)
        obj = self.repo.model(**data)
        obj.created_by = operator_id
        obj.level = (parent.level + 1) if parent else 1
        if obj.level > 5:
            raise BadRequest("分类层级不能超过 5 级")
        self.repo.add(obj)
        prefix = parent.path if parent else "/"
        obj.path = prefix + str(obj.id) + "/"
        self.db.commit()
        self.db.refresh(obj)
        return obj


class UnitService(CrudService):
    repo_cls = UnitRepo
    label = "计量单位"
    unique_fields = ("code",)


class SupplierService(CrudService):
    repo_cls = SupplierRepo
    label = "供应商"
    unique_fields = ("code",)


class WarehouseService(CrudService):
    repo_cls = WarehouseRepo
    label = "仓库"
    unique_fields = ("code",)

    def validate(self, data: dict, obj=None) -> None:
        manager_id = data.get("manager_id")
        if manager_id is not None and UserRepository(self.db).get(manager_id) is None:
            raise BadRequest("负责人不存在")


class LocationService(CrudService):
    repo_cls = LocationRepo
    label = "库位"

    def check_unique(self, data: dict, exclude_id: int | None = None) -> None:
        if "code" not in data:
            return
        found = self.repo.find_by_pair(
            "warehouse_id", data.get("warehouse_id"), "code", data["code"], exclude_id=exclude_id
        )
        if found is not None:
            raise Conflict("同一仓库下库位编码已存在：" + str(data["code"]))

    def validate(self, data: dict, obj=None) -> None:
        warehouse_id = data.get("warehouse_id")
        if warehouse_id is not None and WarehouseRepo(self.db).get_active(warehouse_id) is None:
            raise BadRequest("仓库不存在")


class MaterialService(CrudService):
    repo_cls = MaterialRepo
    label = "物资"
    unique_fields = ("code",)

    def validate(self, data: dict, obj=None) -> None:
        if data.get("category_id") is not None and MaterialCategoryRepo(self.db).get_active(data["category_id"]) is None:
            raise BadRequest("物资分类不存在")
        if data.get("unit_id") is not None and UnitRepo(self.db).get_active(data["unit_id"]) is None:
            raise BadRequest("计量单位不存在")
        if data.get("default_supplier_id") is not None and SupplierRepo(self.db).get_active(data["default_supplier_id"]) is None:
            raise BadRequest("供应商不存在")
