import { api, type ApiCallOptions } from '@/api/http'
import type { Page } from '@/api/master'
import type { components } from '@/api/schema'

// ---- 接口类型：全部由后端 OpenAPI 生成（npm run gen:api），不手写重复类型 ----
export type OperationLog = components['schemas']['OperationLogOut']
export type DictType = components['schemas']['DictTypeOut']
export type DictItem = components['schemas']['DictItemOut']
export type DictItemCreate = components['schemas']['DictItemCreate']
export type DictItemUpdate = components['schemas']['DictItemUpdate']
export type ScheduledTaskLog = components['schemas']['ScheduledTaskLogOut']
export type TaskLogFinish = components['schemas']['TaskLogFinish']
export type Attachment = components['schemas']['AttachmentOut']

type Params = Record<string, unknown>

// ---------------- 操作日志（只读） ----------------
export function listOperationLogs(params: Params = {}) {
  return api.get<Page<OperationLog>>('/operation-logs', { page: 1, page_size: 20, ...params })
}

// ---------------- 数据字典 ----------------
export function listDictTypes() {
  return api.get<DictType[]>('/dict-types')
}
export function lookupDict(dictType: string) {
  return api.get<DictItem[]>('/dicts/' + encodeURIComponent(dictType))
}
export function listDictItems(params: Params = {}) {
  return api.get<Page<DictItem>>('/dict-items', { page: 1, page_size: 20, ...params })
}
export function getDictItem(id: number) {
  return api.get<DictItem>('/dict-items/' + id)
}
export function createDictItem(payload: DictItemCreate) {
  return api.post<DictItem>('/dict-items', payload)
}
export function updateDictItem(id: number, payload: DictItemUpdate) {
  return api.put<DictItem>('/dict-items/' + id, payload)
}
export function deleteDictItem(id: number) {
  return api.delete<null>('/dict-items/' + id)
}

// ---------------- 定时任务日志 ----------------
export function listTaskLogs(params: Params = {}) {
  return api.get<Page<ScheduledTaskLog>>('/scheduled-task-logs', { page: 1, page_size: 20, ...params })
}
export function getTaskLog(id: number) {
  return api.get<ScheduledTaskLog>('/scheduled-task-logs/' + id)
}
export function finishTaskLog(id: number, payload: TaskLogFinish) {
  return api.post<ScheduledTaskLog>('/scheduled-task-logs/' + id + '/finish', payload)
}

// ---------------- 附件 ----------------
export function listAttachments(params: Params = {}) {
  return api.get<Page<Attachment>>('/attachments', { page: 1, page_size: 20, ...params })
}
export function getAttachment(id: number) {
  return api.get<Attachment>('/attachments/' + id)
}
/** multipart 上传；biz_type/biz_id 可选（不填为未绑定业务的通用附件）。 */
export function uploadAttachment(
  file: File,
  bizType: string | undefined,
  bizId: number | undefined,
  onProgress?: (percent: number) => void,
  options?: ApiCallOptions,
) {
  const form = new FormData()
  form.append('file', file)
  if (bizType) {
    form.append('biz_type', bizType)
  }
  if (bizId !== undefined && bizId !== null && !Number.isNaN(Number(bizId))) {
    form.append('biz_id', String(bizId))
  }
  return api.upload<Attachment>('/attachments', form, {
    ...options,
    onUploadProgress: onProgress
      ? (event) => {
          if (event.total) {
            onProgress(Math.round((event.loaded / event.total) * 100))
          }
        }
      : undefined,
  })
}
export function deleteAttachment(id: number) {
  return api.delete<null>('/attachments/' + id)
}
/** 下载附件：触发浏览器保存，返回 Promise 以便调用方提示。 */
export async function downloadAttachment(id: number, fallbackName: string): Promise<void> {
  const response = await api.download('/attachments/' + id + '/download')
  const disposition = String(response.headers['content-disposition'] || '')
  let name = fallbackName
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(disposition)
  if (match) {
    try {
      name = decodeURIComponent(match[1].replace(/^"|"$/g, ''))
    } catch {
      name = match[1]
    }
  }
  const url = URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
