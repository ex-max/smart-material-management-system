<script setup lang="ts">
import { Download, Refresh } from '@element-plus/icons-vue'
import type { EChartsCoreOption } from 'echarts/core'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import EChart from '@/components/EChart.vue'
import { getForecastCurve, type ForecastCurve } from '@/api/forecast'
import { useMasterOptions } from '@/composables/useMasterOptions'

const { ensureLoaded, optionsOf, labelOf } = useMasterOptions()

const materialId = ref<number | null>(null)
const warehouseId = ref<number | null>(null)
const historyDays = ref(90)
const loading = ref(false)
const curve = ref<ForecastCurve | null>(null)
const chartRef = ref<InstanceType<typeof EChart> | null>(null)
const errorMessage = ref('')

const materials = computed(() => optionsOf('material'))
const warehouses = computed(() => optionsOf('warehouse'))

function num(value: unknown): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

async function load(): Promise<void> {
  if (!materialId.value) {
    ElMessage.warning('请选择物资')
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    curve.value = await getForecastCurve({
      material_id: materialId.value,
      warehouse_id: warehouseId.value,
      history_days: historyDays.value,
    })
    if (!curve.value.forecast.length) {
      errorMessage.value = '该物资×仓库暂无 SUCCESS 预测批次（可先运行 make sync-forecast）'
    }
  } catch {
    errorMessage.value = '预测曲线加载失败'
  } finally {
    loading.value = false
  }
}

const option = computed<EChartsCoreOption>(() => {
  const data = curve.value
  if (!data) {
    return {}
  }
  const historyDates = data.history.map((p) => p.date)
  const forecastDates = data.forecast.map((p) => p.date)
  const dates = [...historyDates, ...forecastDates]
  const withHistoryPad = (values: number[]): Array<number | null> => {
    const out: Array<number | null> = new Array(historyDates.length).fill(null)
    values.forEach((value) => out.push(value))
    return out
  }
  const actual: Array<number | null> = [
    ...data.history.map((p) => num(p.actual_qty)),
    ...forecastDates.map(() => null),
  ]
  const yHat: Array<number | null> = [
    ...forecastDates.map(() => null),
    ...data.forecast.map((p) => num(p.y_hat)),
  ]
  const lower = data.forecast.map((p) => (p.y_lower === null ? num(p.y_hat) : num(p.y_lower)))
  const upper = data.forecast.map((p) => (p.y_upper === null ? num(p.y_hat) : num(p.y_upper)))
  const band = upper.map((value, index) => value - lower[index])

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['实际消耗', '预测值', '95% 置信区间'] },
    grid: { left: 56, right: 24, top: 48, bottom: 36 },
    xAxis: { type: 'category', boundaryGap: false, data: dates },
    yAxis: { type: 'value', min: 0, name: '日需求量' },
    series: [
      {
        name: '95% 置信区间',
        type: 'line',
        data: withHistoryPad(lower),
        stack: 'ci',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
      },
      {
        name: '95% 置信区间',
        type: 'line',
        data: withHistoryPad(band),
        stack: 'ci',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(64, 158, 255, 0.18)' },
        tooltip: { show: false },
      },
      {
        name: '实际消耗',
        type: 'line',
        data: actual,
        symbol: 'none',
        lineStyle: { width: 2 },
      },
      {
        name: '预测值',
        type: 'line',
        data: yHat,
        symbol: 'none',
        lineStyle: { width: 2, type: 'dashed' },
      },
    ],
  }
})

const forecastRows = computed(
  () =>
    curve.value?.forecast.map((p) => ({
      date: p.date,
      horizon_step: p.horizon_step,
      y_hat: num(p.y_hat).toFixed(2),
      y_lower: p.y_lower === null ? '-' : num(p.y_lower).toFixed(2),
      y_upper: p.y_upper === null ? '-' : num(p.y_upper).toFixed(2),
    })) ?? [],
)

function exportImage(): void {
  const url = chartRef.value?.getDataURL()
  if (!url) {
    ElMessage.warning('图表尚未渲染')
    return
  }
  const material = materialId.value ? labelOf('material', materialId.value).replace(/\s+/g, '_') : 'material'
  const warehouse = warehouseId.value ? labelOf('warehouse', warehouseId.value).replace(/\s+/g, '_') : 'all'
  const link = document.createElement('a')
  link.href = url
  link.download = `forecast_${material}_${warehouse}.png`
  link.click()
}

onMounted(async () => {
  await ensureLoaded()
  if (materials.value.length) {
    materialId.value = materials.value[0].id
  }
  if (warehouses.value.length) {
    warehouseId.value = warehouses.value[0].id
  }
  await load()
})
</script>

<template>
  <div v-loading="loading" class="forecast">
    <div class="toolbar">
      <div class="filters">
        <el-select v-model="materialId" filterable placeholder="选择物资" class="select" data-test="material">
          <el-option
            v-for="item in materials"
            :key="item.id"
            :label="item.code + ' ' + item.name"
            :value="item.id"
          />
        </el-select>
        <el-select v-model="warehouseId" filterable clearable placeholder="选择仓库" class="select">
          <el-option
            v-for="item in warehouses"
            :key="item.id"
            :label="item.code + ' ' + item.name"
            :value="item.id"
          />
        </el-select>
        <el-select v-model="historyDays" class="select-narrow">
          <el-option :value="30" label="近 30 天" />
          <el-option :value="60" label="近 60 天" />
          <el-option :value="90" label="近 90 天" />
          <el-option :value="180" label="近 180 天" />
        </el-select>
        <el-button type="primary" :icon="Refresh" @click="load">查询</el-button>
      </div>
      <el-button :icon="Download" @click="exportImage">导出图片</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon class="alert" />

    <div v-if="curve && curve.run_no" class="meta">
      批次 {{ curve.run_no }}（{{ curve.run_status }}） · 模型 {{ curve.model_code || '-' }} · 分层
      {{ curve.demand_class || '-' }} · 区间 {{ (curve.interval_level * 100).toFixed(0) }}%（z={{
        curve.interval_z.toFixed(3)
      }}）
    </div>

    <el-card v-if="curve && curve.forecast.length" shadow="never" class="chart-card">
      <template #header>
        实际消耗（近 {{ curve.history_days }} 天）与未来 {{ curve.forecast.length }} 天预测
      </template>
      <EChart ref="chartRef" :option="option" height="420px" />
    </el-card>
    <el-empty v-else-if="!loading" description="暂无预测曲线数据" :image-size="90" />

    <el-card v-if="curve && curve.forecast.length" shadow="never" class="table-card">
      <template #header>预测明细（含 95% 置信区间）</template>
      <el-table :data="forecastRows" size="small" border>
        <el-table-column prop="date" label="日期" width="130" />
        <el-table-column prop="horizon_step" label="步长" width="90" />
        <el-table-column prop="y_hat" label="预测值" />
        <el-table-column prop="y_lower" label="95% 下界" />
        <el-table-column prop="y_upper" label="95% 上界" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.forecast {
  padding-bottom: 8px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.select {
  width: 240px;
}
.select-narrow {
  width: 130px;
}
.alert {
  margin-bottom: 12px;
}
.meta {
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
}
.chart-card,
.table-card {
  margin-bottom: 16px;
}
</style>
