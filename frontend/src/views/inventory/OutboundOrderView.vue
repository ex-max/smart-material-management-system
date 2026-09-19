<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  cancelOutboundOrder,
  completeOutboundOrder,
  createOutboundOrder,
  deleteOutboundOrder,
  listOutboundOrders,
  postOutboundOrder,
  reverseOutboundOrder,
  type OutboundCreate,
  type OutboundOrder,
} from '@/api/inventory'
import DocumentView from '@/components/DocumentView.vue'
import type { DocConfig } from '@/components/document'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDateTime, fmtNum, fmtText } from '@/utils/format'
import { DOC_STATUS, statusTag } from '@/utils/status'

const listRef = ref<any>(null)
const { ensureLoaded, optionsOf, nameOf } = useMasterOptions()

onMounted(ensureLoaded)

const warehouseOptions = computed(() =>
  optionsOf('warehouse').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)
const materialOptions = computed(() =>
  optionsOf('material').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)

const config: DocConfig = {
  title: '出库单',
  description: '领用 / 调拨 / 报废出库业务 → 过账 → 完成',
  fetch: (params) => listOutboundOrders(params),
  statusMeta: DOC_STATUS,
  canCreate: true,
  createPermission: 'inventory:manage',
  createLabel: '新建出库单',
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
    { label: '领用人ID', value: fmtText(row.receiver_id) },
    { label: '部门', value: row.dept_name || '-' },
    { label: '状态', value: statusTag(row.status).label },
    { label: '出库时间', value: fmtDateTime(row.outbound_at) },
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
      run: (row) => postOutboundOrder(row.id),
    },
    {
      key: 'complete',
      label: '完成',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'IN_PROGRESS',
      confirm: () => '确认完成该出库单？',
      run: (row) => completeOutboundOrder(row.id),
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
      run: (row) => cancelOutboundOrder(row.id),
    },
    {
      key: 'delete',
      label: '删除',
      type: 'danger',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: () => '确认删除该草稿？',
      run: (row) => deleteOutboundOrder(row.id),
    },
  ],
}

// ---------------- 红冲 ----------------
const reverseVisible = ref(false)
const reverseTarget = ref<OutboundOrder | null>(null)
const reverseReason = ref('')
const reversing = ref(false)

async function openReverse(row: OutboundOrder) {
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
    await reverseOutboundOrder(reverseTarget.value.id, reverseReason.value)
    ElMessage.success('红冲成功')
    reverseVisible.value = false
    await listRef.value?.reload()
  } finally {
    reversing.value = false
  }
}

// ---------------- 新建 ----------------
const createVisible = ref(false)
const saving = ref(false)
interface OutboundItemForm {
  material_id?: number
  quantity: number
  unit_price: number
}
const createForm = reactive({
  warehouse_id: undefined as number | undefined,
  source_type: 'REQUISITION_ISSUE',
  dept_name: '',
  remark: '',
  items: [] as OutboundItemForm[],
})

function emptyItem(): OutboundItemForm {
  return { material_id: undefined, quantity: 1, unit_price: 0 }
}

function openCreate() {
  createForm.warehouse_id = undefined
  createForm.source_type = 'REQUISITION_ISSUE'
  createForm.dept_name = ''
  createForm.remark = ''
  createForm.items = [emptyItem()]
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.warehouse_id) {
    ElMessage.warning('请选择仓库')
    return
  }
  const items = createForm.items.filter((item) => item.material_id && Number(item.quantity) > 0)
  if (items.length === 0) {
    ElMessage.warning('至少填写一行有效的物资与数量')
    return
  }
  const payload: OutboundCreate = {
    warehouse_id: createForm.warehouse_id,
    source_type: createForm.source_type,
    dept_name: createForm.dept_name || null,
    remark: createForm.remark || null,
    items: items.map((item) => ({
      material_id: item.material_id as number,
      quantity: item.quantity,
      unit_price: item.unit_price || 0,
    })),
  }
  saving.value = true
  try {
    await createOutboundOrder(payload)
    ElMessage.success('出库单已创建')
    createVisible.value = false
    await listRef.value?.reload()
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <DocumentView ref="listRef" :config="config" @create="openCreate" />

    <el-dialog v-model="createVisible" title="新建出库单" width="820px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="仓库">
              <el-select v-model="createForm.warehouse_id" filterable placeholder="选择仓库" style="width: 100%">
                <el-option v-for="option in warehouseOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源类型">
              <el-select v-model="createForm.source_type" style="width: 100%">
                <el-option label="领用出库" value="REQUISITION_ISSUE" />
                <el-option label="调拨出库" value="TRANSFER" />
                <el-option label="报废出库" value="SCRAP" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门"><el-input v-model="createForm.dept_name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注"><el-input v-model="createForm.remark" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">出库明细</div>
      <el-table :data="createForm.items" border size="small">
        <el-table-column label="物资" min-width="200">
          <template #default="{ row }">
            <el-select v-model="row.material_id" filterable placeholder="选择物资" style="width: 100%">
              <el-option v-for="option in materialOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="130">
          <template #default="{ row }"><el-input-number v-model="row.quantity" :min="0.01" :precision="2" style="width: 100%" /></template>
        </el-table-column>
        <el-table-column label="单价" width="140">
          <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" style="width: 100%" /></template>
        </el-table-column>
        <el-table-column width="60">
          <template #default="{ $index }">
            <el-button link type="danger" :icon="Delete" @click="createForm.items.splice($index, 1)" />
          </template>
        </el-table-column>
      </el-table>
      <el-button class="add-line" :icon="Plus" @click="createForm.items.push(emptyItem())">添加明细</el-button>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reverseVisible" title="红冲出库单" width="480px">
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

<style scoped>
.items-title {
  margin: 8px 0;
  font-weight: 600;
}
.add-line {
  margin-top: 8px;
}
</style>
