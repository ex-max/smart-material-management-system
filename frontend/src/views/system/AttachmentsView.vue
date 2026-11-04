<script setup lang="ts">
import { Refresh, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { deleteAttachment, downloadAttachment, listAttachments, uploadAttachment, type Attachment } from '@/api/system'
import { useAuth } from '@/composables/useAuth'
import { fmtDateTime } from '@/utils/format'

const { hasPerm } = useAuth()
const canUpload = () => hasPerm('attachment:manage')

const rows = ref<Attachment[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const bizType = ref('')
const bizId = ref<string>('')

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (bizType.value.trim()) {
      params.biz_type = bizType.value.trim()
    }
    if (bizId.value.trim()) {
      params.biz_id = Number(bizId.value.trim())
    }
    const data = await listAttachments(params)
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
  bizType.value = ''
  bizId.value = ''
  page.value = 1
  void load()
}

function fmtSize(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-'
  }
  if (value < 1024) {
    return value + ' B'
  }
  if (value < 1024 * 1024) {
    return (value / 1024).toFixed(1) + ' KB'
  }
  return (value / (1024 * 1024)).toFixed(2) + ' MB'
}

function bizLabel(row: Attachment): string {
  if (row.biz_type && row.biz_id !== null && row.biz_id !== undefined) {
    return row.biz_type + ' #' + row.biz_id
  }
  return '-'
}

// ---------------- 上传 ----------------
const uploadVisible = ref(false)
const uploading = ref(false)
const progress = ref(0)
const uploadFormRef = ref<FormInstance>()
const uploadForm = reactive({
  file: undefined as File | undefined,
  biz_type: '',
  biz_id: undefined as number | undefined,
})
const inputRef = ref<HTMLInputElement>()

function openUpload() {
  uploadForm.file = undefined
  uploadForm.biz_type = ''
  uploadForm.biz_id = undefined
  progress.value = 0
  uploadVisible.value = true
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    uploadForm.file = file
  }
  if (inputRef.value) {
    inputRef.value.value = ''
  }
}

async function submitUpload() {
  if (!uploadForm.file) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  uploading.value = true
  progress.value = 0
  try {
    await uploadAttachment(uploadForm.file, uploadForm.biz_type || undefined, uploadForm.biz_id, (p) => {
      progress.value = p
    })
    ElMessage.success('上传成功')
    uploadVisible.value = false
    await load()
  } finally {
    uploading.value = false
  }
}

// ---------------- 下载 / 删除 ----------------
const downloading = ref<number | null>(null)

async function handleDownload(row: Attachment) {
  downloading.value = row.id
  try {
    await downloadAttachment(row.id, row.file_name)
  } finally {
    downloading.value = null
  }
}

async function handleDelete(row: Attachment) {
  try {
    await ElMessageBox.confirm('确认删除附件「' + row.file_name + '」？删除后列表不可见（文件本体保留，可审计）。', '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  await deleteAttachment(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <el-card>
    <template #header>
      <div class="att-header">
        <div>
          <span class="att-title">附件管理</span>
          <span class="att-desc">文件本体本地存储，数据库只存元数据</span>
        </div>
        <div>
          <el-button :icon="Refresh" @click="load">刷新</el-button>
          <el-button v-if="canUpload()" type="primary" :icon="UploadFilled" @click="openUpload">上传</el-button>
        </div>
      </div>
    </template>

    <div class="toolbar">
      <el-input v-model="bizType" placeholder="业务类型" clearable style="width: 180px" @keyup.enter="search" @clear="search" />
      <el-input v-model="bizId" placeholder="业务ID" clearable style="width: 130px" @keyup.enter="search" @clear="search" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
      <span class="total">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column prop="content_type" label="MIME" width="140" show-overflow-tooltip />
      <el-table-column label="关联业务" width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ bizLabel(row) }}</template>
      </el-table-column>
      <el-table-column prop="uploaded_by" label="上传人" width="100" />
      <el-table-column label="上传时间" width="170">
        <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :loading="downloading === row.id" @click="handleDownload(row)">下载</el-button>
          <el-button v-if="canUpload()" link type="danger" @click="handleDelete(row)">删除</el-button>
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

  <el-dialog v-model="uploadVisible" title="上传附件" width="520px" destroy-on-close>
    <el-form ref="uploadFormRef" :model="uploadForm" label-width="100px">
      <el-form-item label="文件" required>
        <input ref="inputRef" type="file" style="display: none" @change="onFileChange" />
        <el-button type="primary" @click="inputRef?.click()">选择文件</el-button>
        <span v-if="uploadForm.file" class="file-name">{{ uploadForm.file.name }}</span>
      </el-form-item>
      <el-form-item label="业务类型">
        <el-input v-model="uploadForm.biz_type" placeholder="可选；如 purchase_order" maxlength="32" />
      </el-form-item>
      <el-form-item label="业务ID">
        <el-input-number v-model="uploadForm.biz_id" :min="1" controls-position="right" style="width: 100%" placeholder="可选" />
      </el-form-item>
      <el-form-item v-if="uploading" label="进度">
        <el-progress :percentage="progress" :stroke-width="14" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="uploadVisible = false" :disabled="uploading">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.att-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.att-title {
  font-size: 16px;
  font-weight: 600;
}
.att-desc {
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
.file-name {
  margin-left: 12px;
  color: #606266;
}
</style>
