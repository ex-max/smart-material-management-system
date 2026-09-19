<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  cancelStocktakeOrder,
  completeStocktakeOrder,
  countStocktakeOrder,
  createStocktakeOrder,
  deleteStocktakeOrder,
  listStocktakeOrders,
  reverseStocktakeOrder,
  startStocktakeOrder,
  type StocktakeCreate,
  type StocktakeOrder,
} from '@/api/inventory'
import DocumentView from '@/components/DocumentView.vue'
import type { DocConfig } from '@/components/document'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDate, fmtDateTime, fmtNum } from '@/utils/format'
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

const SCOPE_META: Record<string, string> = { FULL: '全盘', PARTIAL: '抽盘' }
function scopeLabel(scope: unknown): string {
  return SCOPE_META[String(scope || '')] || String(scope || '-')
}

const config: DocConfig = {
  title: '盘点单',
  description: '库存盘点：开始盘点 → 录入实盘 → 完成',
  fetch: (params) => listStocktakeOrders(params),
  statusMeta: DOC_STATUS,
  canCreate: true,
  createPermission: 'inventory:manage',
  createLabel: '新建盘点单',
  columns: [
    { prop: 'doc_no', label: '单号', width: 190 },
    { prop: 'warehouse_id', label: '仓库', width: 150, formatter: (row) => nameOf('warehouse', row.warehouse_id) },
    { prop: 'scope', label: '范围', width: 90, formatter: (row) => scopeLabel(row.scope) },
    { prop: 'status', label: '状态', width: 90, tag: (row) => statusTag(row.status) },
    { prop: 'planned_date', label: '计划日期', width: 120, formatter: (row) => fmtDate(row.planned_date) },
    { prop: 'created_at', label: '创建时间', width: 170, formatter: (row) => fmtDateTime(row.created_at) },
  ],
  detailFields: (row) => [
    { label: '单号', value: row.doc_no },
    { label: '仓库', value: nameOf('warehouse', row.warehouse_id) },
    { label: '范围', value: scopeLabel(row.scope) },
    { label: '状态', value: statusTag(row.status).label },
    { label: '计划日期', value: fmtDate(row.planned_date) },
    { label: '开始时间', value: fmtDateTime(row.started_at) },
    { label: '完成时间', value: fmtDateTime(row.finished_at) },
    { label: '作废原因', value: row.cancel_reason || '-' },
    { label: '备注', value: row.remark || '-' },
  ],
  detailItems: (row) => ({
    columns: [
      { prop: 'line_no', label: '行号', width: 70 },
      { prop: 'material_id', label: '物资', minWidth: 160, formatter: (item) => nameOf('material', item.material_id) },
      { prop: 'book_qty', label: '账面数量', width: 110, formatter: (item) => fmtNum(item.book_qty) },
      { prop: 'actual_qty', label: '实盘数量', width: 110, formatter: (item) => fmtNum(item.actual_qty) },
      { prop: 'diff_qty', label: '差异', width: 100, formatter: (item) => fmtNum(item.diff_qty) },
      { prop: 'reason', label: '差异原因', minWidth: 140, formatter: (item) => item.reason || '-' },
      { prop: 'remark', label: '备注', minWidth: 120, formatter: (item) => item.remark || '-' },
    ],
    rows: row.items || [],
  }),
  actions: [
    {
      key: 'start',
      label: '开始盘点',
      type: 'warning',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: (row) => '确认开始盘点 ' + row.doc_no + '？',
      run: (row) => startStocktakeOrder(row.id),
    },
    {
      key: 'count',
      label: '录入实盘',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'IN_PROGRESS',
      silent: true,
      run: (row) => openCount(row),
    },
    {
      key: 'complete',
      label: '完成',
      type: 'success',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'IN_PROGRESS',
      confirm: () => '确认完成该盘点单？完成后将按差异生成盘盈/盘亏流水。',
      run: (row) => completeStocktakeOrder(row.id),
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
      run: (row) => cancelStocktakeOrder(row.id),
    },
    {
      key: 'delete',
      label: '删除',
      type: 'danger',
      permission: 'inventory:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: () => '确认删除该草稿？',
      run: (row) => deleteStocktakeOrder(row.id),
    },
  ],
}

// ---------------- 录入实盘 ----------------
interface CountItemForm {
  stocktake_item_id: number
  material_name: string
  book_qty: unknown
  actual_qty: number
  reason: string
}
const countVisible = ref(false)
const countTarget = ref<StocktakeOrder | null>(null)
const counting = ref(false)
const countItems = ref<CountItemForm[]>([])

async function openCount(row: StocktakeOrder) {
  countTarget.value = row
  countItems.value = (row.items || []).map((item) => ({
    stocktake_item_id: item.id,
    material_name: nameOf('material', item.material_id),
    book_qty: item.book_qty,
    actual_qty: Number(item.actual_qty ?? item.book_qty) || 0,
    reason: item.reason || '',
  }))
  countVisible.value = true
}

async function submitCount() {
  if (!countTarget.value) {
    return
  }
  counting.value = true
  try {
    await countStocktakeOrder(countTarget.value.id, {
      items: countItems.value.map((item) => ({
        stocktake_item_id: item.stocktake_item_id,
        actual_qty: item.actual_qty,
        reason: item.reason || null,
      })),
    })
    ElMessage.success('实盘数量已保存')
    countVisible.value = false
    await listRef.value?.reload()
  } finally {
    counting.value = false
  }
}

// ---------------- 红冲 ----------------
const reverseVisible = ref(false)
const reverseTarget = ref<StocktakeOrder | null>(null)
const reverseReason = ref('')
const reversing = ref(false)

async function openReverse(row: StocktakeOrder) {
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
    await reverseStocktakeOrder(reverseTarget.value.id, reverseReason.value)
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
interface StocktakeItemForm {
  material_id?: number
  book_qty: number
  reason: string
}
const createForm = reactive({
  warehouse_id: undefined as number | undefined,
  scope: 'PARTIAL',
  planned_date: undefined as string | undefined,
  remark: '',
  items: [] as StocktakeItemForm[],
})

function emptyItem(): StocktakeItemForm {
  return { material_id: undefined, book_qty: 0, reason: '' }
}

function openCreate() {
  createForm.warehouse_id = undefined
  createForm.scope = 'PARTIAL'
  createForm.planned_date = undefined
  createForm.remark = ''
  createForm.items = [emptyItem()]
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.warehouse_id) {
    ElMessage.warning('请选择仓库')
    return
  }
  const items = createForm.items.filter((item) => item.material_id)
  if (items.length === 0) {
    ElMessage.warning('至少填写一行有效的物资')
    return
  }
  const payload: StocktakeCreate = {
    warehouse_id: createForm.warehouse_id,
    scope: createForm.scope,
    planned_date: createForm.planned_date || null,
    remark: createForm.remark || null,
    items: items.map((item) => ({
      material_id: item.material_id as number,
      book_qty: Number(item.book_qty) || 0,
      reason: item.reason || null,
    })),
  }
  saving.value = true
  try {
    await createStocktakeOrder(payload)
    ElMessage.success('盘点单已创建')
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

    <el-dialog v-model="countVisible" title="录入实盘数量" width="820px">
      <el-form label-width="90px">
        <el-form-item label="单号">{{ countTarget?.doc_no }}</el-form-item>
      </el-form>
      <el-table :data="countItems" border size="small">
        <el-table-column prop="material_name" label="物资" min-width="200" />
        <el-table-column label="账面数量" width="130" align="right">
          <template #default="{ row }">{{ fmtNum(row.book_qty) }}</template>
        </el-table-column>
        <el-table-column label="实盘数量" width="160">
          <template #default="{ row }">
            <el-input-number v-model="row.actual_qty" :min="0" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="差异原因" min-width="180">
          <template #default="{ row }"><el-input v-model="row.reason" placeholder="盘盈/盘亏原因" /></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="countVisible = false">取消</el-button>
        <el-button type="primary" :loading="counting" @click="submitCount">保存实盘</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="新建盘点单" width="820px">
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
            <el-form-item label="盘点范围">
              <el-select v-model="createForm.scope" style="width: 100%">
                <el-option label="全盘" value="FULL" />
                <el-option label="抽盘" value="PARTIAL" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划日期">
              <el-date-picker v-model="createForm.planned_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注"><el-input v-model="createForm.remark" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">盘点明细</div>
      <el-table :data="createForm.items" border size="small">
        <el-table-column label="物资" min-width="200">
          <template #default="{ row }">
            <el-select v-model="row.material_id" filterable placeholder="选择物资" style="width: 100%">
              <el-option v-for="option in materialOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="账面数量" width="130">
          <template #default="{ row }"><el-input-number v-model="row.book_qty" :min="0" :precision="2" style="width: 100%" /></template>
        </el-table-column>
        <el-table-column label="盘点原因" min-width="180">
          <template #default="{ row }"><el-input v-model="row.reason" placeholder="可选" /></template>
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

    <el-dialog v-model="reverseVisible" title="红冲盘点单" width="480px">
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
