<script setup lang="ts">
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createDictItem,
  deleteDictItem,
  listDictItems,
  listDictTypes,
  updateDictItem,
  type DictItem,
  type DictItemCreate,
  type DictItemUpdate,
  type DictType,
} from '@/api/system'
import { useAuth } from '@/composables/useAuth'

const { hasPerm } = useAuth()
const canManage = computed(() => hasPerm('dict:manage'))

// ---------------- 左侧：字典类型 ----------------
const types = ref<DictType[]>([])
const activeType = ref<string>('')
const typesLoading = ref(false)

async function loadTypes() {
  typesLoading.value = true
  try {
    types.value = await listDictTypes()
    if (!activeType.value && types.value.length) {
      activeType.value = types.value[0].dict_type
      await loadItems()
    }
  } finally {
    typesLoading.value = false
  }
}

async function selectType(type: string) {
  activeType.value = type
  page.value = 1
  await loadItems()
}

// ---------------- 右侧：字典项 ----------------
const items = ref<DictItem[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const activeFilter = ref<'' | 'active' | 'inactive'>('')
const page = ref(1)
const pageSize = ref(20)

async function loadItems() {
  if (!activeType.value) {
    items.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (keyword.value.trim()) {
      params.keyword = keyword.value.trim()
    }
    if (activeFilter.value === 'active') {
      params.is_active = true
    } else if (activeFilter.value === 'inactive') {
      params.is_active = false
    }
    const data = await listDictItems({ ...params, dict_type: activeType.value })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void loadItems()
}

function reset() {
  keyword.value = ''
  activeFilter.value = ''
  page.value = 1
  void loadItems()
}

// ---------------- 新增/编辑弹窗 ----------------
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<Record<string, any>>({
  dict_type: '',
  dict_key: '',
  dict_label: '',
  sort_no: 0,
  is_active: true,
  remark: '',
})

const rules = computed<FormRules>(() => ({
  dict_type: [{ required: true, message: '请输入字典类型', trigger: 'blur' }],
  dict_key: [{ required: true, message: '请输入键', trigger: 'blur' }],
  dict_label: [{ required: true, message: '请输入显示值', trigger: 'blur' }],
}))

const dialogTitle = computed(() => (editingId.value === null ? '新增' : '编辑') + '字典项')

function openCreate() {
  editingId.value = null
  form.dict_type = activeType.value || ''
  form.dict_key = ''
  form.dict_label = ''
  form.sort_no = 0
  form.is_active = true
  form.remark = ''
  dialogVisible.value = true
}

function openEdit(row: DictItem) {
  editingId.value = row.id
  form.dict_type = row.dict_type
  form.dict_key = row.dict_key
  form.dict_label = row.dict_label
  form.sort_no = row.sort_no
  form.is_active = row.is_active
  form.remark = row.remark || ''
  dialogVisible.value = true
}

async function submitForm() {
  if (formRef.value) {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) {
      return
    }
  }
  saving.value = true
  try {
    if (editingId.value !== null) {
      const payload: DictItemUpdate = {
        dict_label: form.dict_label,
        sort_no: form.sort_no,
        is_active: form.is_active,
        remark: form.remark || null,
      }
      await updateDictItem(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      const payload: DictItemCreate = {
        dict_type: form.dict_type,
        dict_key: form.dict_key,
        dict_label: form.dict_label,
        sort_no: form.sort_no,
        is_active: form.is_active,
        remark: form.remark || null,
      }
      await createDictItem(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadTypes()
    await loadItems()
  } finally {
    saving.value = false
  }
}

async function removeItem(row: DictItem) {
  try {
    await ElMessageBox.confirm('确认删除「' + row.dict_label + '」？删除后不可见（软删除）。', '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  await deleteDictItem(row.id)
  ElMessage.success('已删除')
  await loadTypes()
  await loadItems()
}

onMounted(loadTypes)
</script>

<template>
  <el-row :gutter="16" class="dict-page">
    <el-col :span="7">
      <el-card>
        <template #header>
          <div class="type-header">
            <span class="type-title">字典类型</span>
            <el-button :icon="Refresh" circle @click="loadTypes" />
          </div>
        </template>
        <div v-loading="typesLoading" class="type-list">
          <el-empty v-if="!types.length" description="暂无字典类型" :image-size="60" />
          <div
            v-for="t in types"
            :key="t.dict_type"
            class="type-item"
            :class="{ active: t.dict_type === activeType }"
            @click="selectType(t.dict_type)"
          >
            <div class="type-name">{{ t.dict_type }}</div>
            <div class="type-count">共 {{ t.item_count }} 项 / 启用 {{ t.active_count }}</div>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :span="17">
      <el-card>
        <template #header>
          <div class="item-header">
            <div>
              <span class="item-title">字典项</span>
              <span class="item-desc">{{ activeType || '未选择类型' }}</span>
            </div>
            <el-button v-if="canManage" type="primary" :icon="Plus" :disabled="!activeType" @click="openCreate">
              新增
            </el-button>
          </div>
        </template>

        <div class="toolbar">
          <el-input v-model="keyword" placeholder="关键字（键/显示值）" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
          <el-select v-model="activeFilter" placeholder="状态" clearable style="width: 130px" @change="search">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
          <el-button @click="reset">重置</el-button>
          <span class="total">共 {{ total }} 条</span>
        </div>

        <el-table v-loading="loading" :data="items" border stripe>
          <el-table-column prop="dict_type" label="类型" width="140" show-overflow-tooltip />
          <el-table-column prop="dict_key" label="键" width="160" show-overflow-tooltip />
          <el-table-column prop="dict_label" label="显示值" min-width="140" show-overflow-tooltip />
          <el-table-column prop="sort_no" label="排序" width="80" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :disabled="!canManage" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" :disabled="!canManage" @click="removeItem(row)">删除</el-button>
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
            @current-change="loadItems"
          />
        </div>
      </el-card>
    </el-col>
  </el-row>

  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="类型" prop="dict_type">
        <el-input v-model="form.dict_type" :disabled="editingId !== null" placeholder="如 doc_status" />
      </el-form-item>
      <el-form-item label="键" prop="dict_key">
        <el-input v-model="form.dict_key" :disabled="editingId !== null" placeholder="如 DRAFT（不可修改）" />
      </el-form-item>
      <el-form-item label="显示值" prop="dict_label">
        <el-input v-model="form.dict_label" placeholder="如 草稿" />
      </el-form-item>
      <el-form-item label="排序" prop="sort_no">
        <el-input-number v-model="form.sort_no" :min="0" controls-position="right" style="width: 100%" />
      </el-form-item>
      <el-form-item label="启用" prop="is_active">
        <el-switch v-model="form.is_active" />
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input v-model="form.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dict-page {
  height: 100%;
}
.type-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.type-title {
  font-size: 16px;
  font-weight: 600;
}
.type-list {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}
.type-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid #ebeef5;
}
.type-item:hover {
  background: #f5f7fa;
}
.type-item.active {
  background: #ecf5ff;
  border-color: #409eff;
}
.type-name {
  font-weight: 600;
  color: #303133;
}
.type-count {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.item-title {
  font-size: 16px;
  font-weight: 600;
}
.item-desc {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}
.total {
  margin-left: auto;
  color: #909399;
  font-size: 13px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>