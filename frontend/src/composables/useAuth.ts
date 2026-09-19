import { computed, ref } from 'vue'

import type { components } from '@/api/schema'

export type CurrentUser = components['schemas']['UserOut']

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

export function useAuth() {
  const isAuthenticated = computed(() => Boolean(token.value))

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

  return { token, user, isAuthenticated, setSession, logout }
}
