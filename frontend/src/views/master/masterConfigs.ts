import {
  locationsApi,
  materialCategoriesApi,
  materialsApi,
  suppliersApi,
  unitsApi,
  warehousesApi,
} from '@/api/master'

/** 行数据：id 必有，其余字段按各资源动态访问（动态表格/表单边界，故意放开类型）。 */
export type Row = { id: number } & Record<string, any>

export type TagType = '' | 'success' | 'info' | 'warning' | 'danger'
export type OptionKind = 'category' | 'unit' | 'supplier' | 'warehouse'

export interface OptionItem {
  id: number
  code: string
  name: string
}

export interface SelectOption {
  label: string
  value: string | number
}

export type FieldType = 'input' | 'textarea' | 'number' | 'select' | 'switch'

export interface FieldConfig {
  prop: string
  label: string
  type: FieldType
  required?: boolean
  /** 编辑时禁用/不提交（如：更新 DTO 不接受编码、库位不可换仓） */
  disabledOnEdit?: boolean
  /** 是否可提交 null（默认 true；false 表示空值直接省略，交给后端默认值） */
  nullable?: boolean
  placeholder?: string
  optionKind?: OptionKind
  options?: SelectOption[]
  min?: number
  max?: number
  precision?: number
  step?: number
  span?: number
  help?: string
}

export interface FilterConfig {
  prop: string
  label: string
  optionKind?: OptionKind
  options?: SelectOption[]
  width?: number
}

export interface RowContext {
  optionName: (kind: OptionKind, id: unknown) => string
  fmtNum: (value: unknown, digits?: number) => string
  fmtText: (value: unknown) => string
}

export interface ColumnConfig {
  prop: string
  label: string
  width?: number
  minWidth?: number
  formatter?: (row: Row, ctx: RowContext) => string
  tag?: (row: Row, ctx: RowContext) => { label: string; type: TagType }
}

export interface MasterApi {
  list: (params?: Record<string, unknown>) => Promise<{ total: number; items: Row[] }>
  create: (payload: Record<string, unknown>) => Promise<unknown>
  update: (id: number, payload: Record<string, unknown>) => Promise<unknown>
  remove: (id: number) => Promise<unknown>
}

export interface MasterConfig {
  key: string
  title: string
  description: string
  api: MasterApi
  searchProps: string[]
  filters: FilterConfig[]
  columns: ColumnConfig[]
  fields: FieldConfig[]
  defaults: () => Record<string, unknown>
  toForm: (row: Row) => Record<string, unknown>
  toPayload: (form: Record<string, unknown>, editing: boolean) => Record<string, unknown>
}

// ---------------- 通用工具 ----------------
export function numOrUndef(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') {
    return undefined
  }
  const num = Number(value)
  return Number.isNaN(num) ? undefined : num
}

export function buildPayload(
  fields: FieldConfig[],
  form: Record<string, unknown>,
  editing: boolean,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const field of fields) {
    if (editing && field.disabledOnEdit) {
      continue
    }
    const value = form[field.prop]
    if (field.type === 'switch') {
      payload[field.prop] = Boolean(value)
      continue
    }
    if (value === undefined || value === null || value === '') {
      if (field.required || field.nullable === false) {
        continue
      }
      payload[field.prop] = null
      continue
    }
    payload[field.prop] = value
  }
  return payload
}

const activeTag = (row: Row): { label: string; type: TagType } => ({
  label: row.is_active ? '启用' : '停用',
  type: row.is_active ? 'success' : 'info',
})

const batchTag = (row: Row): { label: string; type: TagType } => ({
  label: row.is_batch_managed ? '批次管理' : '非批次',
  type: row.is_batch_managed ? 'warning' : 'info',
})

const supplierStatusOptions: SelectOption[] = [
  { label: '合作中', value: 'ACTIVE' },
  { label: '停用', value: 'INACTIVE' },
  { label: '黑名单', value: 'BLACKLIST' },
]

const supplierStatusTag = (row: Row): { label: string; type: TagType } => {
  const labels: Record<string, string> = { ACTIVE: '合作中', INACTIVE: '停用', BLACKLIST: '黑名单' }
  const types: Record<string, TagType> = { ACTIVE: 'success', INACTIVE: 'info', BLACKLIST: 'danger' }
  const status = String(row.status || '')
  return { label: labels[status] || status || '-', type: types[status] || '' }
}

const activeStatusOptions: SelectOption[] = [
  { label: '启用', value: 'ACTIVE' },
  { label: '停用', value: 'INACTIVE' },
]

// ---------------- 物资分类 ----------------
const categoryFields: FieldConfig[] = [
  { prop: 'code', label: '编码', type: 'input', required: true, disabledOnEdit: true, placeholder: '如 CAT-001' },
  { prop: 'name', label: '名称', type: 'input', required: true },
  { prop: 'parent_id', label: '上级分类', type: 'select', optionKind: 'category', disabledOnEdit: true, placeholder: '留空为顶级分类', help: '多级树；创建后不可修改上级' },
  { prop: 'sort_no', label: '排序', type: 'number', min: 0, nullable: false },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]

// ---------------- 计量单位 ----------------
const unitFields: FieldConfig[] = [
  { prop: 'code', label: '编码', type: 'input', required: true, disabledOnEdit: true, placeholder: '如 PCS' },
  { prop: 'name', label: '名称', type: 'input', required: true, placeholder: '如 个' },
  { prop: 'scale', label: '小数位', type: 'number', min: 0, max: 4, nullable: false, help: '0–4 位' },
  { prop: 'sort_no', label: '排序', type: 'number', min: 0, nullable: false },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]

// ---------------- 供应商 ----------------
const supplierFields: FieldConfig[] = [
  { prop: 'code', label: '编码', type: 'input', required: true, disabledOnEdit: true, placeholder: '如 SUP-001' },
  { prop: 'name', label: '名称', type: 'input', required: true },
  { prop: 'short_name', label: '简称', type: 'input' },
  { prop: 'contact_person', label: '联系人', type: 'input' },
  { prop: 'contact_phone', label: '联系电话', type: 'input' },
  { prop: 'email', label: '邮箱', type: 'input' },
  { prop: 'lead_time_days', label: '提前期(天)', type: 'number', min: 0.1, precision: 1 },
  { prop: 'rating', label: '评级', type: 'number', min: 0, max: 5, precision: 1, help: '0–5' },
  { prop: 'status', label: '状态', type: 'select', required: true, options: supplierStatusOptions },
  { prop: 'payment_terms', label: '账期', type: 'input', placeholder: '如 月结30天' },
  { prop: 'tax_no', label: '税号', type: 'input' },
  { prop: 'address', label: '地址', type: 'input', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]

// ---------------- 仓库 ----------------
const warehouseFields: FieldConfig[] = [
  { prop: 'code', label: '编码', type: 'input', required: true, disabledOnEdit: true, placeholder: '如 WH01' },
  { prop: 'name', label: '名称', type: 'input', required: true },
  { prop: 'address', label: '地址', type: 'input' },
  { prop: 'manager_id', label: '负责人ID', type: 'number', min: 1, help: '用户 ID，可留空' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]

// ---------------- 库位 ----------------
const locationFields: FieldConfig[] = [
  { prop: 'warehouse_id', label: '仓库', type: 'select', required: true, optionKind: 'warehouse', disabledOnEdit: true },
  { prop: 'code', label: '编码', type: 'input', required: true, disabledOnEdit: true, placeholder: '如 A-01-01' },
  { prop: 'name', label: '名称', type: 'input' },
  { prop: 'zone', label: '库区', type: 'input', placeholder: '如 A 区' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]

// ---------------- 物资档案 ----------------
const materialFields: FieldConfig[] = [
  { prop: 'code', label: '编码', type: 'input', required: true, disabledOnEdit: true, placeholder: '如 MAT-0001' },
  { prop: 'name', label: '名称', type: 'input', required: true },
  { prop: 'spec', label: '规格', type: 'input' },
  { prop: 'category_id', label: '分类', type: 'select', required: true, optionKind: 'category' },
  { prop: 'unit_id', label: '单位', type: 'select', required: true, optionKind: 'unit' },
  { prop: 'brand', label: '品牌', type: 'input' },
  { prop: 'barcode', label: '条码', type: 'input' },
  { prop: 'safety_stock', label: '安全库存', type: 'number', min: 0, nullable: false, help: '留空按 0 处理' },
  { prop: 'max_stock', label: '最大库存', type: 'number', min: 0 },
  { prop: 'reorder_point', label: '再订货点', type: 'number', min: 0 },
  { prop: 'lead_time_days', label: '提前期(天)', type: 'number', min: 0.1, precision: 1 },
  { prop: 'shelf_life_days', label: '保质期(天)', type: 'number', min: 1, help: '批次物资必填' },
  { prop: 'default_supplier_id', label: '默认供应商', type: 'select', optionKind: 'supplier' },
  { prop: 'abc_class', label: 'ABC 分类', type: 'select', options: [{ label: 'A 类', value: 'A' }, { label: 'B 类', value: 'B' }, { label: 'C 类', value: 'C' }] },
  { prop: 'status', label: '状态', type: 'select', required: true, options: activeStatusOptions },
  { prop: 'is_batch_managed', label: '批次管理', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]

export const masterConfigs: Record<string, MasterConfig> = {
  categories: {
    key: 'categories',
    title: '物资分类',
    description: '多级分类树，编码唯一',
    api: materialCategoriesApi as unknown as MasterApi,
    searchProps: ['code', 'name', 'path'],
    filters: [],
    columns: [
      { prop: 'code', label: '编码', width: 150 },
      { prop: 'name', label: '名称', minWidth: 160 },
      { prop: 'level', label: '层级', width: 80 },
      { prop: 'path', label: '路径', minWidth: 200 },
      { prop: 'sort_no', label: '排序', width: 80 },
      { prop: 'is_active', label: '状态', width: 90, tag: activeTag },
      { prop: 'remark', label: '备注', minWidth: 120 },
    ],
    fields: categoryFields,
    defaults: () => ({ code: '', name: '', parent_id: undefined, sort_no: 0, is_active: true, remark: '' }),
    toForm: (row) => ({
      code: row.code,
      name: row.name,
      parent_id: numOrUndef(row.parent_id),
      sort_no: numOrUndef(row.sort_no) ?? 0,
      is_active: Boolean(row.is_active),
      remark: row.remark ?? '',
    }),
    toPayload: (form, editing) => buildPayload(categoryFields, form, editing),
  },
  units: {
    key: 'units',
    title: '计量单位',
    description: '基本计量单位与小数位',
    api: unitsApi as unknown as MasterApi,
    searchProps: ['code', 'name'],
    filters: [],
    columns: [
      { prop: 'code', label: '编码', width: 140 },
      { prop: 'name', label: '名称', minWidth: 140 },
      { prop: 'scale', label: '小数位', width: 90 },
      { prop: 'sort_no', label: '排序', width: 80 },
      { prop: 'is_active', label: '状态', width: 90, tag: activeTag },
      { prop: 'remark', label: '备注', minWidth: 140 },
    ],
    fields: unitFields,
    defaults: () => ({ code: '', name: '', scale: 0, sort_no: 0, is_active: true, remark: '' }),
    toForm: (row) => ({
      code: row.code,
      name: row.name,
      scale: numOrUndef(row.scale) ?? 0,
      sort_no: numOrUndef(row.sort_no) ?? 0,
      is_active: Boolean(row.is_active),
      remark: row.remark ?? '',
    }),
    toPayload: (form, editing) => buildPayload(unitFields, form, editing),
  },
  suppliers: {
    key: 'suppliers',
    title: '供应商',
    description: '供货商档案与评级',
    api: suppliersApi as unknown as MasterApi,
    searchProps: ['code', 'name', 'short_name', 'contact_person'],
    filters: [{ prop: 'status', label: '状态', options: supplierStatusOptions, width: 160 }],
    columns: [
      { prop: 'code', label: '编码', width: 140 },
      { prop: 'name', label: '名称', minWidth: 180 },
      { prop: 'short_name', label: '简称', width: 120 },
      { prop: 'contact_person', label: '联系人', width: 110 },
      { prop: 'contact_phone', label: '电话', width: 140 },
      { prop: 'lead_time_days', label: '提前期', width: 90, formatter: (row, ctx) => ctx.fmtNum(row.lead_time_days, 1) },
      { prop: 'rating', label: '评级', width: 80, formatter: (row, ctx) => ctx.fmtNum(row.rating, 1) },
      { prop: 'status', label: '状态', width: 100, tag: supplierStatusTag },
      { prop: 'remark', label: '备注', minWidth: 120 },
    ],
    fields: supplierFields,
    defaults: () => ({
      code: '',
      name: '',
      short_name: '',
      contact_person: '',
      contact_phone: '',
      email: '',
      lead_time_days: undefined,
      rating: undefined,
      status: 'ACTIVE',
      payment_terms: '',
      tax_no: '',
      address: '',
      remark: '',
    }),
    toForm: (row) => ({
      code: row.code,
      name: row.name,
      short_name: row.short_name ?? '',
      contact_person: row.contact_person ?? '',
      contact_phone: row.contact_phone ?? '',
      email: row.email ?? '',
      lead_time_days: numOrUndef(row.lead_time_days),
      rating: numOrUndef(row.rating),
      status: row.status ?? 'ACTIVE',
      payment_terms: row.payment_terms ?? '',
      tax_no: row.tax_no ?? '',
      address: row.address ?? '',
      remark: row.remark ?? '',
    }),
    toPayload: (form, editing) => buildPayload(supplierFields, form, editing),
  },
  warehouses: {
    key: 'warehouses',
    title: '仓库',
    description: '仓库档案',
    api: warehousesApi as unknown as MasterApi,
    searchProps: ['code', 'name', 'address'],
    filters: [],
    columns: [
      { prop: 'code', label: '编码', width: 140 },
      { prop: 'name', label: '名称', minWidth: 160 },
      { prop: 'address', label: '地址', minWidth: 200 },
      { prop: 'manager_id', label: '负责人ID', width: 110 },
      { prop: 'is_active', label: '状态', width: 90, tag: activeTag },
      { prop: 'remark', label: '备注', minWidth: 140 },
    ],
    fields: warehouseFields,
    defaults: () => ({ code: '', name: '', address: '', manager_id: undefined, is_active: true, remark: '' }),
    toForm: (row) => ({
      code: row.code,
      name: row.name,
      address: row.address ?? '',
      manager_id: numOrUndef(row.manager_id),
      is_active: Boolean(row.is_active),
      remark: row.remark ?? '',
    }),
    toPayload: (form, editing) => buildPayload(warehouseFields, form, editing),
  },
  locations: {
    key: 'locations',
    title: '库位',
    description: '仓库下的库位/库区',
    api: locationsApi as unknown as MasterApi,
    searchProps: ['code', 'name', 'zone'],
    filters: [{ prop: 'warehouse_id', label: '仓库', optionKind: 'warehouse', width: 180 }],
    columns: [
      { prop: 'warehouse_id', label: '仓库', width: 150, formatter: (row, ctx) => ctx.optionName('warehouse', row.warehouse_id) },
      { prop: 'code', label: '编码', width: 150 },
      { prop: 'name', label: '名称', minWidth: 140 },
      { prop: 'zone', label: '库区', width: 120 },
      { prop: 'is_active', label: '状态', width: 90, tag: activeTag },
      { prop: 'remark', label: '备注', minWidth: 140 },
    ],
    fields: locationFields,
    defaults: () => ({ warehouse_id: undefined, code: '', name: '', zone: '', is_active: true, remark: '' }),
    toForm: (row) => ({
      warehouse_id: numOrUndef(row.warehouse_id),
      code: row.code,
      name: row.name ?? '',
      zone: row.zone ?? '',
      is_active: Boolean(row.is_active),
      remark: row.remark ?? '',
    }),
    toPayload: (form, editing) => buildPayload(locationFields, form, editing),
  },
  materials: {
    key: 'materials',
    title: '物资档案',
    description: '物资主数据与库存参数',
    api: materialsApi as unknown as MasterApi,
    searchProps: ['code', 'name', 'spec', 'brand', 'barcode'],
    filters: [{ prop: 'category_id', label: '分类', optionKind: 'category', width: 200 }],
    columns: [
      { prop: 'code', label: '编码', width: 140 },
      { prop: 'name', label: '名称', minWidth: 160 },
      { prop: 'spec', label: '规格', width: 140 },
      { prop: 'category_id', label: '分类', width: 140, formatter: (row, ctx) => ctx.optionName('category', row.category_id) },
      { prop: 'unit_id', label: '单位', width: 100, formatter: (row, ctx) => ctx.optionName('unit', row.unit_id) },
      { prop: 'safety_stock', label: '安全库存', width: 110 },
      { prop: 'reorder_point', label: 'ROP', width: 90 },
      { prop: 'lead_time_days', label: '提前期', width: 90, formatter: (row, ctx) => ctx.fmtNum(row.lead_time_days, 1) },
      { prop: 'abc_class', label: 'ABC', width: 80, formatter: (row, ctx) => ctx.fmtText(row.abc_class) },
      { prop: 'is_batch_managed', label: '批次', width: 110, tag: batchTag },
      { prop: 'default_supplier_id', label: '默认供应商', width: 150, formatter: (row, ctx) => ctx.optionName('supplier', row.default_supplier_id) },
      { prop: 'status', label: '状态', width: 90, tag: activeTag },
      { prop: 'remark', label: '备注', minWidth: 120 },
    ],
    fields: materialFields,
    defaults: () => ({
      code: '',
      name: '',
      spec: '',
      category_id: undefined,
      unit_id: undefined,
      brand: '',
      barcode: '',
      safety_stock: 0,
      max_stock: undefined,
      reorder_point: undefined,
      lead_time_days: undefined,
      shelf_life_days: undefined,
      default_supplier_id: undefined,
      abc_class: undefined,
      status: 'ACTIVE',
      is_batch_managed: false,
      remark: '',
    }),
    toForm: (row) => ({
      code: row.code,
      name: row.name,
      spec: row.spec ?? '',
      category_id: numOrUndef(row.category_id),
      unit_id: numOrUndef(row.unit_id),
      brand: row.brand ?? '',
      barcode: row.barcode ?? '',
      safety_stock: numOrUndef(row.safety_stock) ?? 0,
      max_stock: numOrUndef(row.max_stock),
      reorder_point: numOrUndef(row.reorder_point),
      lead_time_days: numOrUndef(row.lead_time_days),
      shelf_life_days: numOrUndef(row.shelf_life_days),
      default_supplier_id: numOrUndef(row.default_supplier_id),
      abc_class: row.abc_class ?? undefined,
      status: row.status ?? 'ACTIVE',
      is_batch_managed: Boolean(row.is_batch_managed),
      remark: row.remark ?? '',
    }),
    toPayload: (form, editing) => buildPayload(materialFields, form, editing),
  },
}
