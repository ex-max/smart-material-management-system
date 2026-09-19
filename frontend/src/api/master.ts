import { api } from '@/api/http'
import type { components } from '@/api/schema'

export interface Page<T> {
  total: number
  items: T[]
}

// ---- 接口类型：全部由后端 OpenAPI 生成（npm run gen:api），不手写重复类型 ----
export type Material = components['schemas']['MaterialOut']
export type MaterialCreate = components['schemas']['MaterialCreate']
export type MaterialUpdate = components['schemas']['MaterialUpdate']

export type MaterialCategory = components['schemas']['MaterialCategoryOut']
export type MaterialCategoryCreate = components['schemas']['MaterialCategoryCreate']
export type MaterialCategoryUpdate = components['schemas']['MaterialCategoryUpdate']

export type Unit = components['schemas']['UnitOut']
export type UnitCreate = components['schemas']['UnitCreate']
export type UnitUpdate = components['schemas']['UnitUpdate']

export type Supplier = components['schemas']['SupplierOut']
export type SupplierCreate = components['schemas']['SupplierCreate']
export type SupplierUpdate = components['schemas']['SupplierUpdate']

export type Warehouse = components['schemas']['WarehouseOut']
export type WarehouseCreate = components['schemas']['WarehouseCreate']
export type WarehouseUpdate = components['schemas']['WarehouseUpdate']

export type Location = components['schemas']['LocationOut']
export type LocationCreate = components['schemas']['LocationCreate']
export type LocationUpdate = components['schemas']['LocationUpdate']

export interface CrudApi<T, C, U> {
  list: (params?: Record<string, unknown>) => Promise<Page<T>>
  create: (payload: C) => Promise<T>
  update: (id: number, payload: U) => Promise<T>
  remove: (id: number) => Promise<null>
}

function crud<T, C, U>(resource: string): CrudApi<T, C, U> {
  return {
    list: (params = {}) => api.get<Page<T>>('/' + resource, { page: 1, page_size: 200, ...params }),
    create: (payload) => api.post<T>('/' + resource, payload),
    update: (id, payload) => api.put<T>('/' + resource + '/' + id, payload),
    remove: (id) => api.delete<null>('/' + resource + '/' + id),
  }
}

export const materialCategoriesApi = crud<MaterialCategory, MaterialCategoryCreate, MaterialCategoryUpdate>(
  'material-categories',
)
export const unitsApi = crud<Unit, UnitCreate, UnitUpdate>('units')
export const suppliersApi = crud<Supplier, SupplierCreate, SupplierUpdate>('suppliers')
export const warehousesApi = crud<Warehouse, WarehouseCreate, WarehouseUpdate>('warehouses')
export const locationsApi = crud<Location, LocationCreate, LocationUpdate>('locations')
export const materialsApi = crud<Material, MaterialCreate, MaterialUpdate>('materials')

// 便捷列表：补货决策页等复用（只取前 200 条做下拉）
export function listMaterials(params: Record<string, unknown> = {}) {
  return materialsApi.list({ page: 1, page_size: 200, ...params })
}

export function listWarehouses() {
  return warehousesApi.list({ page: 1, page_size: 200 })
}

export function listMaterialCategories() {
  return materialCategoriesApi.list({ page: 1, page_size: 200 })
}

export function listUnits() {
  return unitsApi.list({ page: 1, page_size: 200 })
}

export function listSuppliers() {
  return suppliersApi.list({ page: 1, page_size: 200 })
}
