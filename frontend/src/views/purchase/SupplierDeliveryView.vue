<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  acceptDelivery,
  cancelDelivery,
  createDelivery,
  deleteDelivery,
  getOrder,
  listDeliveries,
  listOrders,
  submitDelivery,
  type Delivery,
  type DeliveryCreate,
  type PO,
} from '@/api/purchase'
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

const INSPECTION_OPTIONS = [
  { label: '合格', value: 'PASS' },
  { label: '让步接收', value: 'CONCESSION' },
  { label: '不合格', value: 'REJECT' },
]

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return now.getFullYear() + '-' + month + '-' + day
}

const config: DocConfig = {
  title: '到货/验收单',
  description: '到货登记 → 提交 → 验收入库',
  fetch: (params) => listDeliveries(params),
  statusMeta: DOC_STATUS,
  canCreate: true,
  createPermission: 'purchase:manage',
  createLabel: '新建到货单',
  columns: [
    { prop: 'doc_no', label: '单号', width: 190 },
    { prop: 'po_id', label: '采购订单ID', width: 110 },
    {
      prop: 'supplier_id',
      label: '供应商',
      minWidth: 140,
      formatter: (row) => nameOf('supplier', row.supplier_id),
    },
    { prop: 'delivery_date', label: '到货日期', width: 110, formatter: (row) => fmtDate(row.delivery_date) },
    { prop: 'status', label: '状态', width: 90, tag: (row) => statusTag(row.status) },
    { prop: 'total_amount', label: '金额', width: 110, formatter: (row) => fmtNum(row.total_amount) },
    { prop: 'created_at', label: '创建时间', width: 160, formatter: (row) => fmtDateTime(row.created_at) },
  ],
  detailFields: (row) => [
    { label: '单号', value: row.doc_no },
    { label: '采购订单', value: String(row.po_id) },
    { label: '供应商', value: nameOf('supplier', row.supplier_id) },
    { label: '到货日期', value: fmtDate(row.delivery_date) },
    { label: '状态', value: statusTag(row.status).label },
    { label: '金额', value: fmtNum(row.total_amount) },
    { label: '验收时间', value: fmtDateTime(row.inspected_at) },
    { label: '作废原因', value: row.cancel_reason || '-' },
    { label: '备注', value: row.remark || '-' },
  ],
  detailItems: (row) => ({
    columns: [
      { prop: 'line_no', label: '行号', width: 70 },
      { prop: 'material_code', label: '物资编码', width: 150 },
      { prop: 'material_name', label: '物资', minWidth: 140 },
      { prop: 'quantity', label: '到货数量', width: 100, formatter: (item) => fmtNum(item.quantity) },
      { prop: 'accepted_qty', label: '合格数量', width: 100, formatter: (item) => fmtNum(item.accepted_qty) },
      { prop: 'rejected_qty', label: '拒收数量', width: 100, formatter: (item) => fmtNum(item.rejected_qty) },
      { prop: 'batch_no', label: '批次号', width: 130, formatter: (item) => item.batch_no || '-' },
      { prop: 'inspection_result', label: '检验结果', width: 100, formatter: (item) => item.inspection_result || '-' },
      { prop: 'expiry_date', label: '到期日期', width: 110, formatter: (item) => fmtDate(item.expiry_date) },
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
      confirm: (row) => '确认提交到货单 ' + row.doc_no + '？',
      run: (row) => submitDelivery(row.id),
    },
    {
      key: 'accept',
      label: '验收',
      type: 'success',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'PENDING',
      silent: true,
      run: (row) => openAccept(row),
    },
    {
      key: 'cancel',
      label: '拒收/作废',
      type: 'danger',
      permission: 'purchase:manage',
      visible: (row) => !['CANCELLED', 'COMPLETED'].includes(row.status),
      confirm: (row) => '确认作废到货单 ' + row.doc_no + '？',
      run: (row) => cancelDelivery(row.id),
    },
    {
      key: 'delete',
      label: '删除',
      type: 'danger',
      permission: 'purchase:manage',
      visible: (row) => row.status === 'DRAFT',
      confirm: () => '确认删除该草稿到货单？',
      run: (row) => deleteDelivery(row.id),
    },
  ],
}

// ---------------- 新建 ----------------
const createVisible = ref(false)
const saving = ref(false)
const poOptions = ref<PO[]>([])
const poItems = ref<PO['items']>([])

interface DeliveryItemForm {
  po_item_id?: number
  quantity: number
  batch_no: string
  production_date?: string
  expiry_date?: string
  inspection_result: string
}

const createForm = reactive({
  po_id: undefined as number | undefined,
  delivery_date: today(),
  remark: '',
  items: [] as DeliveryItemForm[],
})

function emptyItem(): DeliveryItemForm {
  return {
    po_item_id: undefined,
    quantity: 1,
    batch_no: '',
    production_date: undefined,
    expiry_date: undefined,
    inspection_result: 'PASS',
  }
}

const poItemOptions = computed(() =>
  poItems.value.map((item) => ({
    label:
      '#' + item.line_no + ' ' + item.material_code + ' ' + item.material_name + '（订购 ' + fmtNum(item.quantity) + '）',
    value: item.id,
  })),
)

async function openCreate() {
  createForm.po_id = undefined
  createForm.delivery_date = today()
  createForm.remark = ''
  createForm.items = [emptyItem()]
  poItems.value = []
  try {
    const result = await listOrders({ page: 1, page_size: 200 })
    poOptions.value = result.items.filter((po) => ['APPROVED', 'IN_PROGRESS'].includes(po.status))
  } catch {
    poOptions.value = []
  }
  createVisible.value = true
}

async function onPoChange(value: unknown) {
  const poId = value ? Number(value) : undefined
  createForm.items = [emptyItem()]
  poItems.value = []
  if (!poId) {
    return
  }
  try {
    const po = await getOrder(poId)
    poItems.value = po.items || []
  } catch {
    poItems.value = []
  }
}

async function submitCreate() {
  if (!createForm.po_id) {
    ElMessage.warning('请选择采购订单')
    return
  }
  const items = createForm.items.filter((item) => item.po_item_id && Number(item.quantity) > 0)
  if (items.length === 0) {
    ElMessage.warning('至少填写一行有效的到货明细')
    return
  }
  const payload: DeliveryCreate = {
    po_id: createForm.po_id,
    delivery_date: createForm.delivery_date || today(),
    remark: createForm.remark || null,
    items: items.map((item) => ({
      po_item_id: item.po_item_id as number,
      quantity: item.quantity,
      batch_no: item.batch_no || null,
      production_date: item.production_date || null,
      expiry_date: item.expiry_date || null,
      inspection_result: item.inspection_result || null,
      remark: null,
    })),
  }
  saving.value = true
  try {
    await createDelivery(payload)
    ElMessage.success('到货单已创建')
    createVisible.value = false
    await listRef.value?.reload()
  } finally {
    saving.value = false
  }
}

// ---------------- 验收 ----------------
const acceptVisible = ref(false)
const acceptTarget = ref<Delivery | null>(null)
const acceptForm = reactive({
  warehouse_id: undefined as number | undefined,
  location_id: undefined as number | undefined,
  remark: '',
})

interface AcceptItemForm {
  delivery_item_id: number
  accepted_qty: number
  rejected_qty: number
  inspection_result: string
  remark: string
}

const acceptItems = ref<AcceptItemForm[]>([])

async function openAccept(row: Delivery) {
  acceptTarget.value = row
  acceptForm.warehouse_id = undefined
  acceptForm.location_id = undefined
  acceptForm.remark = ''
  acceptItems.value = (row.items || []).map((item) => ({
    delivery_item_id: item.id,
    accepted_qty: Number(item.quantity),
    rejected_qty: 0,
    inspection_result: item.inspection_result || 'PASS',
    remark: '',
  }))
  acceptVisible.value = true
}

async function submitAccept() {
  if (!acceptTarget.value) {
    return
  }
  if (!acceptForm.warehouse_id) {
    ElMessage.warning('请选择入库仓库')
    return
  }
  saving.value = true
  try {
    await acceptDelivery(acceptTarget.value.id, {
      warehouse_id: acceptForm.warehouse_id,
      location_id: acceptForm.location_id || null,
      remark: acceptForm.remark || null,
      items: acceptItems.value.map((item) => ({
        delivery_item_id: item.delivery_item_id,
        accepted_qty: Number(item.accepted_qty) || 0,
        rejected_qty: Number(item.rejected_qty) || 0,
        inspection_result: item.inspection_result || null,
        remark: item.remark || null,
      })),
    })
    ElMessage.success('验收成功')
    acceptVisible.value = false
    await listRef.value?.reload()
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <DocumentView ref="listRef" :config="config" @create="openCreate" />

    <el-dialog v-model="createVisible" title="新建到货单" width="960px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="采购订单">
              <el-select
                v-model="createForm.po_id"
                filterable
                placeholder="选择已确认采购订单"
                style="width: 100%"
                @change="onPoChange"
              >
                <el-option
                  v-for="po in poOptions"
                  :key="po.id"
                  :label="po.doc_no + ' ' + nameOf('supplier', po.supplier_id)"
                  :value="po.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到货日期">
              <el-date-picker
                v-model="createForm.delivery_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="createForm.remark" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">到货明细</div>
      <el-table :data="createForm.items" border size="small">
        <el-table-column label="订单行" min-width="230">
          <template #default="{ row }">
            <el-select v-model="row.po_item_id" filterable placeholder="选择订单行" style="width: 100%">
              <el-option
                v-for="option in poItemOptions"
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
        <el-table-column label="批次号" width="140">
          <template #default="{ row }"><el-input v-model="row.batch_no" /></template>
        </el-table-column>
        <el-table-column label="生产日期" width="150">
          <template #default="{ row }">
            <el-date-picker v-model="row.production_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="到期日期" width="150">
          <template #default="{ row }">
            <el-date-picker v-model="row.expiry_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="检验结果" width="130">
          <template #default="{ row }">
            <el-select v-model="row.inspection_result" style="width: 100%">
              <el-option
                v-for="option in INSPECTION_OPTIONS"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
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

    <el-dialog v-model="acceptVisible" title="验收入库" width="880px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="入库仓库">
              <el-select v-model="acceptForm.warehouse_id" filterable placeholder="选择仓库" style="width: 100%">
                <el-option
                  v-for="option in warehouseOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="库位ID">
              <el-input-number v-model="acceptForm.location_id" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="acceptForm.remark" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="items-title">验收明细</div>
      <el-table :data="acceptItems" border size="small">
        <el-table-column label="合格数量" width="150">
          <template #default="{ row }">
            <el-input-number v-model="row.accepted_qty" :min="0" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="拒收数量" width="150">
          <template #default="{ row }">
            <el-input-number v-model="row.rejected_qty" :min="0" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="检验结果" width="150">
          <template #default="{ row }">
            <el-select v-model="row.inspection_result" style="width: 100%">
              <el-option
                v-for="option in INSPECTION_OPTIONS"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="160">
          <template #default="{ row }"><el-input v-model="row.remark" /></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="acceptVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitAccept">确认验收</el-button>
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
