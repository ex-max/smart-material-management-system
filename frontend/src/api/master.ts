import { api } from '@/api/http'
import type { components } from '@/api/schema'

export type Material = components['schemas']['MaterialOut']
export type Warehouse = components['schemas']['WarehouseOut']

export interface Page<T> {
  total: number
  items: T[]
}

export function listMaterials() {
  return api.get<Page<Material>>('/materials', { page: 1, page_size: 200 })
}

export function listWarehouses() {
  return api.get<Page<Warehouse>>('/warehouses', { page: 1, page_size: 200 })
}
