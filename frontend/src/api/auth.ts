import { api } from '@/api/http'
import type { components } from '@/api/schema'

export type LoginResult = components['schemas']['LoginResult']
export type CurrentUser = components['schemas']['UserOut']

export function login(username: string, password: string) {
  return api.post<LoginResult>('/auth/login', { username, password })
}

export function fetchMe() {
  return api.get<CurrentUser>('/auth/me')
}
