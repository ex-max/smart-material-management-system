<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  cancelOrder,
  confirmOrder,
  createOrder,
  deleteOrder,
  listOrders,
  type POCreate,
} from '@/api/purchase'
import DocumentView from '@/components/DocumentView.vue'
import type { DocConfig } from '@/components/document'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDate, fmtDateTime, fmtNum } from '@/utils/format'
import { DOC_STATUS, statusTag } from '@/utils/status'

const listRef = ref<any>(null)
const { ensureLoaded, optionsOf, nameOf } = useMasterOptions()

onMounted(ensureLoaded)

const materialOptions = computed(() =>
  optionsOf('material').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)
const supplierOptions = computed(() =>
  optionsOf('supplier').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return now.getFullYear() + '-' + month + '-' + day
}

const config: DocConfig = {
  title: '采购订单',
  description: '采购下单 → 确认 → 到货验收',
  fetch: (params) => listOrders(params),
  statusMeta: DOC_STATUS,
  canCreate: true,
  createPermission: 'purchase:manage',
  createLabel: '新建订单',
  columns: [
    { prop: 'doc_no', label: '单号', width: 190 },
    {
      prop: 'supplier_id',
      label: '供应商',
      minWidth: 140,
      formatter: (row) => nameOf('supplier', row.supplier_id),
    },
    { prop: 'status', label: '状态', width: 90, tag: (row) => statusTag(row.status) },
    { prop: 'order_date', label: '订单日期', width: 110, formatter: (row) => fmtDate(row.order_date) },
    { prop: 'expected_date', label: '期望到货', width: 110, formatter: (row) => fmtDate(row.expected_date) },
    { prop: 'total_amount', label: '含税金额', width: 110, formatter: (row) => fmtNum(row.total_amount) },
    { prop: 'tax_amount', label: '税额', width: 100, formatter: (row) => fmtNum(row.tax_amount) },
    { prop: 'created_at', label: '创建时间', width: 160, formatter: (row) => fmtDateTime(row.created_at) },
  ],
  detailFields: (row) => [
    { label: '单号', value: row.doc_no },
    { label: '供应商', value: nameOf('supplier', row.supplier_id) },
    { label: '状态', value: statusTag(row.status).label },
    { label: '订单日期', value: fmtDate(row.order_date) },
    { label: '期望到货', value: fmtDate(row.expected_date) },
    { label: '币种', value: row.currency || '-' },
    { label: '账期', value: row.payment_terms || '-' },
    { label: '含税金额', value: fmtNum(row.total_amount) },
    { label: '税额', value: fmtNum(row.tax_amount) },
    { label: '收货地址', value: row.delivery_address || '-' },
    { label: '备注', value: row.remark || '-' },
  ],
  detailItems: (row) => ({
    columns: [
      { prop: 'line_no', label: '行号', width: 70 },
      { prop: 'material_code', label: '物资编码', width: 150 },
      { prop: 'material_name', label: '物资', minWidth: 140 },
      { prop: 'quantity', label: '数量', width: 100, formatter: (item) => fmtNum(item.quantity) },
      { prop: 'unit_price', label: '单价', width: 100, formatter: (item) => fmtNum(item.unit_price) },
      { prop: 'tax_rate', label: '税率%', width: 90, formatter: (item) => fmtNum(item.tax_rate) },
      { prop: 'amount', label: '金额', width: 110, formatter: (item) => fmtNum(item.amount) },
      { prop: 'received_qty', label: '已收数量', width: 100, formatter: (item) => fmtNum(item.received_qty) },
    ],
    rows: row.items || [],
  }),
  actions: [
    {
      key: 'confirm',
      label: '确认下单',
      type: 'success',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: (row) => '确认下单 ' + row.doc_no + '？',
      run: (row) => confirmOrder(row.id),
    },
    {
      key: 'cancel',
      label: '作废',
      type: 'danger',
      permission: 'purchase:manage',
      visible: (row) => !['COMPLETED', 'CANCELLED'].includes(row.status),
      confirm: (row) => '确认作废 ' + row.doc_no + '？',
      run: (row) => cancelOrder(row.id),
    },
    {
      key: 'delete',
      label: '删除',
      type: 'danger',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: () => '确认删除该草稿订单？',
      run: (row) => deleteOrder(row.id),
    },
  ],
}

// ---------------- 新建 ----------------
const createVisible = ref(false)
const saving = ref(false)

interface POItemForm {
  material_id?: number
  quantity: number
  unit_price: number
  tax_rate: number
  expected_date?: string
}

const createForm = reactive({
  supplier_id: undefined as number | undefined,
  order_date: today(),
  expected_date: undefined as string | undefined,
  currency: 'CNY',
  payment_terms: '',
  delivery_address: '',
  remark: '',
  items: [] as POItemForm[],
})

function emptyItem(): POItemForm {
  return { material_id: undefined, quantity: 1, unit_price: 0, tax_rate: 0, expected_date: undefined }
}

function openCreate() {
  createForm.supplier_id = undefined
  createForm.order_date = today()
  createForm.expected_date = undefined
  createForm.currency = 'CNY'
  createForm.payment_terms = ''
  createForm.delivery_address = ''
  createForm.remark = ''
  createForm.items = [emptyItem()]
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.supplier_id) {
    ElMessage.warning('请选择供应商')
    return
  }
  const items = createForm.items.filter((item) => item.material_id && Number(item.quantity) > 0)
  if (items.length === 0) {
    ElMessage.warning('至少填写一行有效的物资与数量')
    return
  }
  const payload: POCreate = {
    supplier_id: createForm.supplier_id,
    order_date: createForm.order_date || null,
    expected_date: createForm.expected_date || null,
    currency: createForm.currency || 'CNY',
    payment_terms: createForm.payment_terms || null,
    delivery_address: createForm.delivery_address || null,
    remark: createForm.remark || null,
    items: items.map((item) => ({
      material_id: item.material_id as number,
      quantity: item.quantity,
      unit_price: Number(item.unit_price) || 0,
      tax_rate: Number(item.tax_rate) || 0,
      expected_date: item.expected_date || null,
    })),
  }
  saving.value = true
  try {
    await createOrder(payload)
    ElMessage.success('采购订单已创建')
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

    <el-dialog v-model="createVisible" title="新建采购订单" width="920px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="供应商">
              <el-select v-model="createForm.supplier_id" filterable placeholder="选择供应商" style="width: 100%">
                <el-option
                  v-for="option in supplierOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="订单日期">
              <el-date-picker
                v-model="createForm.order_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望到货">
              <el-date-picker
                v-model="createForm.expected_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="币种"><el-input v-model="createForm.currency" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="账期"><el-input v-model="createForm.payment_terms" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="收货地址"><el-input v-model="createForm.delivery_address" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="createForm.remark" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">订单明细</div>
      <el-table :data="createForm.items" border size="small">
        <el-table-column label="物资" min-width="200">
          <template #default="{ row }">
            <el-select v-model="row.material_id" filterable placeholder="选择物资" style="width: 100%">
              <el-option
                v-for="option in materialOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="0.01" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="单价" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.unit_price" :min="0" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="税率%" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.tax_rate" :min="0" :max="100" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="期望到货" width="150">
          <template #default="{ row }">
            <el-date-picker v-model="row.expected_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </template>
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
