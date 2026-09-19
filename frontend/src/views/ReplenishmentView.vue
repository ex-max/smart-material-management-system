<script setup lang="ts">
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { listMaterials, listWarehouses } from '@/api/master'
import {
  confirmSuggestion,
  convertSuggestion,
  convertSuggestions,
  createPolicy,
  deletePolicy,
  generateSuggestions,
  listPolicies,
  listSuggestions,
  rejectSuggestion,
  updatePolicy,
  type ReplenishmentPolicy,
  type ReplenishmentPolicyCreate,
  type ReplenishmentSuggestion,
} from '@/api/replenishment'

interface NamedOption {
  id: number
  code: string
  name: string
}

const activeTab = ref<'suggestions' | 'policies'>('suggestions')

const materials = ref<Map<number, NamedOption>>(new Map())
const warehouses = ref<Map<number, NamedOption>>(new Map())
const materialOptions = ref<NamedOption[]>([])
const warehouseOptions = ref<NamedOption[]>([])

const statusMeta: Record<string, { label: string; type: '' | 'success' | 'info' | 'warning' | 'danger' }> = {
  OPEN: { label: '待确认', type: 'warning' },
  SUGGESTED: { label: '已确认', type: '' },
  CONVERTED: { label: '已转单', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
  EXPIRED: { label: '已失效', type: 'info' },
  CLOSED: { label: '已关闭', type: 'info' },
}

const strategyMeta: Record<string, string> = {
  FIXED: '固定阈值',
  FORECAST: '预测驱动',
  EOQ: 'EOQ',
  MIN_MAX: '最小-最大',
}

const triggerMeta: Record<string, string> = {
  BELOW_ROP: '低于 ROP',
  FORECAST: '预测触发',
  SAFETY: '安全库存',
  MANUAL: '手工',
}

// ---------------- 建议 ----------------
const filters = reactive<{
  status?: string
  material_id?: number
  warehouse_id?: number
  trigger_type?: string
}>({})
const suggestions = ref<ReplenishmentSuggestion[]>([])
const suggestionTotal = ref(0)
const suggestionLoading = ref(false)
const suggestionPage = ref(1)
const suggestionPageSize = ref(20)
const selectedIds = ref<number[]>([])
const generating = ref(false)

const detailVisible = ref(false)
const detail = ref<ReplenishmentSuggestion | null>(null)

const confirmVisible = ref(false)
const confirmTarget = ref<ReplenishmentSuggestion | null>(null)
const confirmForm = reactive<{ final_qty?: number; remark: string }>({ final_qty: undefined, remark: '' })

const rejectVisible = ref(false)
const rejectTarget = ref<ReplenishmentSuggestion | null>(null)
const rejectReason = ref('')

function materialName(id: number | null | undefined): string {
  if (id === null || id === undefined) {
    return '全局'
  }
  return materials.value.get(id)?.name || '#' + id
}

function warehouseName(id: number | null | undefined): string {
  if (id === null || id === undefined) {
    return '全部'
  }
  return warehouses.value.get(id)?.name || '#' + id
}

function fmt(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const num = Number(value)
  return Number.isNaN(num) ? String(value) : num.toFixed(2)
}

async function loadMasters() {
  try {
    const [materialPage, warehousePage] = await Promise.all([listMaterials(), listWarehouses()])
    const materialMap = new Map<number, NamedOption>()
    const materialList: NamedOption[] = []
    for (const item of materialPage.items) {
      const option = { id: item.id, code: item.code, name: item.name }
      materialMap.set(item.id, option)
      materialList.push(option)
    }
    const warehouseMap = new Map<number, NamedOption>()
    const warehouseList: NamedOption[] = []
    for (const item of warehousePage.items) {
      const option = { id: item.id, code: item.code, name: item.name }
      warehouseMap.set(item.id, option)
      warehouseList.push(option)
    }
    materials.value = materialMap
    materialOptions.value = materialList
    warehouses.value = warehouseMap
    warehouseOptions.value = warehouseList
  } catch {
    // 无主数据查看权限时静默降级为只显示 id
  }
}

async function loadSuggestions() {
  suggestionLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: suggestionPage.value,
      page_size: suggestionPageSize.value,
    }
    if (filters.status) {
      params.status = filters.status
    }
    if (filters.material_id) {
      params.material_id = filters.material_id
    }
    if (filters.warehouse_id) {
      params.warehouse_id = filters.warehouse_id
    }
    if (filters.trigger_type) {
      params.trigger_type = filters.trigger_type
    }
    const result = await listSuggestions(params)
    suggestions.value = result.items
    suggestionTotal.value = result.total
  } finally {
    suggestionLoading.value = false
  }
}

function searchSuggestions() {
  suggestionPage.value = 1
  void loadSuggestions()
}

function resetSuggestionFilters() {
  filters.status = undefined
  filters.material_id = undefined
  filters.warehouse_id = undefined
  filters.trigger_type = undefined
  searchSuggestions()
}

async function handleGenerate() {
  generating.value = true
  try {
    const scope: { material_id?: number; warehouse_id?: number } = {}
    if (filters.material_id) {
      scope.material_id = filters.material_id
    }
    if (filters.warehouse_id) {
      scope.warehouse_id = filters.warehouse_id
    }
    const result = await generateSuggestions(scope)
    ElMessage.success(
      '生成完成：新增 ' + result.created + '，更新 ' + result.updated + '，关闭 ' + result.closed,
    )
    await loadSuggestions()
  } finally {
    generating.value = false
  }
}

function handleSelectionChange(rows: ReplenishmentSuggestion[]) {
  selectedIds.value = rows.map((row) => row.id)
}

function openDetail(row: ReplenishmentSuggestion) {
  detail.value = row
  detailVisible.value = true
}

function openConfirm(row: ReplenishmentSuggestion) {
  confirmTarget.value = row
  confirmForm.final_qty = Number(row.suggested_qty)
  confirmForm.remark = ''
  confirmVisible.value = true
}

async function submitConfirm() {
  if (!confirmTarget.value) {
    return
  }
  await confirmSuggestion(confirmTarget.value.id, {
    final_qty: confirmForm.final_qty,
    remark: confirmForm.remark || null,
  })
  ElMessage.success('已确认建议，可转请购单')
  confirmVisible.value = false
  await loadSuggestions()
}

function openReject(row: ReplenishmentSuggestion) {
  rejectTarget.value = row
  rejectReason.value = ''
  rejectVisible.value = true
}

async function submitReject() {
  if (!rejectTarget.value) {
    return
  }
  await rejectSuggestion(rejectTarget.value.id, { reason: rejectReason.value || null })
  ElMessage.success('已驳回建议')
  rejectVisible.value = false
  await loadSuggestions()
}

async function handleConvert(row: ReplenishmentSuggestion) {
  try {
    await ElMessageBox.confirm('确认将该建议转为请购单（草稿）？', '转请购单', { type: 'warning' })
  } catch {
    return
  }
  const result = await convertSuggestion(row.id)
  ElMessage.success('已生成请购单 ' + result.pr.doc_no)
  detailVisible.value = false
  await loadSuggestions()
}

async function handleBatchConvert() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先勾选已确认的建议')
    return
  }
  try {
    await ElMessageBox.confirm('确认将选中的 ' + selectedIds.value.length + ' 条建议转为请购单？', '批量转单', {
      type: 'warning',
    })
  } catch {
    return
  }
  const results = await convertSuggestions(selectedIds.value)
  ElMessage.success('批量转单完成，共 ' + results.length + ' 张请购单')
  selectedIds.value = []
  await loadSuggestions()
}

// ---------------- 策略 ----------------
const policies = ref<ReplenishmentPolicy[]>([])
const policyTotal = ref(0)
const policyLoading = ref(false)
const policyPage = ref(1)
const policyPageSize = ref(20)

const policyVisible = ref(false)
const editingPolicyId = ref<number | null>(null)
const policySaving = ref(false)
const policyForm = reactive({
  policy_code: '',
  policy_name: '',
  material_id: undefined as number | undefined,
  warehouse_id: undefined as number | undefined,
  strategy: 'FORECAST',
  service_level_type: 'CSL',
  service_level: 0.95,
  review_period_days: 7,
  order_cost: undefined as number | undefined,
  holding_cost_rate: undefined as number | undefined,
  min_order_qty: undefined as number | undefined,
  pack_size: undefined as number | undefined,
  lead_time_days: undefined as number | undefined,
  is_active: true,
  remark: '',
})

const policyTitle = computed(() => (editingPolicyId.value === null ? '新建补货策略' : '编辑补货策略'))

async function loadPolicies() {
  policyLoading.value = true
  try {
    const result = await listPolicies({ page: policyPage.value, page_size: policyPageSize.value })
    policies.value = result.items
    policyTotal.value = result.total
  } finally {
    policyLoading.value = false
  }
}

function openPolicyDialog(row?: ReplenishmentPolicy) {
  if (row) {
    editingPolicyId.value = row.id
    policyForm.policy_code = row.policy_code
    policyForm.policy_name = row.policy_name || ''
    policyForm.material_id = row.material_id ?? undefined
    policyForm.warehouse_id = row.warehouse_id ?? undefined
    policyForm.strategy = row.strategy
    policyForm.service_level_type = row.service_level_type || 'CSL'
    policyForm.service_level = row.service_level ? Number(row.service_level) : 0.95
    policyForm.review_period_days = row.review_period_days ?? 7
    policyForm.order_cost = row.order_cost ? Number(row.order_cost) : undefined
    policyForm.holding_cost_rate = row.holding_cost_rate ? Number(row.holding_cost_rate) : undefined
    policyForm.min_order_qty = row.min_order_qty ? Number(row.min_order_qty) : undefined
    policyForm.pack_size = row.pack_size ? Number(row.pack_size) : undefined
    policyForm.lead_time_days = row.lead_time_days ? Number(row.lead_time_days) : undefined
    policyForm.is_active = row.is_active
    policyForm.remark = row.remark || ''
  } else {
    editingPolicyId.value = null
    policyForm.policy_code = ''
    policyForm.policy_name = ''
    policyForm.material_id = undefined
    policyForm.warehouse_id = undefined
    policyForm.strategy = 'FORECAST'
    policyForm.service_level_type = 'CSL'
    policyForm.service_level = 0.95
    policyForm.review_period_days = 7
    policyForm.order_cost = undefined
    policyForm.holding_cost_rate = undefined
    policyForm.min_order_qty = undefined
    policyForm.pack_size = undefined
    policyForm.lead_time_days = undefined
    policyForm.is_active = true
    policyForm.remark = ''
  }
  policyVisible.value = true
}

async function submitPolicy() {
  if (!policyForm.policy_code || !policyForm.strategy) {
    ElMessage.warning('策略编码与策略类型必填')
    return
  }
  const payload: ReplenishmentPolicyCreate = {
    policy_code: policyForm.policy_code,
    policy_name: policyForm.policy_name || null,
    material_id: policyForm.material_id ?? null,
    warehouse_id: policyForm.warehouse_id ?? null,
    strategy: policyForm.strategy,
    service_level_type: policyForm.service_level_type,
    service_level: policyForm.service_level,
    review_period_days: policyForm.review_period_days,
    order_cost: policyForm.order_cost ?? null,
    holding_cost_rate: policyForm.holding_cost_rate ?? null,
    min_order_qty: policyForm.min_order_qty ?? null,
    pack_size: policyForm.pack_size ?? null,
    lead_time_days: policyForm.lead_time_days ?? null,
    is_active: policyForm.is_active,
    remark: policyForm.remark || null,
  }
  policySaving.value = true
  try {
    if (editingPolicyId.value === null) {
      await createPolicy(payload)
      ElMessage.success('策略已创建')
    } else {
      await updatePolicy(editingPolicyId.value, payload)
      ElMessage.success('策略已更新')
    }
    policyVisible.value = false
    await loadPolicies()
  } finally {
    policySaving.value = false
  }
}

async function removePolicy(row: ReplenishmentPolicy) {
  try {
    await ElMessageBox.confirm('确认删除策略 ' + row.policy_code + '？', '删除策略', { type: 'warning' })
  } catch {
    return
  }
  await deletePolicy(row.id)
  ElMessage.success('已删除')
  await loadPolicies()
}

onMounted(async () => {
  await loadMasters()
  await Promise.all([loadSuggestions(), loadPolicies()])
})
</script>

<template>
  <div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="补货建议" name="suggestions">
        <div class="page-toolbar">
          <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
            <el-option v-for="(meta, key) in statusMeta" :key="key" :label="meta.label" :value="key" />
          </el-select>
          <el-select v-model="filters.material_id" placeholder="物资" clearable filterable style="width: 200px">
            <el-option
              v-for="item in materialOptions"
              :key="item.id"
              :label="item.code + ' ' + item.name"
              :value="item.id"
            />
          </el-select>
          <el-select v-model="filters.warehouse_id" placeholder="仓库" clearable style="width: 160px">
            <el-option
              v-for="item in warehouseOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
          <el-button :icon="Search" @click="searchSuggestions">查询</el-button>
          <el-button @click="resetSuggestionFilters">重置</el-button>
          <el-button type="primary" :icon="Refresh" :loading="generating" @click="handleGenerate">
            生成建议
          </el-button>
          <el-button type="success" :disabled="selectedIds.length === 0" @click="handleBatchConvert">
            批量转请购单
          </el-button>
          <span class="hint">生成范围取上方「物资/仓库」筛选</span>
        </div>

        <el-table
          v-loading="suggestionLoading"
          :data="suggestions"
          row-key="id"
          border
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="46" />
          <el-table-column prop="suggestion_no" label="建议号" width="180" />
          <el-table-column label="物资" min-width="140">
            <template #default="{ row }">{{ materialName(row.material_id) }}</template>
          </el-table-column>
          <el-table-column label="仓库" min-width="120">
            <template #default="{ row }">{{ warehouseName(row.warehouse_id) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <el-tag :type="statusMeta[row.status]?.type || 'info'">
                {{ statusMeta[row.status]?.label || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发" width="100">
            <template #default="{ row }">{{ triggerMeta[row.trigger_type] || row.trigger_type }}</template>
          </el-table-column>
          <el-table-column label="可用量" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.available_qty) }}</template>
          </el-table-column>
          <el-table-column label="ROP" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.rop) }}</template>
          </el-table-column>
          <el-table-column label="SS" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.safety_stock) }}</template>
          </el-table-column>
          <el-table-column label="预测日均" align="right" width="110">
            <template #default="{ row }">{{ fmt(row.daily_demand_hat) }}</template>
          </el-table-column>
          <el-table-column label="建议量" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.suggested_qty) }}</template>
          </el-table-column>
          <el-table-column label="确认量" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.final_qty) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <el-button v-if="row.status === 'OPEN'" link type="warning" @click="openConfirm(row)">
                确认
              </el-button>
              <el-button
                v-if="row.status === 'OPEN' || row.status === 'SUGGESTED'"
                link
                type="danger"
                @click="openReject(row)"
              >
                驳回
              </el-button>
              <el-button v-if="row.status === 'SUGGESTED'" link type="success" @click="handleConvert(row)">
                转请购单
              </el-button>
            </template>
          </el-table-column>
          <template #empty>暂无建议，可点击「生成建议」</template>
        </el-table>

        <el-pagination
          class="pager"
          layout="total, sizes, prev, pager, next"
          :total="suggestionTotal"
          v-model:current-page="suggestionPage"
          v-model:page-size="suggestionPageSize"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="loadSuggestions"
          @size-change="searchSuggestions"
        />
      </el-tab-pane>

      <el-tab-pane label="补货策略" name="policies">
        <div class="page-toolbar">
          <el-button type="primary" :icon="Plus" @click="openPolicyDialog()">新建策略</el-button>
          <el-button :icon="Refresh" @click="loadPolicies">刷新</el-button>
        </div>

        <el-table v-loading="policyLoading" :data="policies" row-key="id" border>
          <el-table-column prop="policy_code" label="策略编码" width="180" />
          <el-table-column prop="policy_name" label="名称" min-width="140" />
          <el-table-column label="物资" min-width="140">
            <template #default="{ row }">{{ materialName(row.material_id) }}</template>
          </el-table-column>
          <el-table-column label="仓库" min-width="120">
            <template #default="{ row }">{{ warehouseName(row.warehouse_id) }}</template>
          </el-table-column>
          <el-table-column label="策略" width="110">
            <template #default="{ row }">{{ strategyMeta[row.strategy] || row.strategy }}</template>
          </el-table-column>
          <el-table-column label="服务水平" width="110">
            <template #default="{ row }">{{ row.service_level_type }} / {{ fmt(row.service_level) }}</template>
          </el-table-column>
          <el-table-column label="复核周期" align="right" width="100">
            <template #default="{ row }">{{ row.review_period_days ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="起订量" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.min_order_qty) }}</template>
          </el-table-column>
          <el-table-column label="包装" align="right" width="90">
            <template #default="{ row }">{{ fmt(row.pack_size) }}</template>
          </el-table-column>
          <el-table-column label="提前期" align="right" width="100">
            <template #default="{ row }">{{ fmt(row.lead_time_days) }}</template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPolicyDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removePolicy(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>暂无策略</template>
        </el-table>

        <el-pagination
          class="pager"
          layout="total, sizes, prev, pager, next"
          :total="policyTotal"
          v-model:current-page="policyPage"
          v-model:page-size="policyPageSize"
          :page-sizes="[10, 20, 50]"
          @current-change="loadPolicies"
          @size-change="loadPolicies"
        />
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="detailVisible" title="建议详情（可解释）" size="620px">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="建议号">{{ detail.suggestion_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            {{ statusMeta[detail.status]?.label || detail.status }}
          </el-descriptions-item>
          <el-descriptions-item label="物资">{{ materialName(detail.material_id) }}</el-descriptions-item>
          <el-descriptions-item label="仓库">{{ warehouseName(detail.warehouse_id) }}</el-descriptions-item>
          <el-descriptions-item label="策略来源">#{{ detail.policy_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="预测批次">#{{ detail.forecast_run_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="当前结存">{{ fmt(detail.current_qty) }}</el-descriptions-item>
          <el-descriptions-item label="锁定">{{ fmt(detail.locked_qty) }}</el-descriptions-item>
          <el-descriptions-item label="在途">{{ fmt(detail.in_transit_qty) }}</el-descriptions-item>
          <el-descriptions-item label="可用量">{{ fmt(detail.available_qty) }}</el-descriptions-item>
          <el-descriptions-item label="预测日均 D̂">{{ fmt(detail.daily_demand_hat) }}</el-descriptions-item>
          <el-descriptions-item label="提前期 LT">{{ fmt(detail.lead_time_days) }}</el-descriptions-item>
          <el-descriptions-item label="σD">{{ fmt(detail.sigma_d) }}</el-descriptions-item>
          <el-descriptions-item label="σLT">{{ fmt(detail.sigma_lt) }}</el-descriptions-item>
          <el-descriptions-item label="安全库存 SS">{{ fmt(detail.safety_stock) }}</el-descriptions-item>
          <el-descriptions-item label="再订货点 ROP">{{ fmt(detail.rop) }}</el-descriptions-item>
          <el-descriptions-item label="EOQ 参考">{{ fmt(detail.eoq) }}</el-descriptions-item>
          <el-descriptions-item label="建议量">{{ fmt(detail.suggested_qty) }}</el-descriptions-item>
          <el-descriptions-item label="确认量">{{ fmt(detail.final_qty) }}</el-descriptions-item>
          <el-descriptions-item label="转请购单">
            {{ detail.converted_pr_id ? 'PR #' + detail.converted_pr_id : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="reason-title">触发依据 reason</div>
        <div class="reason-text">{{ detail.reason }}</div>
      </template>
    </el-drawer>

    <el-dialog v-model="confirmVisible" title="确认补货建议" width="420px">
      <el-form label-width="90px">
        <el-form-item label="建议量">
          <span>{{ fmt(confirmTarget?.suggested_qty) }}</span>
        </el-form-item>
        <el-form-item label="确认数量">
          <el-input-number v-model="confirmForm.final_qty" :min="0.0001" :step="1" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="confirmForm.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" @click="submitConfirm">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="驳回补货建议" width="420px">
      <el-form label-width="90px">
        <el-form-item label="建议号">{{ rejectTarget?.suggestion_no }}</el-form-item>
        <el-form-item label="驳回原因">
          <el-input v-model="rejectReason" type="textarea" :rows="3" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="policyVisible" :title="policyTitle" width="680px">
      <el-form label-width="120px">
        <el-form-item label="策略编码" required>
          <el-input v-model="policyForm.policy_code" :disabled="editingPolicyId !== null" maxlength="32" />
        </el-form-item>
        <el-form-item label="策略名称">
          <el-input v-model="policyForm.policy_name" maxlength="64" />
        </el-form-item>
        <el-form-item label="适用物资">
          <el-select v-model="policyForm.material_id" clearable filterable placeholder="全局" style="width: 100%">
            <el-option
              v-for="item in materialOptions"
              :key="item.id"
              :label="item.code + ' ' + item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="适用仓库">
          <el-select v-model="policyForm.warehouse_id" clearable placeholder="全部" style="width: 100%">
            <el-option v-for="item in warehouseOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略类型" required>
          <el-select v-model="policyForm.strategy" style="width: 100%">
            <el-option label="预测驱动" value="FORECAST" />
            <el-option label="最小-最大" value="MIN_MAX" />
            <el-option label="固定阈值" value="FIXED" />
            <el-option label="EOQ" value="EOQ" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务水平口径">
          <el-select v-model="policyForm.service_level_type" style="width: 100%">
            <el-option label="CSL（周期服务水平）" value="CSL" />
            <el-option label="FILL_RATE" value="FILL_RATE" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务水平（小数）">
          <el-input-number v-model="policyForm.service_level" :min="0.01" :max="0.99" :step="0.01" />
        </el-form-item>
        <el-form-item label="复核周期（天）">
          <el-input-number v-model="policyForm.review_period_days" :min="1" :step="1" />
        </el-form-item>
        <el-form-item label="订货成本">
          <el-input-number v-model="policyForm.order_cost" :min="0" />
        </el-form-item>
        <el-form-item label="持有成本率">
          <el-input-number v-model="policyForm.holding_cost_rate" :min="0" :step="0.01" />
        </el-form-item>
        <el-form-item label="起订量">
          <el-input-number v-model="policyForm.min_order_qty" :min="0.0001" />
        </el-form-item>
        <el-form-item label="包装倍数">
          <el-input-number v-model="policyForm.pack_size" :min="0.0001" />
        </el-form-item>
        <el-form-item label="提前期（天）">
          <el-input-number v-model="policyForm.lead_time_days" :min="0.01" :step="0.5" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="policyForm.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="policyForm.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyVisible = false">取消</el-button>
        <el-button type="primary" :loading="policySaving" @click="submitPolicy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.reason-title {
  margin: 18px 0 8px;
  font-weight: 600;
}
</style>
