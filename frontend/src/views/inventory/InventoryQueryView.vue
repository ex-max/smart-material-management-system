<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  listInventory,
  listInventoryBatches,
  listInventoryTransactions,
  reconcileInventory,
  type InventoryBatch,
  type InventoryRow,
  type InventoryTxn,
  type Reconcile,
} from '@/api/inventory'
import { useMasterOptions } from '@/composables/useMasterOptions'
import { fmtDate, fmtDateTime, fmtNum } from '@/utils/format'
import { TXN_TYPE } from '@/utils/status'

type TabName = 'inventory' | 'batches' | 'txns'

interface TabState<T> {
  material_id?: number
  warehouse_id?: number
  page: number
  page_size: number
  total: number
  rows: T[]
  loading: boolean
}

const activeTab = ref<TabName>('inventory')
const { ensureLoaded, optionsOf, nameOf } = useMasterOptions()

onMounted(ensureLoaded)

const materialOptions = computed(() =>
  optionsOf('material').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)
const warehouseOptions = computed(() =>
  optionsOf('warehouse').map((item) => ({ label: item.code + ' ' + item.name, value: item.id })),
)

const inventoryTab = reactive<TabState<InventoryRow>>({
  page: 1,
  page_size: 20,
  total: 0,
  rows: [],
  loading: false,
})
const batchTab = reactive<TabState<InventoryBatch>>({
  page: 1,
  page_size: 20,
  total: 0,
  rows: [],
  loading: false,
})
const txnTab = reactive<TabState<InventoryTxn>>({
  page: 1,
  page_size: 20,
  total: 0,
  rows: [],
  loading: false,
})

function buildParams(tab: TabState<unknown>): Record<string, unknown> {
  const params: Record<string, unknown> = { page: tab.page, page_size: tab.page_size }
  if (tab.material_id) {
    params.material_id = tab.material_id
  }
  if (tab.warehouse_id) {
    params.warehouse_id = tab.warehouse_id
  }
  return params
}

async function loadInventory() {
  inventoryTab.loading = true
  try {
    const result = await listInventory(buildParams(inventoryTab))
    inventoryTab.rows = result.items
    inventoryTab.total = result.total
  } finally {
    inventoryTab.loading = false
  }
}

async function loadBatches() {
  batchTab.loading = true
  try {
    const result = await listInventoryBatches(buildParams(batchTab))
    batchTab.rows = result.items
    batchTab.total = result.total
  } finally {
    batchTab.loading = false
  }
}

async function loadTransactions() {
  txnTab.loading = true
  try {
    const result = await listInventoryTransactions(buildParams(txnTab))
    txnTab.rows = result.items
    txnTab.total = result.total
  } finally {
    txnTab.loading = false
  }
}

function searchInventory() {
  inventoryTab.page = 1
  void loadInventory()
}
function resetInventory() {
  inventoryTab.material_id = undefined
  inventoryTab.warehouse_id = undefined
  searchInventory()
}
function searchBatches() {
  batchTab.page = 1
  void loadBatches()
}
function resetBatches() {
  batchTab.material_id = undefined
  batchTab.warehouse_id = undefined
  searchBatches()
}
function searchTransactions() {
  txnTab.page = 1
  void loadTransactions()
}
function resetTransactions() {
  txnTab.material_id = undefined
  txnTab.warehouse_id = undefined
  searchTransactions()
}

// ---------------- 库存对账 ----------------
const reconcileVisible = ref(false)
const reconciling = ref(false)
const reconcile = ref<Reconcile | null>(null)

const RECONCILE_SECTIONS = [
  { key: 'inventory_vs_batch', label: '结存 vs 批次' },
  { key: 'inventory_vs_txn', label: '结存 vs 流水' },
  { key: 'batch_vs_txn', label: '批次 vs 流水' },
  { key: 'negative_or_locked', label: '负库存 / 锁定量异常' },
]

function sectionRows(sectionKey: string): Record<string, unknown>[] {
  const data = reconcile.value
  if (!data) {
    return []
  }
  const value = (data as unknown as Record<string, unknown>)[sectionKey]
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : []
}

function keysOf(rows: Record<string, unknown>[]): string[] {
  const keys: string[] = []
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!keys.includes(key)) {
        keys.push(key)
      }
    }
  }
  return keys
}

function cellText(value: unknown): string {
  if (value === null || value === undefined) {
    return '-'
  }
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

async function handleReconcile() {
  reconciling.value = true
  try {
    reconcile.value = await reconcileInventory()
    reconcileVisible.value = true
  } finally {
    reconciling.value = false
  }
}

onMounted(() => {
  void loadInventory()
  void loadBatches()
  void loadTransactions()
})
</script>

<template>
  <div>
    <el-card>
      <template #header>
        <div class="query-header">
          <span class="query-title">库存查询</span>
          <span class="query-desc">结存 / 批次 / 流水，库存余额由流水推导</span>
          <el-button class="reconcile-btn" type="primary" :loading="reconciling" @click="handleReconcile">
            库存对账
          </el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="结存" name="inventory">
          <div class="page-toolbar">
            <el-select v-model="inventoryTab.material_id" placeholder="物资" clearable filterable style="width: 200px" @change="searchInventory">
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="inventoryTab.warehouse_id" placeholder="仓库" clearable filterable style="width: 180px" @change="searchInventory">
              <el-option v-for="item in warehouseOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button :icon="Search" @click="searchInventory">查询</el-button>
            <el-button @click="resetInventory">重置</el-button>
          </div>
          <el-table v-loading="inventoryTab.loading" :data="inventoryTab.rows" border stripe>
            <el-table-column label="物资" min-width="170">
              <template #default="{ row }">{{ nameOf('material', row.material_id) }}</template>
            </el-table-column>
            <el-table-column label="仓库" min-width="140">
              <template #default="{ row }">{{ nameOf('warehouse', row.warehouse_id) }}</template>
            </el-table-column>
            <el-table-column label="结存数量" width="120" align="right">
              <template #default="{ row }">{{ fmtNum(row.quantity) }}</template>
            </el-table-column>
            <el-table-column label="锁定量" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.locked_qty) }}</template>
            </el-table-column>
            <el-table-column prop="version" label="版本" width="80" align="right" />
            <el-table-column label="最近变动" width="170">
              <template #default="{ row }">{{ fmtDateTime(row.last_txn_at) }}</template>
            </el-table-column>
            <template #empty>暂无结存数据</template>
          </el-table>
          <el-pagination
            class="pager"
            layout="total, sizes, prev, pager, next"
            :total="inventoryTab.total"
            v-model:current-page="inventoryTab.page"
            v-model:page-size="inventoryTab.page_size"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="loadInventory"
            @size-change="searchInventory"
          />
        </el-tab-pane>

        <el-tab-pane label="批次" name="batches">
          <div class="page-toolbar">
            <el-select v-model="batchTab.material_id" placeholder="物资" clearable filterable style="width: 200px" @change="searchBatches">
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="batchTab.warehouse_id" placeholder="仓库" clearable filterable style="width: 180px" @change="searchBatches">
              <el-option v-for="item in warehouseOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button :icon="Search" @click="searchBatches">查询</el-button>
            <el-button @click="resetBatches">重置</el-button>
          </div>
          <el-table v-loading="batchTab.loading" :data="batchTab.rows" border stripe>
            <el-table-column label="物资" min-width="170">
              <template #default="{ row }">{{ nameOf('material', row.material_id) }}</template>
            </el-table-column>
            <el-table-column label="仓库" min-width="140">
              <template #default="{ row }">{{ nameOf('warehouse', row.warehouse_id) }}</template>
            </el-table-column>
            <el-table-column prop="batch_no" label="批次号" width="160" />
            <el-table-column label="数量" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.quantity) }}</template>
            </el-table-column>
            <el-table-column label="锁定量" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.locked_qty) }}</template>
            </el-table-column>
            <el-table-column label="有效期" width="120">
              <template #default="{ row }">{{ fmtDate(row.expiry_date) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" />
            <template #empty>暂无批次数据</template>
          </el-table>
          <el-pagination
            class="pager"
            layout="total, sizes, prev, pager, next"
            :total="batchTab.total"
            v-model:current-page="batchTab.page"
            v-model:page-size="batchTab.page_size"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="loadBatches"
            @size-change="searchBatches"
          />
        </el-tab-pane>

        <el-tab-pane label="流水" name="txns">
          <div class="page-toolbar">
            <el-select v-model="txnTab.material_id" placeholder="物资" clearable filterable style="width: 200px" @change="searchTransactions">
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="txnTab.warehouse_id" placeholder="仓库" clearable filterable style="width: 180px" @change="searchTransactions">
              <el-option v-for="item in warehouseOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button :icon="Search" @click="searchTransactions">查询</el-button>
            <el-button @click="resetTransactions">重置</el-button>
          </div>
          <el-table v-loading="txnTab.loading" :data="txnTab.rows" border stripe>
            <el-table-column label="发生时间" width="170">
              <template #default="{ row }">{{ fmtDateTime(row.occurred_at) }}</template>
            </el-table-column>
            <el-table-column label="物资" min-width="170">
              <template #default="{ row }">{{ nameOf('material', row.material_id) }}</template>
            </el-table-column>
            <el-table-column label="仓库" min-width="140">
              <template #default="{ row }">{{ nameOf('warehouse', row.warehouse_id) }}</template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">{{ TXN_TYPE[row.txn_type] || row.txn_type }}</template>
            </el-table-column>
            <el-table-column label="数量" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.quantity) }}</template>
            </el-table-column>
            <el-table-column prop="source_no" label="来源单号" width="180" />
            <el-table-column label="结存后" width="120" align="right">
              <template #default="{ row }">{{ fmtNum(row.balance_after) }}</template>
            </el-table-column>
            <template #empty>暂无流水数据</template>
          </el-table>
          <el-pagination
            class="pager"
            layout="total, sizes, prev, pager, next"
            :total="txnTab.total"
            v-model:current-page="txnTab.page"
            v-model:page-size="txnTab.page_size"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="loadTransactions"
            @size-change="searchTransactions"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="reconcileVisible" title="库存对账" width="900px">
      <template v-if="reconcile">
        <div class="reconcile-head">
          <el-tag :type="reconcile.ok ? 'success' : 'danger'" size="large">
            {{ reconcile.ok ? '对账通过' : '对账失败' }}
          </el-tag>
          <span class="hint">结存应等于批次汇总、等于流水汇总，且无负库存/超锁定量</span>
        </div>
        <div v-for="section in RECONCILE_SECTIONS" :key="section.key" class="reconcile-section">
          <div class="section-title">{{ section.label }}（差异 {{ sectionRows(section.key).length }} 条）</div>
          <el-table v-if="sectionRows(section.key).length" :data="sectionRows(section.key)" border size="small">
            <el-table-column
              v-for="key in keysOf(sectionRows(section.key))"
              :key="key"
              :prop="key"
              :label="key"
              min-width="120"
            >
              <template #default="{ row }">{{ cellText(row[key]) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="无差异记录" :image-size="60" />
        </div>
      </template>
      <template #footer>
        <el-button @click="reconcileVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.query-header {
  display: flex;
  align-items: center;
}
.query-title {
  font-size: 16px;
  font-weight: 600;
}
.query-desc {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}
.reconcile-btn {
  margin-left: auto;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.reconcile-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.reconcile-section {
  margin-top: 16px;
}
.section-title {
  margin-bottom: 8px;
  font-weight: 600;
  font-size: 13px;
}
</style>
