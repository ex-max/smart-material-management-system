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

/** 单次请求选项：silent=true 时拦截器不弹全局错误提示（用于概览页对 403 静默降级）。 */
export interface ApiCallOptions {
  silent?: boolean
}

declare module 'axios' {
  export interface AxiosRequestConfig {
    silent?: boolean
  }
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
    } else if (!error.config?.silent) {
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
  get: <T>(url: string, params?: Record<string, unknown>, options?: ApiCallOptions) =>
    unwrap<T>(http.get(url, { params, ...options })),
  post: <T>(url: string, data?: unknown, options?: ApiCallOptions) =>
    unwrap<T>(http.post(url, data, options)),
  put: <T>(url: string, data?: unknown, options?: ApiCallOptions) =>
    unwrap<T>(http.put(url, data, options)),
  delete: <T>(url: string, options?: ApiCallOptions) => unwrap<T>(http.delete(url, options)),
}

export default http
