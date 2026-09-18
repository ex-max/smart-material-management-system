from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core.database import get_db
from app.core.permissions import Perm
from app.core.response import ok
from app.schema import master as ms
from app.service.master import (
    LocationService,
    MaterialCategoryService,
    MaterialService,
    SupplierService,
    UnitService,
    WarehouseService,
)

router = APIRouter(tags=["主数据"])


def register(path, tag, service_cls, create_schema, update_schema, out_schema, name):
    view = require_perm(Perm.MATERIAL_VIEW)
    manage = require_perm(Perm.MATERIAL_MANAGE)

    @router.get(path, name="list_" + name, tags=[tag])
    def list_items(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        user=Depends(view),
        db: Session = Depends(get_db),
    ):
        items, total = service_cls(db).list(page, page_size)
        return ok({"total": total, "items": [out_schema.model_validate(x).model_dump() for x in items]})

    @router.post(path, name="create_" + name, status_code=201, tags=[tag])
    def create_item(payload: create_schema, user=Depends(manage), db: Session = Depends(get_db)):
        return ok(out_schema.model_validate(service_cls(db).create(payload, user.id)).model_dump())

    @router.get(path + "/{item_id}", name="get_" + name, tags=[tag])
    def get_item(item_id: int, user=Depends(view), db: Session = Depends(get_db)):
        return ok(out_schema.model_validate(service_cls(db).get(item_id)).model_dump())

    @router.put(path + "/{item_id}", name="update_" + name, tags=[tag])
    def update_item(item_id: int, payload: update_schema, user=Depends(manage), db: Session = Depends(get_db)):
        return ok(out_schema.model_validate(service_cls(db).update(item_id, payload)).model_dump())

    @router.delete(path + "/{item_id}", name="delete_" + name, tags=[tag])
    def delete_item(item_id: int, user=Depends(manage), db: Session = Depends(get_db)):
        service_cls(db).delete(item_id)
        return ok(None)


register(
    "/material-categories",
    "物资分类",
    MaterialCategoryService,
    ms.MaterialCategoryCreate,
    ms.MaterialCategoryUpdate,
    ms.MaterialCategoryOut,
    "material_category",
)
register("/units", "计量单位", UnitService, ms.UnitCreate, ms.UnitUpdate, ms.UnitOut, "unit")
register("/suppliers", "供应商", SupplierService, ms.SupplierCreate, ms.SupplierUpdate, ms.SupplierOut, "supplier")
register(
    "/warehouses", "仓库", WarehouseService, ms.WarehouseCreate, ms.WarehouseUpdate, ms.WarehouseOut, "warehouse"
)
register("/locations", "库位", LocationService, ms.LocationCreate, ms.LocationUpdate, ms.LocationOut, "location")
register("/materials", "物资", MaterialService, ms.MaterialCreate, ms.MaterialUpdate, ms.MaterialOut, "material")
