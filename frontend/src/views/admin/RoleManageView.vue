<script setup lang="ts">
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createRole,
  deleteRole,
  getRolePermissions,
  listPermissions,
  listRoles,
  saveRolePermissions,
  updateRole,
  type Permission,
  type Role,
} from '@/api/admin'
import { useAuth } from '@/composables/useAuth'
import { fmtText } from '@/utils/format'

const { hasPerm } = useAuth()
const canManage = computed(() => hasPerm('role:manage'))

// ---------------- 角色列表 ----------------
const rows = ref<Role[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    rows.value = await listRoles()
  } finally {
    loading.value = false
  }
}

// ---------------- 新增 / 编辑 ----------------
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  description: '',
  sort_no: 0,
  status: 'ACTIVE',
})
const rules: FormRules = {
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    { min: 2, max: 32, message: '长度 2-32', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 2, max: 64, message: '长度 2-64', trigger: 'blur' },
  ],
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { code: '', name: '', description: '', sort_no: 0, status: 'ACTIVE' })
  dialogVisible.value = true
}

function openEdit(row: Role) {
  editingId.value = row.id
  Object.assign(form, {
    code: row.code,
    name: row.name,
    description: row.description || '',
    sort_no: row.sort_no,
    status: row.status,
  })
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  if (editingId.value === null) {
    await createRole({
      code: form.code,
      name: form.name,
      description: form.description || null,
      sort_no: form.sort_no,
      status: form.status,
      permission_ids: [],
    })
    ElMessage.success('角色已创建')
  } else {
    await updateRole(editingId.value, {
      name: form.name,
      description: form.description || null,
      sort_no: form.sort_no,
      status: form.status,
    })
    ElMessage.success('角色已更新')
  }
  dialogVisible.value = false
  void load()
}

async function remove(row: Role) {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.name}」？删除后其授权将一并失效。`, '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  await deleteRole(row.id)
  ElMessage.success('角色已删除')
  void load()
}

// ---------------- 权限分配 ----------------
const permDialog = ref(false)
const permTarget = ref<Role | null>(null)
const permissions = ref<Permission[]>([])
const checkedPermIds = ref<number[]>([])
const saving = ref(false)

/** 前端按 code 前缀分组（user:/role:/material:/purchase:/inventory:/forecast:/replenishment:/operation:/dict:/task:/attachment:）。 */
function groupPermissions(items: Permission[]) {
  const groups = new Map<string, Permission[]>()
  for (const p of items) {
    const prefix = p.code.includes(':') ? p.code.split(':')[0] : 'other'
    const list = groups.get(prefix) || []
    list.push(p)
    groups.set(prefix, list)
  }
  return [...groups.entries()].map(([key, list]) => ({ key, list }))
}

const permGroups = computed(() => groupPermissions(permissions.value))

async function openPermDialog(row: Role) {
  permTarget.value = row
  if (!permissions.value.length) {
    try {
      permissions.value = await listPermissions()
    } catch {
      // 无权限查看权限码时降级
    }
  }
  checkedPermIds.value = await getRolePermissions(row.id)
  permDialog.value = true
}

async function submitPermissions() {
  if (!permTarget.value) {
    return
  }
  saving.value = true
  try {
    await saveRolePermissions(permTarget.value.id, { permission_ids: checkedPermIds.value })
    ElMessage.success('权限已保存')
    permDialog.value = false
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-button :icon="Refresh" @click="load">刷新</el-button>
      <div class="spacer" />
      <el-button v-if="hasPerm('role:manage')" type="primary" :icon="Plus" @click="openCreate">新增角色</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="code" label="编码" min-width="110" />
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="description" label="描述" min-width="160">
        <template #default="{ row }">{{ fmtText(row.description) }}</template>
      </el-table-column>
      <el-table-column prop="sort_no" label="排序" width="70" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'" size="small">
            {{ row.status === 'ACTIVE' ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_builtin" label="类型" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.is_builtin" type="danger" size="small">内置</el-tag>
          <el-tag v-else type="info" size="small">自定义</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <template v-if="canManage">
            <el-button link type="primary" @click="openPermDialog(row)">配置权限</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="!row.is_builtin" link type="danger" @click="remove(row)">删除</el-button>
          </template>
          <span v-else class="muted">只读</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增 / 编辑角色 -->
    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新增角色' : '编辑角色'" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="如 SALES" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_no" :min="0" />
        </el-form-item>
        <el-form-item v-if="editingId !== null" label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="ACTIVE">启用</el-radio>
            <el-radio value="INACTIVE" :disabled="permTarget?.is_builtin">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 权限分配 -->
    <el-dialog v-model="permDialog" :title="`配置权限：${permTarget?.name}`" width="560px">
      <el-checkbox-group v-model="checkedPermIds" class="perm-groups">
        <div v-for="group in permGroups" :key="group.key" class="perm-group">
          <div class="perm-group-title">{{ group.key }}</div>
          <el-checkbox v-for="p in group.list" :key="p.id" :value="p.id">
            {{ p.code }}（{{ p.name }}）
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="permDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPermissions">保存权限</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.muted {
  color: #909399;
}
.perm-groups {
  display: block;
  width: 100%;
}
.perm-group {
  margin-bottom: 12px;
  padding: 8px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.perm-group-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #606266;
}
.perm-group :deep(.el-checkbox) {
  margin-right: 16px;
  margin-bottom: 6px;
  width: 220px;
}
</style>
