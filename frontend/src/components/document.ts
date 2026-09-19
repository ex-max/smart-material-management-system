import type { TagType } from '@/utils/status'

export interface DocColumn {
  prop: string
  label: string
  width?: number
  minWidth?: number
  formatter?: (row: any) => string
  tag?: (row: any) => { label: string; type: TagType }
}

export interface DocAction {
  key: string
  label: string
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  permission?: string
  visible?: (row: any) => boolean
  confirm?: (row: any) => string
  /** true 时由 run 自行提示/刷新（用于打开弹窗类动作） */
  silent?: boolean
  run: (row: any) => Promise<unknown>
}

export interface DocFilter {
  prop: string
  label: string
  options: () => { label: string; value: any }[]
}

export interface DocConfig {
  title: string
  description?: string
  fetch: (params: Record<string, unknown>) => Promise<{ total: number; items: any[] }>
  columns: DocColumn[]
  statusMeta: Record<string, { label: string; type: TagType }>
  detailFields?: (row: any) => { label: string; value: string }[]
  detailItems?: (row: any) => { columns: DocColumn[]; rows: any[] }
  actions?: DocAction[]
  extraFilters?: DocFilter[]
  canCreate?: boolean
  createPermission?: string
  createLabel?: string
}
