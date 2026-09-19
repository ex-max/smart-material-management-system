<script setup lang="ts">
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import {
  listMaterialCategories,
  listSuppliers,
  listUnits,
  listWarehouses,
  type Page,
} from '@/api/master'
import { useAuth } from '@/composables/useAuth'

import {
  masterConfigs,
  type FieldConfig,
  type FilterConfig,
  type MasterConfig,
  type OptionItem,
  type OptionKind,
  type Row,
  type RowContext,
  type SelectOption,
} from './masterConfigs'

const route = useRoute()
const { hasPerm } = useAuth()
const canManage = computed(() => hasPerm('material:manage'))

const config = computed<MasterConfig>(() => {
  const key = String(route.meta.entity || '')
  return masterConfigs[key] || masterConfigs.materials
})

// ---------------- 引用数据（分类/单位/供应商/仓库下拉）----------------
const options = reactive<Record<OptionKind, OptionItem[]>>({
  category: [],
  unit: [],
  supplier: [],
  warehouse: [],
})
const optionMaps: Record<OptionKind, Map<number, OptionItem>> = {
  category: new Map(),
  unit: new Map(),
  supplier: new Map(),
  warehouse: new Map(),
}

function fillOptions(kind: OptionKind, page: Page<{ id: number; code: string; name: string }>) {
  options[kind] = page.items.map((item) => ({ id: item.id, code: item.code, name: item.name }))
  optionMaps[kind] = new Map(options[kind].map((item) => [item.id, item]))
}

async function loadOptions() {
  try {
    const [categories, units, suppliers, warehouses] = await Promise.all([
      listMaterialCategories(),
      listUnits(),
      listSuppliers(),
      listWarehouses(),
    ])
    fillOptions('category', categories)
    fillOptions('unit', units)
    fillOptions('supplier', suppliers)
    fillOptions('warehouse', warehouses)
  } catch {
    // 无主数据查看权限时降级（后端 403 已由全局拦截器提示）
  }
}

const ctx: RowContext = {
  optionName: (kind, id) => {
    if (id === null || id === undefined || id === '') {
      return '-'
    }
    return optionMaps[kind].get(Number(id))?.name || '#' + String(id)
  },
  fmtNum: (value, digits = 2) => {
    if (value === null || value === undefined || value === '') {
      return '-'
    }
    const num = Number(value)
    return Number.isNaN(num) ? String(value) : num.toFixed(digits)
  },
  fmtText: (value) => (value === null || value === undefined || value === '' ? '-' : String(value)),
}

function selectOptions(field: FieldConfig): SelectOption[] {
  if (field.options) {
    return field.options
  }
  if (!field.optionKind) {
    return []
  }
  let list = options[field.optionKind]
  if (field.prop === 'parent_id' && editingId.value !== null) {
    list = list.filter((item) => item.id !== editingId.value)
  }
  return list.map((item) => ({ label: item.code + ' ' + item.name, value: item.id }))
}

function filterOptions(filter: FilterConfig): SelectOption[] {
  if (filter.options) {
    return filter.options
  }
  if (!filter.optionKind) {
    return []
  }
  return options[filter.optionKind].map((item) => ({ label: item.code + ' ' + item.name, value: item.id }))
}

// ---------------- 列表 ----------------
const rows = ref<Row[]>([])
const loading = ref(false)
const keyword = ref('')
const filters = reactive<Record<string, unknown>>({})
const page = ref(1)
const pageSize = ref(20)

async function loadRows() {
  loading.value = true
  try {
    const result = await config.value.api.list()
    rows.value = result.items as Row[]
  } finally {
    loading.value = false
  }
}

const filteredRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const active = config.value.filters || []
  return rows.value.filter((row) => {
    if (kw) {
      const haystack = config.value.searchProps.map((prop) => String(row[prop] ?? '')).join(' ').toLowerCase()
      if (!haystack.includes(kw)) {
        return false
      }
    }
    for (const filter of active) {
      const selected = filters[filter.prop]
      if (selected !== undefined && selected !== null && selected !== '' && row[filter.prop] !== selected) {
        return false
      }
    }
    return true
  })
})

const pagedRows = computed(() =>
  filteredRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value),
)

function resetFilters() {
  keyword.value = ''
  for (const key of Object.keys(filters)) {
    delete filters[key]
  }
  page.value = 1
}

watch(filteredRows, () => {
  const maxPage = Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value))
  if (page.value > maxPage) {
    page.value = maxPage
  }
})

// ---------------- 表单 ----------------
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = ref<Record<string, any>>({})

const rules = computed<FormRules>(() => {
  const result: FormRules = {}
  for (const field of config.value.fields) {
    if (field.required) {
      result[field.prop] = [
        { required: true, message: (field.type === 'select' ? '请选择' : '请输入') + field.label, trigger: field.type === 'select' ? 'change' : 'blur' },
      ]
    }
  }
  return result
})

const dialogTitle = computed(() => (editingId.value === null ? '新增' : '编辑') + config.value.title)

function openCreate() {
  editingId.value = null
  form.value = config.value.defaults()
  dialogVisible.value = true
}

function openEdit(row: Row) {
  editingId.value = row.id
  form.value = config.value.toForm(row)
  dialogVisible.value = true
}

async function submitForm() {
  if (formRef.value) {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) {
      return
    }
  }
  const editing = editingId.value !== null
  const payload = config.value.toPayload(form.value, editing)
  saving.value = true
  try {
    if (editing && editingId.value !== null) {
      await config.value.api.update(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await config.value.api.create(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadRows()
  } finally {
    saving.value = false
  }
}

async function removeRow(row: Row) {
  const label = String(row.name || row.code || row.id)
  try {
    await ElMessageBox.confirm('确认删除「' + label + '」？删除后不可见（软删除）。', '删除确认', { type: 'warning' })
  } catch {
    return
  }
  await config.value.api.remove(row.id)
  ElMessage.success('已删除')
  await loadRows()
}

// ---------------- 初始化 / 切换实体 ----------------
async function init() {
  resetFilters()
  await loadOptions()
  await loadRows()
}

onMounted(init)
watch(() => route.meta.entity, init)
</script>

<template>
  <div class="master-page">
    <el-card>
      <template #header>
        <div class="master-header">
          <div>
            <span class="master-title">{{ config.title }}</span>
            <span class="master-desc">{{ config.description }}</span>
          </div>
          <div>
            <el-button :icon="Refresh" @click="loadRows">刷新</el-button>
            <el-button v-if="canManage" type="primary" :icon="Plus" @click="openCreate">新增</el-button>
          </div>
        </div>
      </template>

      <div class="page-toolbar">
        <el-input
          v-model="keyword"
          placeholder="关键字（编码/名称）"
          clearable
          :prefix-icon="Search"
          style="width: 240px"
          @input="page = 1"
        />
        <el-select
          v-for="filter in config.filters"
          :key="filter.prop"
          v-model="filters[filter.prop]"
          :placeholder="filter.label"
          clearable
          filterable
          :style="{ width: (filter.width || 180) + 'px' }"
          @change="page = 1"
        >
          <el-option
            v-for="option in filterOptions(filter)"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button @click="resetFilters">重置</el-button>
        <span class="page-total">共 {{ filteredRows.length }} 条</span>
      </div>

      <el-table v-loading="loading" :data="pagedRows" border stripe>
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
            <el-tag v-if="column.tag" :type="column.tag(row, ctx).type" size="small">
              {{ column.tag(row, ctx).label }}
            </el-tag>
            <span v-else>{{ column.formatter ? column.formatter(row, ctx) : (row[column.prop] ?? '-') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!canManage" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :disabled="!canManage" @click="removeRow(row)">删除</el-button>
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
          :total="filteredRows.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="page = 1"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="760px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="16">
          <el-col v-for="field in config.fields" :key="field.prop" :span="field.span || 12">
            <el-form-item :label="field.label" :prop="field.prop">
              <el-input
                v-if="field.type === 'input'"
                v-model="form[field.prop]"
                :placeholder="field.placeholder"
                :disabled="editingId !== null && field.disabledOnEdit"
                clearable
              />
              <el-input
                v-else-if="field.type === 'textarea'"
                v-model="form[field.prop]"
                type="textarea"
                :rows="2"
                :placeholder="field.placeholder"
              />
              <el-input-number
                v-else-if="field.type === 'number'"
                v-model="form[field.prop]"
                :min="field.min"
                :max="field.max"
                :precision="field.precision"
                :step="field.step || 1"
                controls-position="right"
                style="width: 100%"
              />
              <el-switch v-else-if="field.type === 'switch'" v-model="form[field.prop]" />
              <el-select
                v-else
                v-model="form[field.prop]"
                :placeholder="field.placeholder || '请选择'"
                filterable
                clearable
                :disabled="editingId !== null && field.disabledOnEdit"
                style="width: 100%"
              >
                <el-option
                  v-for="option in selectOptions(field)"
                  :key="String(option.value)"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <div v-if="field.help" class="field-help">{{ field.help }}</div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.master-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.master-title {
  font-size: 16px;
  font-weight: 600;
}
.master-desc {
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
.field-help {
  width: 100%;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>
