import { api } from '@/api/http'
import type { Page } from '@/api/master'
import type { components } from '@/api/schema'

export type InventoryRow = components['schemas']['InventoryOut']
export type InventoryBatch = components['schemas']['InventoryBatchOut']
export type InventoryTxn = components['schemas']['InventoryTransactionOut']
export type Reconcile = components['schemas']['ReconcileOut']

export type InboundOrder = components['schemas']['InboundOrderOut']
export type OutboundOrder = components['schemas']['OutboundOrderOut']
export type OutboundCreate = components['schemas']['OutboundCreate']
export type OutboundUpdate = components['schemas']['OutboundUpdate']
export type TransferOrder = components['schemas']['TransferOrderOut']
export type TransferCreate = components['schemas']['TransferCreate']
export type TransferUpdate = components['schemas']['TransferUpdate']
export type StocktakeOrder = components['schemas']['StocktakeOrderOut']
export type StocktakeCreate = components['schemas']['StocktakeCreate']
export type StocktakeUpdate = components['schemas']['StocktakeUpdate']
export type StocktakeCountIn = components['schemas']['StocktakeCountIn']
export type StockAlert = components['schemas']['StockAlertOut']
export type ScanResult = components['schemas']['ScanResult']

type Params = Record<string, unknown>

// ---- 库存查询 ----
export function listInventory(params: Params = {}) {
  return api.get<Page<InventoryRow>>('/inventory', { page: 1, page_size: 20, ...params })
}
export function listInventoryBatches(params: Params = {}) {
  return api.get<Page<InventoryBatch>>('/inventory/batches', { page: 1, page_size: 20, ...params })
}
export function listInventoryTransactions(params: Params = {}) {
  return api.get<Page<InventoryTxn>>('/inventory/transactions', { page: 1, page_size: 20, ...params })
}
export function reconcileInventory() {
  return api.get<Reconcile>('/inventory/reconcile')
}

// ---- 入库单 ----
export function listInboundOrders(params: Params = {}) {
  return api.get<Page<InboundOrder>>('/inbound-orders', { page: 1, page_size: 20, ...params })
}
export function postInboundOrder(id: number) {
  return api.post<InboundOrder>('/inbound-orders/' + id + '/post')
}
export function completeInboundOrder(id: number) {
  return api.post<InboundOrder>('/inbound-orders/' + id + '/complete')
}
export function reverseInboundOrder(id: number, reason?: string) {
  return api.post<InboundOrder>('/inbound-orders/' + id + '/reverse', { reason: reason || null })
}
export function cancelInboundOrder(id: number, reason?: string) {
  return api.post<InboundOrder>('/inbound-orders/' + id + '/cancel', { reason: reason || null })
}

// ---- 出库单 ----
export function listOutboundOrders(params: Params = {}) {
  return api.get<Page<OutboundOrder>>('/outbound-orders', { page: 1, page_size: 20, ...params })
}
export function createOutboundOrder(payload: OutboundCreate) {
  return api.post<OutboundOrder>('/outbound-orders', payload)
}
export function updateOutboundOrder(id: number, payload: OutboundUpdate) {
  return api.put<OutboundOrder>('/outbound-orders/' + id, payload)
}
export function deleteOutboundOrder(id: number) {
  return api.delete<null>('/outbound-orders/' + id)
}
export function postOutboundOrder(id: number) {
  return api.post<OutboundOrder>('/outbound-orders/' + id + '/post')
}
export function completeOutboundOrder(id: number) {
  return api.post<OutboundOrder>('/outbound-orders/' + id + '/complete')
}
export function cancelOutboundOrder(id: number, reason?: string) {
  return api.post<OutboundOrder>('/outbound-orders/' + id + '/cancel', { reason: reason || null })
}
export function reverseOutboundOrder(id: number, reason?: string) {
  return api.post<OutboundOrder>('/outbound-orders/' + id + '/reverse', { reason: reason || null })
}

// ---- 调拨单 ----
export function listTransferOrders(params: Params = {}) {
  return api.get<Page<TransferOrder>>('/transfer-orders', { page: 1, page_size: 20, ...params })
}
export function createTransferOrder(payload: TransferCreate) {
  return api.post<TransferOrder>('/transfer-orders', payload)
}
export function updateTransferOrder(id: number, payload: TransferUpdate) {
  return api.put<TransferOrder>('/transfer-orders/' + id, payload)
}
export function deleteTransferOrder(id: number) {
  return api.delete<null>('/transfer-orders/' + id)
}
export function postTransferOrder(id: number) {
  return api.post<TransferOrder>('/transfer-orders/' + id + '/post')
}
export function completeTransferOrder(id: number) {
  return api.post<TransferOrder>('/transfer-orders/' + id + '/complete')
}
export function cancelTransferOrder(id: number, reason?: string) {
  return api.post<TransferOrder>('/transfer-orders/' + id + '/cancel', { reason: reason || null })
}
export function reverseTransferOrder(id: number, reason?: string) {
  return api.post<TransferOrder>('/transfer-orders/' + id + '/reverse', { reason: reason || null })
}

// ---- 盘点单 ----
export function listStocktakeOrders(params: Params = {}) {
  return api.get<Page<StocktakeOrder>>('/stocktake-orders', { page: 1, page_size: 20, ...params })
}
export function createStocktakeOrder(payload: StocktakeCreate) {
  return api.post<StocktakeOrder>('/stocktake-orders', payload)
}
export function updateStocktakeOrder(id: number, payload: StocktakeUpdate) {
  return api.put<StocktakeOrder>('/stocktake-orders/' + id, payload)
}
export function deleteStocktakeOrder(id: number) {
  return api.delete<null>('/stocktake-orders/' + id)
}
export function startStocktakeOrder(id: number) {
  return api.post<StocktakeOrder>('/stocktake-orders/' + id + '/start')
}
export function countStocktakeOrder(id: number, payload: StocktakeCountIn) {
  return api.post<StocktakeOrder>('/stocktake-orders/' + id + '/counts', payload)
}
export function completeStocktakeOrder(id: number) {
  return api.post<StocktakeOrder>('/stocktake-orders/' + id + '/complete')
}
export function cancelStocktakeOrder(id: number, reason?: string) {
  return api.post<StocktakeOrder>('/stocktake-orders/' + id + '/cancel', { reason: reason || null })
}
export function reverseStocktakeOrder(id: number, reason?: string) {
  return api.post<StocktakeOrder>('/stocktake-orders/' + id + '/reverse', { reason: reason || null })
}

// ---- 预警 ----
export function listStockAlerts(params: Params = {}) {
  return api.get<Page<StockAlert>>('/stock-alerts', { page: 1, page_size: 20, ...params })
}
export function scanStockAlerts() {
  return api.post<ScanResult>('/stock-alerts/scan')
}
export function ackStockAlert(id: number) {
  return api.post<StockAlert>('/stock-alerts/' + id + '/ack')
}
export function resolveStockAlert(id: number) {
  return api.post<StockAlert>('/stock-alerts/' + id + '/resolve')
}
export function ignoreStockAlert(id: number, reason?: string) {
  return api.post<StockAlert>('/stock-alerts/' + id + '/ignore', { reason: reason || null })
}
