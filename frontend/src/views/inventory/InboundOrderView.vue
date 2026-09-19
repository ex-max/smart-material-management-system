<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import {
  cancelInboundOrder,
  completeInboundOrder,
  listInboundOrders,
  postInboundOrder,
  reverseInboundOrder,
  type InboundOrder,
} from '@/api/inventory'
import DocumentView from '@/components/DocumentView.vue'
import type { DocConfig } from '@/components/document'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDate, fmtDateTime, fmtNum, fmtText } from '@/utils/format'
import { DOC_STATUS, statusTag } from '@/utils/status'

const listRef = ref<any>(null)
const { ensureLoaded, nameOf } = useMasterOptions()

onMounted(ensureLoaded)

const config: DocConfig = {
  title: '入库单',
  description: '采购到货 / 调拨入库等入库业务 → 过账 → 完成',
  fetch: (params) => listInboundOrders(params),
  statusMeta: DOC_STATUS,
  columns: [
    { prop: 'doc_no', label: '单号', width: 190 },
    { prop: 'source_type', label: '来源类型', width: 130 },
    { prop: 'warehouse_id', label: '仓库', width: 140, formatter: (row) => nameOf('warehouse', row.warehouse_id) },
    { prop: 'status', label: '状态', width: 90, tag: (row) => statusTag(row.status) },
    { prop: 'total_amount', label: '金额', width: 110, formatter: (row) => fmtNum(row.total_amount) },
    { prop: 'created_at', label: '创建时间', width: 170, formatter: (row) => fmtDateTime(row.created_at) },
  ],
  detailFields: (row) => [
    { label: '单号', value: row.doc_no },
    { label: '来源类型', value: fmtText(row.source_type) },
    { label: '来源ID', value: fmtText(row.source_id) },
    { label: '仓库', value: nameOf('warehouse', row.warehouse_id) },
    { label: '状态', value: statusTag(row.status).label },
    { label: '入库时间', value: fmtDateTime(row.inbound_at) },
    { label: '金额', value: fmtNum(row.total_amount) },
    { label: '作废原因', value: row.cancel_reason || '-' },
    { label: '备注', value: row.remark || '-' },
  ],
  detailItems: (row) => ({
    columns: [
      { prop: 'line_no', label: '行号', width: 70 },
      { prop: 'material_code', label: '物资编码', width: 150 },
      { prop: 'material_name', label: '物资', minWidth: 140 },
      { prop: 'quantity', label: '数量', width: 100, formatter: (item) => fmtNum(item.quantity) },
      { prop: 'unit_price', label: '单价', width: 100, formatter: (item) => fmtNum(item.unit_price) },
      { prop: 'amount', label: '金额', width: 110, formatter: (item) => fmtNum(item.amount) },
      { prop: 'batch_no', label: '批次号', width: 130 },
      { prop: 'expiry_date', label: '有效期', width: 110, formatter: (item) => fmtDate(item.expiry_date) },
    ],
    rows: row.items || [],
  }),
  actions: [
    {
      key: 'post',
      label: '过账',
      type: 'success',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: (row) => '确认过账 ' + row.doc_no + '？过账后将更新库存。',
      run: (row) => postInboundOrder(row.id),
    },
    {
      key: 'complete',
      label: '完成',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'IN_PROGRESS',
      confirm: () => '确认完成该入库单？',
      run: (row) => completeInboundOrder(row.id),
    },
    {
      key: 'reverse',
      label: '红冲',
      type: 'danger',
      permission: 'inventory:manage',
      visible: (row) => ['IN_PROGRESS', 'COMPLETED'].includes(row.status),
      silent: true,
      run: (row) => openReverse(row),
    },
    {
      key: 'cancel',
      label: '作废',
      type: 'danger',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: (row) => '确认作废 ' + row.doc_no + '？',
      run: (row) => cancelInboundOrder(row.id),
    },
  ],
}

// ---------------- 红冲 ----------------
const reverseVisible = ref(false)
const reverseTarget = ref<InboundOrder | null>(null)
const reverseReason = ref('')
const reversing = ref(false)

async function openReverse(row: InboundOrder) {
  reverseTarget.value = row
  reverseReason.value = ''
  reverseVisible.value = true
}

async function submitReverse() {
  if (!reverseTarget.value) {
    return
  }
  if (!reverseReason.value) {
    ElMessage.warning('请填写红冲原因')
    return
  }
  reversing.value = true
  try {
    await reverseInboundOrder(reverseTarget.value.id, reverseReason.value)
    ElMessage.success('红冲成功')
    reverseVisible.value = false
    await listRef.value?.reload()
  } finally {
    reversing.value = false
  }
}
</script>

<template>
  <div>
    <DocumentView ref="listRef" :config="config" />

    <el-dialog v-model="reverseVisible" title="红冲入库单" width="480px">
      <el-form label-width="90px">
        <el-form-item label="单号">{{ reverseTarget?.doc_no }}</el-form-item>
        <el-form-item label="红冲原因">
          <el-input v-model="reverseReason" type="textarea" :rows="3" placeholder="请填写红冲原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reverseVisible = false">取消</el-button>
        <el-button type="danger" :loading="reversing" @click="submitReverse">确认红冲</el-button>
      </template>
    </el-dialog>
  </div>
</template>
