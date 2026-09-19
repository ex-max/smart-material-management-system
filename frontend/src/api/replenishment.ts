import { api } from '@/api/http'
import type { components } from '@/api/schema'

export type ReplenishmentPolicy = components['schemas']['ReplenishmentPolicyOut']
export type ReplenishmentPolicyCreate = components['schemas']['ReplenishmentPolicyCreate']
export type ReplenishmentPolicyUpdate = components['schemas']['ReplenishmentPolicyUpdate']
export type ReplenishmentSuggestion = components['schemas']['ReplenishmentSuggestionOut']
export type GenerateResult = components['schemas']['GenerateResult']
export type ConvertResult = components['schemas']['ConvertResult']
export type ConvertResponse = components['schemas']['ConvertResponse']
export type ConfirmInput = components['schemas']['SuggestionConfirmIn']
export type RejectInput = components['schemas']['SuggestionRejectIn']

export interface Page<T> {
  total: number
  items: T[]
}

export function listPolicies(params: Record<string, unknown> = {}) {
  return api.get<Page<ReplenishmentPolicy>>('/replenishment-policies', params)
}

export function createPolicy(payload: ReplenishmentPolicyCreate) {
  return api.post<ReplenishmentPolicy>('/replenishment-policies', payload)
}

export function updatePolicy(policyId: number, payload: ReplenishmentPolicyUpdate) {
  return api.put<ReplenishmentPolicy>(`/replenishment-policies/${policyId}`, payload)
}

export function deletePolicy(policyId: number) {
  return api.delete<null>(`/replenishment-policies/${policyId}`)
}

export function generateSuggestions(scope: { material_id?: number; warehouse_id?: number } = {}) {
  const query = new URLSearchParams()
  if (scope.material_id) {
    query.set('material_id', String(scope.material_id))
  }
  if (scope.warehouse_id) {
    query.set('warehouse_id', String(scope.warehouse_id))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return api.post<GenerateResult>(`/replenishment-suggestions/generate${suffix}`)
}

export function listSuggestions(params: Record<string, unknown> = {}) {
  return api.get<Page<ReplenishmentSuggestion>>('/replenishment-suggestions', params)
}

export function getSuggestion(suggestionId: number) {
  return api.get<ReplenishmentSuggestion>(`/replenishment-suggestions/${suggestionId}`)
}

export function confirmSuggestion(suggestionId: number, payload: ConfirmInput) {
  return api.post<ReplenishmentSuggestion>(`/replenishment-suggestions/${suggestionId}/confirm`, payload)
}

export function rejectSuggestion(suggestionId: number, payload: RejectInput) {
  return api.post<ReplenishmentSuggestion>(`/replenishment-suggestions/${suggestionId}/reject`, payload)
}

export function convertSuggestion(suggestionId: number) {
  return api.post<ConvertResponse>(`/replenishment-suggestions/${suggestionId}/convert`)
}

export function convertSuggestions(suggestionIds: number[]) {
  return api.post<ConvertResult[]>('/replenishment-suggestions/convert-batch', {
    suggestion_ids: suggestionIds,
  })
}
