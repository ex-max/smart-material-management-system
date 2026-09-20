<script setup lang="ts">
import { Download, Refresh } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import EChart from '@/components/EChart.vue'
import { useDashboard } from '@/composables/useDashboard'

const {
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
} = useDashboard()

const refreshedAt = ref('')

async function refresh(): Promise<void> {
  await load()
  refreshedAt.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

onMounted(refresh)
</script>

<template>
  <div v-loading="loading" class="home">
    <div class="toolbar">
      <div>
        <div class="page-desc">
          数据来自现有列表接口的前端聚合（每类最多取前 200 条）；无权限的模块静默降级为「暂无数据」。
        </div>
        <div v-if="refreshedAt" class="refresh-time">刷新时间：{{ refreshedAt }}</div>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" @click="refresh">刷新</el-button>
        <el-button type="primary" :icon="Download" @click="exportCsv">导出 CSV</el-button>
      </div>
    </div>

    <el-alert
      v-if="loadError"
      type="warning"
      :closable="false"
      show-icon
      title="概览数据加载失败，请稍后重试。"
      class="alert"
    />

    <el-row :gutter="12" class="stats">
      <el-col v-for="card in statCards" :key="card.key" :xs="12" :sm="8" :md="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">
            <span class="num">{{ card.value }}</span>
            <span class="unit">{{ card.unit }}</span>
          </div>
          <div class="stat-hint">{{ card.hint }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="charts">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header>单据状态分布</template>
          <EChart v-if="docStatusData.length" :option="docStatusOption" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header>库存 Top10 物资</template>
          <EChart v-if="topMaterials.length" :option="topInventoryOption" />
          <el-empty v-else description="暂无库存结存" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header>近期出入库趋势（按流水，最近 14 天）</template>
          <EChart v-if="trend.dates.length" :option="trendOption" />
          <el-empty v-else description="暂无库存流水" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header>预警类型分布</template>
          <EChart v-if="alertTypeData.length" :option="alertTypeOption" />
          <el-empty v-else description="暂无库存预警" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.home {
  padding-bottom: 8px;
}
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.page-desc {
  color: #606266;
  font-size: 13px;
}
.refresh-time {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.alert {
  margin-bottom: 12px;
}
.stats {
  margin-bottom: 4px;
}
.stat-card {
  margin-bottom: 12px;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.stat-value {
  margin: 6px 0 4px;
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.num {
  font-size: 26px;
  font-weight: 600;
  color: #303133;
}
.unit {
  font-size: 12px;
  color: #909399;
}
.stat-hint {
  color: #c0c4cc;
  font-size: 12px;
  min-height: 16px;
}
.charts {
  margin-top: 8px;
}
.chart-card {
  margin-bottom: 12px;
}
</style>
