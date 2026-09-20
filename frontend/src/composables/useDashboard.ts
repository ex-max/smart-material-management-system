import type { EChartsCoreOption } from 'echarts/core'
import { computed, ref } from 'vue'

import {
  dashboardApi,
  type DeliveryOut,
  type InboundOrderOut,
  type InventoryOut,
  type InventoryTxnOut,
  type MaterialOut,
  type OutboundOrderOut,
  type POOut,
  type PROut,
  type ReplenishmentSuggestionOut,
  type StockAlertOut,
  type WarehouseOut,
} from '@/api/dashboard'
import type { CsvCell } from '@/utils/csv'
import { downloadCsv } from '@/utils/csv'
import { ALERT_TYPE, DOC_STATUS } from '@/utils/status'

interface Page<T> {
  total: number
  items: T[]
}

interface DashboardSnapshot {
  materials: MaterialOut[]
  materialTotal: number
  warehouses: WarehouseOut[]
  warehouseTotal: number
  inventory: InventoryOut[]
  inventoryTotal: number
  transactions: InventoryTxnOut[]
  alerts: StockAlertOut[]
  alertTotal: number
  requisitions: PROut[]
  orders: POOut[]
  deliveries: DeliveryOut[]
  inbound: InboundOrderOut[]
  outbound: OutboundOrderOut[]
  suggestions: ReplenishmentSuggestionOut[]
  suggestionTotal: number
}

function emptySnapshot(): DashboardSnapshot {
  return {
    materials: [],
    materialTotal: 0,
    warehouses: [],
    warehouseTotal: 0,
    inventory: [],
    inventoryTotal: 0,
    transactions: [],
    alerts: [],
    alertTotal: 0,
    requisitions: [],
    orders: [],
    deliveries: [],
    inbound: [],
    outbound: [],
    suggestions: [],
    suggestionTotal: 0,
  }
}

/** 单个接口失败（如无权限 403）时返回空页，保证其它卡片照常渲染。 */
async function safe<T>(promise: Promise<Page<T>>): Promise<Page<T>> {
  try {
    return await promise
  } catch {
    return { total: 0, items: [] }
  }
}

function num(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function round2(value: number): number {
  return Math.round(value * 100) / 100
}

export function useDashboard() {
  const data = ref<DashboardSnapshot>(emptySnapshot())
  const loading = ref(false)
  const loadError = ref(false)

  async function load(): Promise<void> {
    loading.value = true
    loadError.value = false
    try {
      const [
        materials,
        warehouses,
        inventory,
        transactions,
        alerts,
        requisitions,
        orders,
        deliveries,
        inbound,
        outbound,
        suggestions,
      ] = await Promise.all([
        safe(dashboardApi.materials()),
        safe(dashboardApi.warehouses()),
        safe(dashboardApi.inventory()),
        safe(dashboardApi.transactions()),
        safe(dashboardApi.alerts()),
        safe(dashboardApi.requisitions()),
        safe(dashboardApi.orders()),
        safe(dashboardApi.deliveries()),
        safe(dashboardApi.inbound()),
        safe(dashboardApi.outbound()),
        safe(dashboardApi.suggestions()),
      ])
      data.value = {
        materials: materials.items,
        materialTotal: materials.total,
        warehouses: warehouses.items,
        warehouseTotal: warehouses.total,
        inventory: inventory.items,
        inventoryTotal: inventory.total,
        transactions: transactions.items,
        alerts: alerts.items,
        alertTotal: alerts.total,
        requisitions: requisitions.items,
        orders: orders.items,
        deliveries: deliveries.items,
        inbound: inbound.items,
        outbound: outbound.items,
        suggestions: suggestions.items,
        suggestionTotal: suggestions.total,
      }
    } catch {
      loadError.value = true
    } finally {
      loading.value = false
    }
  }

  const documents = computed(() => [
    ...data.value.requisitions,
    ...data.value.orders,
    ...data.value.deliveries,
    ...data.value.inbound,
    ...data.value.outbound,
  ])

  const inventoryQty = computed(() =>
    round2(data.value.inventory.reduce((sum, row) => sum + num(row.quantity), 0)),
  )
  const inventoryTruncated = computed(() => data.value.inventoryTotal > data.value.inventory.length)
  const pendingDocs = computed(() => documents.value.filter((doc) => doc.status === 'PENDING').length)
  const openAlerts = computed(() => data.value.alerts.filter((alert) => alert.status === 'OPEN'))
  const openSuggestions = computed(() =>
    data.value.suggestions.filter((suggestion) => suggestion.status === 'OPEN').length,
  )
  const suggestionTruncated = computed(
    () => data.value.suggestionTotal > data.value.suggestions.length,
  )

  interface StatCard {
    key: string
    label: string
    value: number
    unit: string
    hint: string
    type: '' | 'success' | 'warning' | 'danger' | 'primary'
  }

  const statCards = computed<StatCard[]>(() => [
    { key: 'materials', label: '物资数', value: data.value.materialTotal, unit: '种', hint: '物资档案', type: 'primary' },
    { key: 'warehouses', label: '仓库数', value: data.value.warehouseTotal, unit: '个', hint: '在用仓库', type: 'primary' },
    {
      key: 'inventory',
      label: '库存结存',
      value: data.value.inventoryTotal,
      unit: '行',
      hint: '总量 ' + inventoryQty.value + (inventoryTruncated.value ? '（前 200 行）' : ''),
      type: 'success',
    },
    { key: 'pending', label: '待审单据', value: pendingDocs.value, unit: '单', hint: '状态 PENDING', type: 'warning' },
    {
      key: 'alerts',
      label: '低库存/预警',
      value: openAlerts.value.length,
      unit: '条',
      hint: '待处理 OPEN' + (data.value.alertTotal > data.value.alerts.length ? '（前 200 条）' : ''),
      type: 'danger',
    },
    {
      key: 'suggestions',
      label: '待确认补货建议',
      value: openSuggestions.value,
      unit: '条',
      hint: '状态 OPEN' + (suggestionTruncated.value ? '（前 200 条）' : ''),
      type: 'warning',
    },
  ])

  // ---- 图 1：单据状态分布（跨请购/采购/到货/入库/出库聚合） ----
  const docStatusData = computed(() => {
    const counts = new Map<string, number>()
    for (const doc of documents.value) {
      counts.set(doc.status, (counts.get(doc.status) || 0) + 1)
    }
    return [...counts.entries()].map(([status, value]) => ({
      name: DOC_STATUS[status]?.label || status,
      value,
    }))
  })

  const docStatusOption = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '66%'],
        center: ['50%', '44%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
        label: { formatter: '{b}: {c}' },
        data: docStatusData.value,
      },
    ],
  }))

  // ---- 图 2：库存 Top10 物资（结存数量按物资汇总） ----
  const topMaterials = computed(() => {
    const nameById = new Map(data.value.materials.map((material) => [material.id, material.name]))
    const codeById = new Map(data.value.materials.map((material) => [material.id, material.code]))
    const sums = new Map<number, number>()
    for (const row of data.value.inventory) {
      sums.set(row.material_id, (sums.get(row.material_id) || 0) + num(row.quantity))
    }
    return [...sums.entries()]
      .map(([id, value]) => {
        const code = codeById.get(id)
        const name = nameById.get(id) || '#' + id
        return { name: code ? code + ' ' + name : name, value: round2(value) }
      })
      .sort((a, b) => a.value - b.value)
      .slice(-10)
  })

  const topInventoryOption = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 32, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: topMaterials.value.map((item) => item.name),
      axisLabel: { width: 130, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        data: topMaterials.value.map((item) => item.value),
        barMaxWidth: 18,
        itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] },
      },
    ],
  }))

  // ---- 图 3：近期出入库趋势（流水按日、按正负方向聚合） ----
  const trend = computed(() => {
    const days = new Map<string, { inQty: number; outQty: number }>()
    for (const txn of data.value.transactions) {
      const date = String(txn.occurred_at || '').slice(0, 10)
      if (!date) {
        continue
      }
      const bucket = days.get(date) || { inQty: 0, outQty: 0 }
      const qty = num(txn.quantity)
      if (qty >= 0) {
        bucket.inQty += qty
      } else {
        bucket.outQty += Math.abs(qty)
      }
      days.set(date, bucket)
    }
    const dates = [...days.keys()].sort().slice(-14)
    return {
      dates,
      inQty: dates.map((date) => round2(days.get(date)?.inQty || 0)),
      outQty: dates.map((date) => round2(days.get(date)?.outQty || 0)),
    }
  })

  const trendOption = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, data: ['入库', '出库'] },
    grid: { left: 8, right: 32, top: 16, bottom: 36, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: trend.value.dates },
    yAxis: { type: 'value' },
    series: [
      {
        name: '入库',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        areaStyle: { opacity: 0.12 },
        itemStyle: { color: '#67c23a' },
        data: trend.value.inQty,
      },
      {
        name: '出库',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        areaStyle: { opacity: 0.12 },
        itemStyle: { color: '#f56c6c' },
        data: trend.value.outQty,
      },
    ],
  }))

  // ---- 图 4：预警类型分布（优先统计 OPEN，无历史时才退回全部） ----
  const alertTypeData = computed(() => {
    const openList = data.value.alerts.filter((alert) => alert.status === 'OPEN')
    const source = openList.length ? openList : data.value.alerts
    const counts = new Map<string, number>()
    for (const alert of source) {
      counts.set(alert.alert_type, (counts.get(alert.alert_type) || 0) + 1)
    }
    return [...counts.entries()].map(([type, value]) => ({ name: ALERT_TYPE[type] || type, value }))
  })

  const alertTypeOption = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '66%'],
        center: ['50%', '44%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
        label: { formatter: '{b}: {c}' },
        data: alertTypeData.value,
      },
    ],
  }))

  function csvRows(): CsvCell[][] {
    const rows: CsvCell[][] = [['分类', '项目', '数值']]
    for (const card of statCards.value) {
      rows.push(['统计卡片', card.label, card.value])
    }
    for (const item of docStatusData.value) {
      rows.push(['单据状态分布', item.name, item.value])
    }
    for (const item of topMaterials.value) {
      rows.push(['库存Top10物资', item.name, item.value])
    }
    for (const item of alertTypeData.value) {
      rows.push(['预警类型分布', item.name, item.value])
    }
    trend.value.dates.forEach((date, index) => {
      rows.push(['出入库趋势', date + ' 入库', trend.value.inQty[index]])
      rows.push(['出入库趋势', date + ' 出库', trend.value.outQty[index]])
    })
    return rows
  }

  function exportCsv(): void {
    const stamp = new Date().toISOString().slice(0, 10)
    downloadCsv('erp-dashboard-' + stamp + '.csv', csvRows())
  }

  return {
    data,
    loading,
    loadError,
    load,
    statCards,
    docStatusData,
    docStatusOption,
    topMaterials,
    topInventoryOption,
    trend,
    trendOption,
    alertTypeData,
    alertTypeOption,
    exportCsv,
  }
}
