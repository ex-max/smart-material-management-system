<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listOperationLogs, type OperationLog } from '@/api/system'
import { fmtDateTime } from '@/utils/format'
import { statusTag, type TagType } from '@/utils/status'

const rows = ref<OperationLog[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const userKw = ref('')
const moduleKw = ref('')
const actionKw = ref('')
const result = ref('')
const timeRange = ref<[Date, Date] | null>(null)

const RESULT_META: Record<string, { label: string; type: TagType }> = {
  SUCCESS: { label: '成功', type: 'success' },
  FAIL: { label: '失败', type: 'danger' },
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (userKw.value.trim()) {
      params.user_id = Number(userKw.value.trim())
    }
    if (moduleKw.value.trim()) {
      params.module = moduleKw.value.trim()
    }
    if (actionKw.value.trim()) {
      params.action = actionKw.value.trim()
    }
    if (result.value) {
      params.result = result.value
    }
    if (timeRange.value) {
      params.start_time = timeRange.value[0].toISOString()
      params.end_time = timeRange.value[1].toISOString()
    }
    const data = await listOperationLogs(params)
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

function reset() {
  userKw.value = ''
  moduleKw.value = ''
  actionKw.value = ''
  result.value = ''
  timeRange.value = null
  page.value = 1
  void load()
}

function username(row: OperationLog): string {
  return row.username || (row.user_id !== null && row.user_id !== undefined ? '#' + row.user_id : '-')
}

onMounted(load)
</script>

<template>
  <el-card>
    <template #header>
      <div class="log-header">
        <span class="log-title">操作日志</span>
        <span class="log-desc">系统请求审计记录（只读）</span>
      </div>
    </template>

    <div class="toolbar">
      <el-input v-model="userKw" placeholder="用户ID" clearable style="width: 130px" @keyup.enter="search" @clear="search" />
      <el-input v-model="moduleKw" placeholder="模块" clearable style="width: 150px" @keyup.enter="search" @clear="search" />
      <el-input v-model="actionKw" placeholder="动作" clearable style="width: 150px" @keyup.enter="search" @clear="search" />
      <el-select v-model="result" placeholder="结果" clearable style="width: 120px" @change="search">
        <el-option label="成功" value="SUCCESS" />
        <el-option label="失败" value="FAIL" />
      </el-select>
      <el-date-picker
        v-model="timeRange"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        style="width: 360px"
        @change="search"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
      <span class="total">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="操作人" width="130" show-overflow-tooltip>
        <template #default="{ row }">{{ username(row) }}</template>
      </el-table-column>
      <el-table-column prop="module" label="模块" width="130" show-overflow-tooltip />
      <el-table-column prop="action" label="动作" width="170" show-overflow-tooltip />
      <el-table-column prop="method" label="方法" width="80" />
      <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.result, RESULT_META).type" size="small">
            {{ statusTag(row.result, RESULT_META).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="duration_ms" label="耗时(ms)" width="100" />
      <el-table-column prop="ip" label="IP" width="130" show-overflow-tooltip />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
      </el-table-column>
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
</template>

<style scoped>
.log-header {
  display: flex;
  align-items: center;
}
.log-title {
  font-size: 16px;
  font-weight: 600;
}
.log-desc {
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