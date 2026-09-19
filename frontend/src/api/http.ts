import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

import { useAuth } from '@/composables/useAuth'
import router from '@/router'

export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  trace_id: string
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 20000,
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const { token } = useAuth()
  if (token.value) {
    config.headers.Authorization = `Bearer ${token.value}`
  }
  return config
})

http.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ApiEnvelope<unknown>>) => {
    const status = error.response?.status
    const body = error.response?.data
    const message = body?.message || error.message || '网络错误'
    if (status === 401) {
      useAuth().logout()
      void router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    } else {
      ElMessage.error(message)
    }
    return Promise.reject(new Error(message))
  },
)

async function unwrap<T>(promise: Promise<AxiosResponse<ApiEnvelope<T>>>): Promise<T> {
  const response = await promise
  const body = response.data
  if (body.code !== 0) {
    ElMessage.error(body.message || '请求失败')
    throw new Error(body.message)
  }
  return body.data
}

export const api = {
  get: <T>(url: string, params?: Record<string, unknown>) => unwrap<T>(http.get(url, { params })),
  post: <T>(url: string, data?: unknown) => unwrap<T>(http.post(url, data)),
  put: <T>(url: string, data?: unknown) => unwrap<T>(http.put(url, data)),
  delete: <T>(url: string) => unwrap<T>(http.delete(url)),
}

export default http
