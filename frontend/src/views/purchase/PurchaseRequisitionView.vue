<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  approveRequisition,
  cancelRequisition,
  convertRequisition,
  createRequisition,
  deleteRequisition,
  listRequisitions,
  submitRequisition,
  type PR,
  type PRCreate,
} from '@/api/purchase'
import DocumentView from '@/components/DocumentView.vue'
import type { DocConfig } from '@/components/document'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDate, fmtDateTime, fmtNum } from '@/utils/format'
import { DOC_STATUS, statusTag } from '@/utils/status'

const listRef = ref<any>(null)
const { ensureLoaded, optionsOf } = useMasterOptions()

onMounted(ensureLoaded)

const materialOptions = computed(() =>
  optionsOf('material').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)
const supplierOptions = computed(() =>
  optionsOf('supplier').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)

const config: DocConfig = {
  title: '请购单',
  description: '需求申请 → 审批 → 转采购订单',
  fetch: (params) => listRequisitions(params),
  statusMeta: DOC_STATUS,
  canCreate: true,
  createPermission: 'purchase:manage',
  columns: [
    { prop: 'doc_no', label: '单号', width: 190 },
    { prop: 'title', label: '标题', minWidth: 140 },
    { prop: 'dept_name', label: '部门', width: 110 },
    { prop: 'status', label: '状态', width: 90, tag: (row) => statusTag(row.status) },
    { prop: 'priority', label: '优先级', width: 80 },
    { prop: 'total_amount', label: '金额', width: 100, formatter: (row) => fmtNum(row.total_amount) },
    { prop: 'expected_date', label: '期望到货', width: 110, formatter: (row) => fmtDate(row.expected_date) },
    { prop: 'created_at', label: '创建时间', width: 160, formatter: (row) => fmtDateTime(row.created_at) },
  ],
  detailFields: (row) => [
    { label: '单号', value: row.doc_no },
    { label: '标题', value: row.title || '-' },
    { label: '部门', value: row.dept_name || '-' },
    { label: '状态', value: statusTag(row.status).label },
    { label: '优先级', value: String(row.priority) },
    { label: '金额', value: fmtNum(row.total_amount) },
    { label: '期望到货', value: fmtDate(row.expected_date) },
    { label: '申请原因', value: row.reason || '-' },
    { label: '审批时间', value: fmtDateTime(row.approved_at) },
    { label: '备注', value: row.remark || '-' },
  ],
  detailItems: (row) => ({
    columns: [
      { prop: 'line_no', label: '行号', width: 70 },
      { prop: 'material_code', label: '物资编码', width: 150 },
      { prop: 'material_name', label: '物资', minWidth: 140 },
      { prop: 'quantity', label: '数量', width: 100, formatter: (item) => fmtNum(item.quantity) },
      { prop: 'unit_name', label: '单位', width: 80 },
      { prop: 'purpose', label: '用途', minWidth: 140 },
    ],
    rows: row.items || [],
  }),
  actions: [
    {
      key: 'submit',
      label: '提交',
      type: 'warning',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: () => '确认提交该请购单进入审批？',
      run: (row) => submitRequisition(row.id),
    },
    {
      key: 'approve',
      label: '审批',
      type: 'success',
      permission: 'purchase:approve',
      visible: (row) => row.status === 'PENDING',
      confirm: () => '确认审批通过？',
      run: (row) => approveRequisition(row.id),
    },
    {
      key: 'convert',
      label: '转订单',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'APPROVED',
      silent: true,
      run: (row) => openConvert(row),
    },
    {
      key: 'cancel',
      label: '作废',
      type: 'danger',
      permission: 'purchase:manage',
      visible: (row) => !['COMPLETED', 'CANCELLED'].includes(row.status),
      confirm: (row) => '确认作废 ' + row.doc_no + '？',
      run: (row) => cancelRequisition(row.id),
    },
    {
      key: 'delete',
      label: '删除',
      type: 'danger',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: () => '确认删除该草稿？',
      run: (row) => deleteRequisition(row.id),
    },
  ],
}

// ---------------- 新建 ----------------
const createVisible = ref(false)
const saving = ref(false)
interface PRItemForm {
  material_id?: number
  quantity: number
  purpose: string
  expected_date?: string
}
const createForm = reactive({
  title: '',
  dept_name: '',
  priority: 3,
  expected_date: undefined as string | undefined,
  reason: '',
  remark: '',
  items: [] as PRItemForm[],
})

function emptyItem(): PRItemForm {
  return { material_id: undefined, quantity: 1, purpose: '', expected_date: undefined }
}

function openCreate() {
  createForm.title = ''
  createForm.dept_name = ''
  createForm.priority = 3
  createForm.expected_date = undefined
  createForm.reason = ''
  createForm.remark = ''
  createForm.items = [emptyItem()]
  createVisible.value = true
}

async function submitCreate() {
  const items = createForm.items.filter((item) => item.material_id && Number(item.quantity) > 0)
  if (items.length === 0) {
    ElMessage.warning('至少填写一行有效的物资与数量')
    return
  }
  const payload: PRCreate = {
    title: createForm.title || null,
    dept_name: createForm.dept_name || null,
    priority: createForm.priority,
    expected_date: createForm.expected_date || null,
    reason: createForm.reason || null,
    remark: createForm.remark || null,
    items: items.map((item) => ({
      material_id: item.material_id as number,
      quantity: item.quantity,
      purpose: item.purpose || null,
      expected_date: item.expected_date || null,
    })),
  }
  saving.value = true
  try {
    await createRequisition(payload)
    ElMessage.success('请购单已创建')
    createVisible.value = false
    await listRef.value?.reload()
  } finally {
    saving.value = false
  }
}

// ---------------- 转采购订单 ----------------
const convertVisible = ref(false)
const convertTarget = ref<PR | null>(null)
const convertForm = reactive({
  supplier_id: undefined as number | undefined,
  currency: 'CNY',
  payment_terms: '',
  delivery_address: '',
  expected_date: undefined as string | undefined,
  remark: '',
})
const convertItems = ref<{ pr_item_id: number; material_name: string; quantity: unknown; unit_price: number; tax_rate: number }[]>([])

async function openConvert(row: PR) {
  convertTarget.value = row
  convertForm.supplier_id = undefined
  convertForm.currency = 'CNY'
  convertForm.payment_terms = ''
  convertForm.delivery_address = ''
  convertForm.expected_date = undefined
  convertForm.remark = ''
  convertItems.value = (row.items || []).map((item) => ({
    pr_item_id: item.id,
    material_name: item.material_code + ' ' + item.material_name,
    quantity: item.quantity,
    unit_price: 0,
    tax_rate: 0,
  }))
  convertVisible.value = true
}

async function submitConvert() {
  if (!convertTarget.value) {
    return
  }
  if (!convertForm.supplier_id) {
    ElMessage.warning('请选择供应商')
    return
  }
  saving.value = true
  try {
    await convertRequisition(convertTarget.value.id, {
      supplier_id: convertForm.supplier_id,
      currency: convertForm.currency || 'CNY',
      payment_terms: convertForm.payment_terms || null,
      delivery_address: convertForm.delivery_address || null,
      expected_date: convertForm.expected_date || null,
      remark: convertForm.remark || null,
      items: convertItems.value.map((item) => ({
        pr_item_id: item.pr_item_id,
        unit_price: Number(item.unit_price) || 0,
        tax_rate: Number(item.tax_rate) || 0,
      })),
    })
    ElMessage.success('已生成采购订单')
    convertVisible.value = false
    await listRef.value?.reload()
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <DocumentView ref="listRef" :config="config" @create="openCreate" />

    <el-dialog v-model="createVisible" title="新建请购单" width="820px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="标题"><el-input v-model="createForm.title" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门"><el-input v-model="createForm.dept_name" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="createForm.priority" :min="1" :max="5" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="期望到货">
              <el-date-picker v-model="createForm.expected_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="原因"><el-input v-model="createForm.reason" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">申请明细</div>
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
        <el-table-column label="用途" min-width="150">
          <template #default="{ row }"><el-input v-model="row.purpose" /></template>
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

    <el-dialog v-model="convertVisible" title="转采购订单" width="820px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="供应商">
              <el-select v-model="convertForm.supplier_id" filterable placeholder="选择供应商" style="width: 100%">
                <el-option v-for="option in supplierOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="币种"><el-input v-model="convertForm.currency" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="账期"><el-input v-model="convertForm.payment_terms" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望到货">
              <el-date-picker v-model="convertForm.expected_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="收货地址"><el-input v-model="convertForm.delivery_address" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">采购明细（可填写单价/税率）</div>
      <el-table :data="convertItems" border size="small">
        <el-table-column prop="material_name" label="物资" min-width="200" />
        <el-table-column label="数量" width="110">
          <template #default="{ row }">{{ row.quantity }}</template>
        </el-table-column>
        <el-table-column label="单价" width="140">
          <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" style="width: 100%" /></template>
        </el-table-column>
        <el-table-column label="税率%" width="130">
          <template #default="{ row }"><el-input-number v-model="row.tax_rate" :min="0" :max="100" :precision="2" style="width: 100%" /></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="convertVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitConvert">生成采购订单</el-button>
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
