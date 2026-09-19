import { api } from '@/api/http'
import type { Page } from '@/api/master'
import type { components } from '@/api/schema'

export type PR = components['schemas']['PROut']
export type PRCreate = components['schemas']['PRCreate']
export type PRUpdate = components['schemas']['PRUpdate']
export type PRConvertIn = components['schemas']['PRConvertIn']

export type PO = components['schemas']['POOut']
export type POCreate = components['schemas']['POCreate']
export type POUpdate = components['schemas']['POUpdate']

export type Delivery = components['schemas']['DeliveryOut']
export type DeliveryCreate = components['schemas']['DeliveryCreate']
export type DeliveryUpdate = components['schemas']['DeliveryUpdate']

type Params = Record<string, unknown>

// ---- 请购单 ----
export function listRequisitions(params: Params = {}) {
  return api.get<Page<PR>>('/purchase-requisitions', { page: 1, page_size: 20, ...params })
}
export function createRequisition(payload: PRCreate) {
  return api.post<PR>('/purchase-requisitions', payload)
}
export function updateRequisition(id: number, payload: PRUpdate) {
  return api.put<PR>('/purchase-requisitions/' + id, payload)
}
export function deleteRequisition(id: number) {
  return api.delete<null>('/purchase-requisitions/' + id)
}
export function submitRequisition(id: number) {
  return api.post<PR>('/purchase-requisitions/' + id + '/submit')
}
export function approveRequisition(id: number) {
  return api.post<PR>('/purchase-requisitions/' + id + '/approve')
}
export function cancelRequisition(id: number, reason?: string) {
  return api.post<PR>('/purchase-requisitions/' + id + '/cancel', { reason: reason || null })
}
export function convertRequisition(id: number, payload: PRConvertIn) {
  return api.post<PO>('/purchase-requisitions/' + id + '/convert-to-po', payload)
}

// ---- 采购订单 ----
export function listOrders(params: Params = {}) {
  return api.get<Page<PO>>('/purchase-orders', { page: 1, page_size: 20, ...params })
}
export function createOrder(payload: POCreate) {
  return api.post<PO>('/purchase-orders', payload)
}
export function getOrder(id: number) {
  return api.get<PO>('/purchase-orders/' + id)
}
export function updateOrder(id: number, payload: POUpdate) {
  return api.put<PO>('/purchase-orders/' + id, payload)
}
export function deleteOrder(id: number) {
  return api.delete<null>('/purchase-orders/' + id)
}
export function confirmOrder(id: number) {
  return api.post<PO>('/purchase-orders/' + id + '/confirm')
}
export function cancelOrder(id: number, reason?: string) {
  return api.post<PO>('/purchase-orders/' + id + '/cancel', { reason: reason || null })
}

// ---- 到货/验收单 ----
export function listDeliveries(params: Params = {}) {
  return api.get<Page<Delivery>>('/supplier-deliveries', { page: 1, page_size: 20, ...params })
}
export function createDelivery(payload: DeliveryCreate) {
  return api.post<Delivery>('/supplier-deliveries', payload)
}
export function getDelivery(id: number) {
  return api.get<Delivery>('/supplier-deliveries/' + id)
}
export function updateDelivery(id: number, payload: DeliveryUpdate) {
  return api.put<Delivery>('/supplier-deliveries/' + id, payload)
}
export function deleteDelivery(id: number) {
  return api.delete<null>('/supplier-deliveries/' + id)
}
export function submitDelivery(id: number) {
  return api.post<Delivery>('/supplier-deliveries/' + id + '/submit')
}
export function acceptDelivery(id: number, payload: components['schemas']['DeliveryAcceptIn']) {
  return api.post<components['schemas']['InboundOrderOut']>('/supplier-deliveries/' + id + '/accept', payload)
}
export function cancelDelivery(id: number, reason?: string) {
  return api.post<Delivery>('/supplier-deliveries/' + id + '/cancel', { reason: reason || null })
}
