import { api } from '@/api/http'
import type { components } from '@/api/schema'

export type ForecastCurve = components['schemas']['ForecastCurveOut']
export type CurveHistoryPoint = components['schemas']['CurveHistoryPoint']
export type CurveForecastPoint = components['schemas']['CurveForecastPoint']

export interface ForecastCurveParams {
  material_id: number
  warehouse_id?: number | null
  history_days?: number
}

/** 预测曲线：最新 SUCCESS/PARTIAL 批次未来预测（含 95% 区间）+ 近 N 天实际消耗。 */
export function getForecastCurve(params: ForecastCurveParams) {
  return api.get<ForecastCurve>('/forecast/curves', { ...params })
}
