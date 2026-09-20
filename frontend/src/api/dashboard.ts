import { api } from '@/api/http'
import type { Page } from '@/api/master'
import type { components } from '@/api/schema'

/**
 * 概览看板数据源：只读现有列表接口，页面内纯前端聚合。
 *
 * - 各 list 接口没有聚合参数，统一 page_size=200 拉取后由 useDashboard 聚合；
 * - 概览对所有登录用户可见，无权限接口（403）用 silent 静默降级为「暂无数据」，
 *   不弹全局错误、不阻塞其它卡片渲染（对齐 ReplenishmentView.loadMasters 的 catch）。
 */
export type MaterialOut = components['schemas']['MaterialOut']
export type WarehouseOut = components['schemas']['WarehouseOut']
export type InventoryOut = components['schemas']['InventoryOut']
export type InventoryTxnOut = components['schemas']['InventoryTransactionOut']
export type StockAlertOut = components['schemas']['StockAlertOut']
export type PROut = components['schemas']['PROut']
export type POOut = components['schemas']['POOut']
export type DeliveryOut = components['schemas']['DeliveryOut']
export type InboundOrderOut = components['schemas']['InboundOrderOut']
export type OutboundOrderOut = components['schemas']['OutboundOrderOut']
export type ReplenishmentSuggestionOut = components['schemas']['ReplenishmentSuggestionOut']

/** 后端列表接口 page_size 上限为 200。 */
export const DASHBOARD_PAGE_SIZE = 200

function fetchPage<T>(path: string, params: Record<string, unknown> = {}) {
  return api.get<Page<T>>(
    path,
    { page: 1, page_size: DASHBOARD_PAGE_SIZE, ...params },
    { silent: true },
  )
}

export const dashboardApi = {
  materials: () => fetchPage<MaterialOut>('/materials'),
  warehouses: () => fetchPage<WarehouseOut>('/warehouses'),
  inventory: () => fetchPage<InventoryOut>('/inventory'),
  transactions: () => fetchPage<InventoryTxnOut>('/inventory/transactions'),
  alerts: () => fetchPage<StockAlertOut>('/stock-alerts'),
  requisitions: () => fetchPage<PROut>('/purchase-requisitions'),
  orders: () => fetchPage<POOut>('/purchase-orders'),
  deliveries: () => fetchPage<DeliveryOut>('/supplier-deliveries'),
  inbound: () => fetchPage<InboundOrderOut>('/inbound-orders'),
  outbound: () => fetchPage<OutboundOrderOut>('/outbound-orders'),
  suggestions: () => fetchPage<ReplenishmentSuggestionOut>('/replenishment-suggestions'),
}
