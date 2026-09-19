<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import {
  ackStockAlert,
  ignoreStockAlert,
  listStockAlerts,
  resolveStockAlert,
  scanStockAlerts,
} from '@/api/inventory'
import DocumentView from '@/components/DocumentView.vue'
import type { DocConfig } from '@/components/document'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDateTime, fmtNum } from '@/utils/format'
import { ALERT_STATUS, ALERT_TYPE, statusTag } from '@/utils/status'

const listRef = ref<any>(null)
const { ensureLoaded, nameOf } = useMasterOptions()

onMounted(ensureLoaded)

function alertTypeLabel(alertType: unknown): string {
  return ALERT_TYPE[String(alertType || '')] || String(alertType || '-')
}

const config: DocConfig = {
  title: '库存预警',
  description: '零库存 / 低库存 / 超储 / 临期自动扫描与处理',
  fetch: (params) => listStockAlerts(params),
  statusMeta: ALERT_STATUS,
  columns: [
    { prop: 'material_id', label: '物资', minWidth: 160, formatter: (row) => nameOf('material', row.material_id) },
    { prop: 'warehouse_id', label: '仓库', width: 150, formatter: (row) => nameOf('warehouse', row.warehouse_id) },
    { prop: 'alert_type', label: '类型', width: 100, formatter: (row) => alertTypeLabel(row.alert_type) },
    { prop: 'level', label: '级别', width: 80 },
    { prop: 'status', label: '状态', width: 90, tag: (row) => statusTag(row.status, ALERT_STATUS) },
    { prop: 'current_value', label: '当前值', width: 100, formatter: (row) => fmtNum(row.current_value) },
    { prop: 'threshold', label: '阈值', width: 100, formatter: (row) => fmtNum(row.threshold) },
    { prop: 'triggered_at', label: '触发时间', width: 170, formatter: (row) => fmtDateTime(row.triggered_at) },
  ],
  detailFields: (row) => [
    { label: '物资', value: nameOf('material', row.material_id) },
    { label: '仓库', value: nameOf('warehouse', row.warehouse_id) },
    { label: '类型', value: alertTypeLabel(row.alert_type) },
    { label: '级别', value: String(row.level ?? '-') },
    { label: '状态', value: statusTag(row.status, ALERT_STATUS).label },
    { label: '当前值', value: fmtNum(row.current_value) },
    { label: '阈值', value: fmtNum(row.threshold) },
    { label: '触发时间', value: fmtDateTime(row.triggered_at) },
    { label: '确认时间', value: fmtDateTime(row.acked_at) },
    { label: '解决时间', value: fmtDateTime(row.resolved_at) },
    { label: '消息', value: row.message || '-' },
    { label: '备注', value: row.remark || '-' },
  ],
  actions: [
    {
      key: 'ack',
      label: '确认',
      type: 'warning',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'OPEN',
      confirm: () => '确认该预警？',
      run: (row) => ackStockAlert(row.id),
    },
    {
      key: 'resolve',
      label: '解决',
      type: 'success',
      permission: 'inventory:manage',
      visible: (row) => ['OPEN', 'ACKED'].includes(row.status),
      confirm: () => '确认该预警已解决？',
      run: (row) => resolveStockAlert(row.id),
    },
    {
      key: 'ignore',
      label: '忽略',
      type: 'info',
      permission: 'inventory:manage',
      visible: (row) => ['OPEN', 'ACKED'].includes(row.status),
      confirm: () => '确认忽略该预警？',
      run: (row) => ignoreStockAlert(row.id),
    },
  ],
}

// ---------------- 扫描预警 ----------------
const scanning = ref(false)

async function handleScan() {
  scanning.value = true
  try {
    const result = await scanStockAlerts()
    ElMessage.success('扫描完成：扫描 ' + result.scanned + ' 项，新增预警 ' + result.created + ' 条')
    await listRef.value?.reload()
  } finally {
    scanning.value = false
  }
}
</script>

<template>
  <div>
    <DocumentView ref="listRef" :config="config">
      <template #toolbar>
        <el-button type="primary" :icon="Refresh" :loading="scanning" @click="handleScan">扫描预警</el-button>
      </template>
    </DocumentView>
  </div>
</template>
