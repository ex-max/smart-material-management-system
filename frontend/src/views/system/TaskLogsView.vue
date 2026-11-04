<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { finishTaskLog, listTaskLogs, type ScheduledTaskLog } from '@/api/system'
import { useAuth } from '@/composables/useAuth'
import { fmtDateTime } from '@/utils/format'
import { statusTag, type TagType } from '@/utils/status'

const { hasPerm } = useAuth()
const canManage = () => hasPerm('task:manage')

const rows = ref<ScheduledTaskLog[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const taskName = ref('')
const taskType = ref('')
const statusFilter = ref('')
const timeRange = ref<[Date, Date] | null>(null)

const TASK_STATUS: Record<string, { label: string; type: TagType }> = {
  RUNNING: { label: '运行中', type: 'warning' },
  SUCCESS: { label: '成功', type: 'success' },
  FAILED: { label: '失败', type: 'danger' },
  SKIPPED: { label: '跳过', type: 'info' },
}

const FINISHABLE: Record<string, { label: string; type: TagType }> = {
  SUCCESS: { label: '成功', type: 'success' },
  FAILED: { label: '失败', type: 'danger' },
  SKIPPED: { label: '跳过', type: 'info' },
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (taskName.value.trim()) {
      params.task_name = taskName.value.trim()
    }
    if (taskType.value.trim()) {
      params.task_type = taskType.value.trim()
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    if (timeRange.value) {
      params.start_time = timeRange.value[0].toISOString()
      params.end_time = timeRange.value[1].toISOString()
    }
    const data = await listTaskLogs(params)
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
  taskName.value = ''
  taskType.value = ''
  statusFilter.value = ''
  timeRange.value = null
  page.value = 1
  void load()
}

// ---------------- 详情 ----------------
const detailVisible = ref(false)
const detail = ref<ScheduledTaskLog | null>(null)

function fieldsOf(row: ScheduledTaskLog) {
  return [
    { label: '任务名', value: row.task_name },
    { label: '任务类型', value: row.task_type || '-' },
    { label: '状态', value: statusTag(row.status, TASK_STATUS).label },
    { label: '开始时间', value: fmtDateTime(row.started_at) },
    { label: '结束时间', value: fmtDateTime(row.finished_at) },
    { label: '耗时(ms)', value: row.duration_ms !== null && row.duration_ms !== undefined ? String(row.duration_ms) : '-' },
    { label: '影响行数', value: row.affected_rows !== null && row.affected_rows !== undefined ? String(row.affected_rows) : '-' },
    { label: '结果摘要', value: row.result_summary || '-' },
    { label: '错误详情', value: row.error_detail || '-' },
    { label: 'trace_id', value: row.trace_id || '-' },
  ]
}

// ---------------- 完成（收尾 RUNNING） ----------------
const finishVisible = ref(false)
const finishId = ref<number | null>(null)
const finishing = ref(false)
const finishFormRef = ref<FormInstance>()
const finishForm = reactive({
  status: 'SUCCESS',
  affected_rows: undefined as number | undefined,
  result_summary: '',
  error_detail: '',
})

function openFinish(row: ScheduledTaskLog) {
  finishId.value = row.id
  finishForm.status = 'SUCCESS'
  finishForm.affected_rows = undefined
  finishForm.result_summary = ''
  finishForm.error_detail = ''
  finishVisible.value = true
}

async function submitFinish() {
  if (finishId.value === null) {
    return
  }
  finishing.value = true
  try {
    await finishTaskLog(finishId.value, {
      status: finishForm.status as 'SUCCESS' | 'FAILED' | 'SKIPPED',
      affected_rows: finishForm.affected_rows,
      result_summary: finishForm.result_summary || null,
      error_detail: finishForm.error_detail || null,
    })
    ElMessage.success('已完成收尾')
    finishVisible.value = false
    await load()
  } finally {
    finishing.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-card>
    <template #header>
      <div class="task-header">
        <div>
          <span class="task-title">定时任务日志</span>
          <span class="task-desc">后台/定时任务执行记录（追加写）</span>
        </div>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </template>

    <div class="toolbar">
      <el-input v-model="taskName" placeholder="任务名" clearable style="width: 180px" @keyup.enter="search" @clear="search" />
      <el-input v-model="taskType" placeholder="任务类型" clearable style="width: 150px" @keyup.enter="search" @clear="search" />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 130px" @change="search">
        <el-option v-for="(meta, key) in TASK_STATUS" :key="key" :label="meta.label" :value="key" />
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
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="task_name" label="任务名" min-width="160" show-overflow-tooltip />
      <el-table-column prop="task_type" label="任务类型" width="130" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status, TASK_STATUS).type" size="small">
            {{ statusTag(row.status, TASK_STATUS).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="170">
        <template #default="{ row }">{{ fmtDateTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="170">
        <template #default="{ row }">{{ fmtDateTime(row.finished_at) }}</template>
      </el-table-column>
      <el-table-column prop="duration_ms" label="耗时(ms)" width="100" />
      <el-table-column prop="affected_rows" label="影响行数" width="100" />
      <el-table-column prop="result_summary" label="结果摘要" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="detail = row; detailVisible = true">详情</el-button>
          <el-button
            v-if="row.status === 'RUNNING' && canManage()"
            link
            type="warning"
            @click="openFinish(row)"
          >
            完成
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

  <el-dialog v-model="detailVisible" title="任务日志详情" width="640px">
    <el-descriptions v-if="detail" :column="1" border size="small">
      <el-descriptions-item v-for="field in fieldsOf(detail)" :key="field.label" :label="field.label" label-width="110px">
        <span style="white-space: pre-wrap">{{ field.value }}</span>
      </el-descriptions-item>
    </el-descriptions>
  </el-dialog>

  <el-dialog v-model="finishVisible" title="任务收尾" width="520px" destroy-on-close>
    <el-form ref="finishFormRef" :model="finishForm" label-width="100px">
      <el-form-item label="结果" required>
        <el-radio-group v-model="finishForm.status">
          <el-radio-button v-for="(meta, key) in FINISHABLE" :key="key" :value="key">{{ meta.label }}</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="影响行数">
        <el-input-number v-model="finishForm.affected_rows" :min="0" controls-position="right" style="width: 100%" />
      </el-form-item>
      <el-form-item label="结果摘要">
        <el-input v-model="finishForm.result_summary" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
      <el-form-item label="错误详情">
        <el-input v-model="finishForm.error_detail" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="finishVisible = false">取消</el-button>
      <el-button type="primary" :loading="finishing" @click="submitFinish">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.task-title {
  font-size: 16px;
  font-weight: 600;
}
.task-desc {
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
