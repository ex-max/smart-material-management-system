from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- 物资分类 ----------------
class MaterialCategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    parent_id: int | None = None
    sort_no: int = 0
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class MaterialCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    sort_no: int | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class MaterialCategoryOut(ORMBase):
    id: int
    parent_id: int | None
    code: str
    name: str
    level: int
    path: str
    sort_no: int
    is_active: bool
    remark: str | None


# ---------------- 计量单位 ----------------
class UnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=32)
    scale: int = Field(default=0, ge=0, le=4)
    sort_no: int = 0
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class UnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    scale: int | None = Field(default=None, ge=0, le=4)
    sort_no: int | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class UnitOut(ORMBase):
    id: int
    code: str
    name: str
    scale: int
    sort_no: int
    is_active: bool
    remark: str | None


# ---------------- 供应商 ----------------
class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    short_name: str | None = Field(default=None, max_length=64)
    contact_person: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=255)
    tax_no: str | None = Field(default=None, max_length=64)
    payment_terms: str | None = Field(default=None, max_length=64)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE|BLACKLIST)$")
    remark: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    short_name: str | None = Field(default=None, max_length=64)
    contact_person: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=255)
    tax_no: str | None = Field(default=None, max_length=64)
    payment_terms: str | None = Field(default=None, max_length=64)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE|BLACKLIST)$")
    remark: str | None = None


class SupplierOut(ORMBase):
    id: int
    code: str
    name: str
    short_name: str | None
    contact_person: str | None
    contact_phone: str | None
    email: str | None
    address: str | None
    tax_no: str | None
    payment_terms: str | None
    lead_time_days: Decimal | None
    rating: Decimal | None
    status: str
    remark: str | None


# ---------------- 仓库 ----------------
class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    manager_id: int | None = None
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    manager_id: int | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class WarehouseOut(ORMBase):
    id: int
    code: str
    name: str
    address: str | None
    manager_id: int | None
    is_active: bool
    remark: str | None


# ---------------- 库位 ----------------
class LocationCreate(BaseModel):
    warehouse_id: int
    code: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=64)
    zone: str | None = Field(default=None, max_length=32)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    zone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class LocationOut(ORMBase):
    id: int
    warehouse_id: int
    code: str
    name: str | None
    zone: str | None
    is_active: bool
    remark: str | None


# ---------------- 物资档案 ----------------
class MaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=128)
    category_id: int
    unit_id: int
    brand: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    safety_stock: Decimal = Field(default=Decimal("0"), ge=0)
    max_stock: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    is_batch_managed: bool = False
    shelf_life_days: int | None = Field(default=None, gt=0)
    default_supplier_id: int | None = None
    abc_class: str | None = Field(default=None, pattern="^[ABC]$")
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE)$")
    remark: str | None = None


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=128)
    category_id: int | None = None
    unit_id: int | None = None
    brand: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    safety_stock: Decimal | None = Field(default=None, ge=0)
    max_stock: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    lead_time_days: Decimal | None = Field(default=None, gt=0)
    is_batch_managed: bool | None = None
    shelf_life_days: int | None = Field(default=None, gt=0)
    default_supplier_id: int | None = None
    abc_class: str | None = Field(default=None, pattern="^[ABC]$")
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")
    remark: str | None = None


class MaterialOut(ORMBase):
    id: int
    code: str
    name: str
    spec: str | None
    category_id: int
    unit_id: int
    brand: str | None
    barcode: str | None
    safety_stock: Decimal
    max_stock: Decimal | None
    reorder_point: Decimal | None
    lead_time_days: Decimal | None
    is_batch_managed: bool
    shelf_life_days: int | None
    default_supplier_id: int | None
    abc_class: str | None
    status: str
    remark: str | None
