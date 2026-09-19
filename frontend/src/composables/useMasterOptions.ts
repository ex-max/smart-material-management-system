import { computed, ref } from 'vue'

import {
  listMaterialCategories,
  listMaterials,
  listSuppliers,
  listUnits,
  listWarehouses,
} from '@/api/master'

export interface NamedOption {
  id: number
  code: string
  name: string
}

export type OptionKind = 'category' | 'unit' | 'supplier' | 'warehouse' | 'material'

const categories = ref<NamedOption[]>([])
const units = ref<NamedOption[]>([])
const suppliers = ref<NamedOption[]>([])
const warehouses = ref<NamedOption[]>([])
const materials = ref<NamedOption[]>([])

const optionLists: Record<OptionKind, typeof categories> = {
  category: categories,
  unit: units,
  supplier: suppliers,
  warehouse: warehouses,
  material: materials,
}

const optionMaps = computed<Record<OptionKind, Map<number, NamedOption>>>(() => ({
  category: new Map(categories.value.map((item) => [item.id, item])),
  unit: new Map(units.value.map((item) => [item.id, item])),
  supplier: new Map(suppliers.value.map((item) => [item.id, item])),
  warehouse: new Map(warehouses.value.map((item) => [item.id, item])),
  material: new Map(materials.value.map((item) => [item.id, item])),
}))

let loaded = false
let inflight: Promise<void> | null = null

export function useMasterOptions() {
  async function ensureLoaded(): Promise<void> {
    if (loaded) {
      return
    }
    if (inflight) {
      return inflight
    }
    inflight = (async () => {
      try {
        const [cats, unitPage, supplierPage, warehousePage, materialPage] = await Promise.all([
          listMaterialCategories(),
          listUnits(),
          listSuppliers(),
          listWarehouses(),
          listMaterials(),
        ])
        categories.value = cats.items.map((i) => ({ id: i.id, code: i.code, name: i.name }))
        units.value = unitPage.items.map((i) => ({ id: i.id, code: i.code, name: i.name }))
        suppliers.value = supplierPage.items.map((i) => ({ id: i.id, code: i.code, name: i.name }))
        warehouses.value = warehousePage.items.map((i) => ({ id: i.id, code: i.code, name: i.name }))
        materials.value = materialPage.items.map((i) => ({ id: i.id, code: i.code, name: i.name }))
        loaded = true
      } catch {
        // 无主数据查看权限时静默降级（后端 403 已由全局拦截器提示）
      } finally {
        inflight = null
      }
    })()
    return inflight
  }

  function optionsOf(kind: OptionKind): NamedOption[] {
    return optionLists[kind].value
  }

  function nameOf(kind: OptionKind, id: unknown): string {
    if (id === null || id === undefined || id === '') {
      return '-'
    }
    return optionMaps.value[kind].get(Number(id))?.name || '#' + String(id)
  }

  function labelOf(kind: OptionKind, id: unknown): string {
    if (id === null || id === undefined || id === '') {
      return '-'
    }
    const item = optionMaps.value[kind].get(Number(id))
    return item ? item.code + ' ' + item.name : '#' + String(id)
  }

  return { ensureLoaded, optionsOf, nameOf, labelOf }
}
