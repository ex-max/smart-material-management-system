<script setup lang="ts">
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { useAuth } from '@/composables/useAuth'
import type { DocAction, DocColumn, DocConfig } from '@/components/document'

const props = defineProps<{ config: DocConfig }>()
const emit = defineEmits<{ (e: 'create'): void }>()

const { hasPerm } = useAuth()
const canCreate = computed(
  () => Boolean(props.config.canCreate) && (!props.config.createPermission || hasPerm(props.config.createPermission)),
)

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const filters = reactive<Record<string, unknown>>({})

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        params[key] = value
      }
    }
    const result = await props.config.fetch(params)
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function reset() {
  for (const key of Object.keys(filters)) {
    delete filters[key]
  }
  page.value = 1
  void load()
}

function visibleActions(row: any): DocAction[] {
  return (props.config.actions || []).filter(
    (action) => (!action.permission || hasPerm(action.permission)) && (!action.visible || action.visible(row)),
  )
}

async function runAction(action: DocAction, row: any) {
  if (action.confirm) {
    try {
      await ElMessageBox.confirm(action.confirm(row), action.label, { type: 'warning' })
    } catch {
      return
    }
  }
  await action.run(row)
  if (!action.silent) {
    ElMessage.success(action.label + '成功')
    await load()
  }
}

const detailVisible = ref(false)
const detail = ref<any>(null)
const detailFields = ref<{ label: string; value: string }[]>([])
const detailItems = ref<{ columns: DocColumn[]; rows: any[] } | null>(null)

function openDetail(row: any) {
  detail.value = row
  detailFields.value = props.config.detailFields ? props.config.detailFields(row) : []
  detailItems.value = props.config.detailItems ? props.config.detailItems(row) : null
  detailVisible.value = true
}

defineExpose({ reload: load, openDetail })

onMounted(load)
</script>

<template>
  <div class="doc-page">
    <el-card>
      <template #header>
        <div class="doc-header">
          <div>
            <span class="doc-title">{{ config.title }}</span>
            <span class="doc-desc">{{ config.description }}</span>
          </div>
          <div>
            <el-button :icon="Refresh" @click="load">刷新</el-button>
            <el-button v-if="canCreate" type="primary" :icon="Plus" @click="emit('create')">
              {{ config.createLabel || '新建' }}
            </el-button>
          </div>
        </div>
      </template>

      <div class="page-toolbar">
        <el-select
          v-if="Object.keys(config.statusMeta).length"
          v-model="filters.status"
          placeholder="状态"
          clearable
          style="width: 150px"
          @change="search"
        >
          <el-option v-for="(meta, key) in config.statusMeta" :key="key" :label="meta.label" :value="key" />
        </el-select>
        <el-select
          v-for="filter in config.extraFilters || []"
          :key="filter.prop"
          v-model="filters[filter.prop]"
          :placeholder="filter.label"
          clearable
          filterable
          style="width: 190px"
          @change="search"
        >
          <el-option
            v-for="option in filter.options()"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button :icon="Search" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <slot name="toolbar" />
        <span class="page-total">共 {{ total }} 条</span>
      </div>

      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column
          v-for="column in config.columns"
          :key="column.prop"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-tag v-if="column.tag" :type="column.tag(row).type" size="small">
              {{ column.tag(row).label }}
            </el-tag>
            <span v-else>{{ column.formatter ? column.formatter(row) : (row[column.prop] ?? '-') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              v-for="action in visibleActions(row)"
              :key="action.key"
              link
              :type="action.type || 'primary'"
              @click="runAction(action, row)"
            >
              {{ action.label }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="search"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" :title="config.title + '详情'" width="860px">
      <el-descriptions v-if="detail" :column="2" border size="small">
        <el-descriptions-item v-for="field in detailFields" :key="field.label" :label="field.label">
          {{ field.value }}
        </el-descriptions-item>
      </el-descriptions>
      <template v-if="detailItems && detailItems.rows.length">
        <div class="items-title">明细</div>
        <el-table :data="detailItems.rows" border size="small">
          <el-table-column
            v-for="column in detailItems.columns"
            :key="column.prop"
            :prop="column.prop"
            :label="column.label"
            :width="column.width"
            :min-width="column.minWidth"
          >
            <template #default="{ row }">
              <el-tag v-if="column.tag" :type="column.tag(row).type" size="small">
                {{ column.tag(row).label }}
              </el-tag>
              <span v-else>{{ column.formatter ? column.formatter(row) : (row[column.prop] ?? '-') }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <slot name="detail" :row="detail" />
    </el-dialog>
  </div>
</template>

<style scoped>
.doc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.doc-title {
  font-size: 16px;
  font-weight: 600;
}
.doc-desc {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}
.page-total {
  margin-left: auto;
  color: #909399;
  font-size: 13px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.items-title {
  margin: 16px 0 8px;
  font-weight: 600;
}
</style>