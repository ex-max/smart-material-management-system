<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import { listPermissions, type Permission } from '@/api/admin'

const items = ref<Permission[]>([])
const loading = ref(false)

/** 前端按 code 前缀分组（user:/role:/material:/purchase:/inventory:/forecast:/replenishment:/operation:/dict:/task:/attachment:）。 */
function groupPermissions(list: Permission[]) {
  const groups = new Map<string, Permission[]>()
  for (const p of list) {
    const prefix = p.code.includes(':') ? p.code.split(':')[0] : 'other'
    const arr = groups.get(prefix) || []
    arr.push(p)
    groups.set(prefix, arr)
  }
  const order = [
    'user', 'role', 'material', 'purchase', 'inventory', 'forecast', 'replenishment', 'operation', 'dict', 'task', 'attachment', 'other',
  ]
  return [...groups.entries()]
    .sort((a, b) => (order.indexOf(a[0]) - order.indexOf(b[0])) || (a[0] < b[0] ? -1 : 1))
    .map(([key, list]) => ({ key, list }))
}

const groups = ref(groupPermissions([]))

async function load() {
  loading.value = true
  try {
    items.value = await listPermissions()
    groups.value = groupPermissions(items.value)
  } finally {
    loading.value = false
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
      <span class="tip">权限码为系统内置（服务端鉴权单一事实源），此处仅只读展示。</span>
    </div>

    <el-card v-for="group in groups" :key="group.key" shadow="never" class="perm-card">
      <template #header>
        <div class="card-header">
          <el-tag size="small" type="primary">{{ group.key }}</el-tag>
          <span class="count">{{ group.list.length }} 项</span>
        </div>
      </template>
      <el-table v-loading="loading" :data="group.list" size="small" border>
        <el-table-column prop="code" label="权限码" min-width="200" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="type" label="类型" width="90" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.tip {
  color: #909399;
  font-size: 13px;
}
.perm-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.count {
  color: #909399;
  font-size: 12px;
}
</style>
