export type TagType = '' | 'success' | 'info' | 'warning' | 'danger'

export interface StatusMeta {
  label: string
  type: TagType
}

/** 全局单据状态（与后端 core/state_machine.py 一致）。 */
export const DOC_STATUS: Record<string, StatusMeta> = {
  DRAFT: { label: '草稿', type: 'info' },
  PENDING: { label: '待审', type: 'warning' },
  APPROVED: { label: '已审', type: '' },
  IN_PROGRESS: { label: '执行中', type: 'warning' },
  COMPLETED: { label: '已完成', type: 'success' },
  CANCELLED: { label: '已作废', type: 'danger' },
}

export const ALERT_STATUS: Record<string, StatusMeta> = {
  OPEN: { label: '待处理', type: 'danger' },
  ACKED: { label: '已确认', type: 'warning' },
  RESOLVED: { label: '已解决', type: 'success' },
  IGNORED: { label: '已忽略', type: 'info' },
  CLOSED: { label: '已关闭', type: 'info' },
}

export const ALERT_TYPE: Record<string, string> = {
  ZERO_STOCK: '零库存',
  LOW_STOCK: '低库存',
  OVERSTOCK: '超储',
  NEAR_EXPIRY: '临期',
  EXPIRED: '过期',
}

export const TXN_TYPE: Record<string, string> = {
  INBOUND: '入库',
  OUTBOUND: '出库',
  TRANSFER_IN: '调拨入',
  TRANSFER_OUT: '调拨出',
  STOCKTAKE_GAIN: '盘盈',
  STOCKTAKE_LOSS: '盘亏',
  REVERSAL: '红冲',
}

export function statusTag(value: unknown, meta: Record<string, StatusMeta> = DOC_STATUS): StatusMeta {
  const key = String(value || '')
  return meta[key] || { label: key || '-', type: 'info' }
}
