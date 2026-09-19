import { computed, ref } from 'vue'

import type { components } from '@/api/schema'

export type CurrentUser = components['schemas']['CurrentUserOut']

const TOKEN_KEY = 'erp_token'
const USER_KEY = 'erp_user'

function readUser(): CurrentUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as CurrentUser
  } catch {
    return null
  }
}

const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
const user = ref<CurrentUser | null>(readUser())

const permissionSet = computed(() => new Set(user.value?.permissions || []))

export function useAuth() {
  const isAuthenticated = computed(() => Boolean(token.value))

  /** 是否拥有某权限码；超管视为拥有一切权限（后端 /auth/me 已返回全部权限码）。 */
  function hasPerm(code: string): boolean {
    if (user.value?.is_superuser) {
      return true
    }
    return permissionSet.value.has(code)
  }

  function hasAnyPerm(codes: string[]): boolean {
    if (user.value?.is_superuser) {
      return true
    }
    return codes.some((code) => permissionSet.value.has(code))
  }

  function setSession(accessToken: string, current: CurrentUser) {
    token.value = accessToken
    user.value = current
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(current))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isAuthenticated, hasPerm, hasAnyPerm, setSession, logout }
}
