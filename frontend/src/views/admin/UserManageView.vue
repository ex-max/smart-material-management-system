<script setup lang="ts">
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  assignUserRoles,
  createUser,
  listRoles,
  listUsers,
  resetUserPassword,
  updateUser,
  type Role,
  type User,
} from '@/api/admin'
import { useAuth } from '@/composables/useAuth'
import { fmtDateTime, fmtText } from '@/utils/format'

const { hasPerm } = useAuth()
const canManage = computed(() => hasPerm('user:create') || hasPerm('user:update'))

// ---------------- 列表 ----------------
const rows = ref<User[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')

async function load() {
  loading.value = true
  try {
    const data = await listUsers({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

// ---------------- 新增 / 编辑 ----------------
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  real_name: '',
  phone: '',
  email: '',
  dept_name: '',
  status: 'ACTIVE',
  role_ids: [] as number[],
})
const roles = ref<Role[]>([])

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    {
      validator: (_rule, value, callback) => {
        if (editingId.value === null && !value) {
          callback(new Error('请输入初始密码'))
        } else if (value && value.length < 6) {
          callback(new Error('密码至少 6 位'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    username: '',
    password: '',
    real_name: '',
    phone: '',
    email: '',
    dept_name: '',
    status: 'ACTIVE',
    role_ids: [],
  })
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    real_name: row.real_name || '',
    phone: row.phone || '',
    email: row.email || '',
    dept_name: row.dept_name || '',
    status: row.status,
    role_ids: (row.roles || []).map((r) => r.id),
  })
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  if (editingId.value === null) {
    await createUser({
      username: form.username,
      password: form.password,
      real_name: form.real_name || null,
      phone: form.phone || null,
      email: form.email || null,
      dept_name: form.dept_name || null,
      role_ids: form.role_ids,
    })
    ElMessage.success('用户已创建')
  } else {
    await updateUser(editingId.value, {
      real_name: form.real_name || null,
      phone: form.phone || null,
      email: form.email || null,
      dept_name: form.dept_name || null,
      status: form.status,
    })
    ElMessage.success('用户已更新')
  }
  dialogVisible.value = false
  void load()
}

// ---------------- 启停用 ----------------
async function toggleStatus(row: User) {
  const next = row.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
  const action = next === 'ACTIVE' ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(`确认${action}用户「${row.username}」？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  await updateUser(row.id, { status: next })
  ElMessage.success(`已${action}`)
  void load()
}

// ---------------- 重置密码 ----------------
const resetDialog = ref(false)
const resetTarget = ref<User | null>(null)
const resetForm = reactive({ password: '', confirm: '' })
const resetFormRef = ref<FormInstance>()
const resetRules: FormRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    {
      validator: (_rule, value, callback) => {
        if (value !== resetForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function openReset(row: User) {
  resetTarget.value = row
  resetForm.password = ''
  resetForm.confirm = ''
  resetDialog.value = true
}

async function submitReset() {
  const valid = await resetFormRef.value?.validate().catch(() => false)
  if (!valid || !resetTarget.value) {
    return
  }
  await resetUserPassword(resetTarget.value.id, { password: resetForm.password })
  ElMessage.success('密码已重置')
  resetDialog.value = false
}

// ---------------- 分配角色 ----------------
const roleDialog = ref(false)
const roleTarget = ref<User | null>(null)
const selectedRoleIds = ref<number[]>([])

async function openAssignRoles(row: User) {
  roleTarget.value = row
  selectedRoleIds.value = (row.roles || []).map((r) => r.id)
  roleDialog.value = true
}

async function submitRoles() {
  if (!roleTarget.value) {
    return
  }
  await assignUserRoles(roleTarget.value.id, { role_ids: selectedRoleIds.value })
  ElMessage.success('角色已更新')
  roleDialog.value = false
  void load()
}

// ---------------- 初始化 ----------------
onMounted(async () => {
  void load()
  try {
    roles.value = await listRoles()
  } catch {
    // 无角色查看权限时下拉为空（后端 403 已提示）
  }
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索用户名/姓名"
        clearable
        style="width: 240px"
        @keyup.enter="search"
        @clear="search"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button :icon="Refresh" @click="search">刷新</el-button>
      <div class="spacer" />
      <el-button v-if="hasPerm('user:create')" type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" min-width="110" />
      <el-table-column prop="real_name" label="姓名" min-width="100">
        <template #default="{ row }">{{ fmtText(row.real_name) }}</template>
      </el-table-column>
      <el-table-column prop="dept_name" label="部门" min-width="100">
        <template #default="{ row }">{{ fmtText(row.dept_name) }}</template>
      </el-table-column>
      <el-table-column label="角色" min-width="140">
        <template #default="{ row }">
          <el-tag v-if="row.is_superuser" type="danger" size="small">超管</el-tag>
          <el-tag
            v-for="r in row.roles || []"
            :key="r.id"
            size="small"
            style="margin-right: 4px"
          >{{ r.name }}</el-tag>
          <span v-if="!row.is_superuser && !(row.roles || []).length" class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'danger'" size="small">
            {{ row.status === 'ACTIVE' ? '正常' : row.status === 'LOCKED' ? '锁定' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" min-width="150">
        <template #default="{ row }">{{ fmtDateTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <template v-if="canManage">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openAssignRoles(row)">分配角色</el-button>
            <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
            <el-button
              v-if="!row.is_superuser"
              link
              :type="row.status === 'ACTIVE' ? 'danger' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'ACTIVE' ? '停用' : '启用' }}
            </el-button>
          </template>
          <span v-else class="muted">只读</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next, sizes"
      :page-sizes="[10, 20, 50, 100]"
      style="margin-top: 12px; justify-content: flex-end"
      @current-change="load"
      @size-change="search"
    />

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新增用户' : '编辑用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="editingId !== null" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="editingId !== null ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.dept_name" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_ids" multiple placeholder="选择角色" style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editingId !== null" label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="ACTIVE">正常</el-radio>
            <el-radio value="DISABLED">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetDialog" title="重置密码" width="420px">
      <p class="tip">将重置用户「{{ resetTarget?.username }}」的登录密码。</p>
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="90px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="resetForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialog = false">取消</el-button>
        <el-button type="primary" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色 -->
    <el-dialog v-model="roleDialog" title="分配角色" width="420px">
      <p class="tip">为用户「{{ roleTarget?.username }}」分配角色（可多选，保存后全量生效）。</p>
      <el-select v-model="selectedRoleIds" multiple placeholder="选择角色" style="width: 100%">
        <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <template #footer>
        <el-button @click="roleDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRoles">保存</el-button>
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
.tip {
  margin: 0 0 12px;
  color: #606266;
  font-size: 13px;
}
</style>
