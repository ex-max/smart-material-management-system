import { api } from '@/api/http'
import type { Page } from '@/api/master'
import type { components } from '@/api/schema'

// ---- 接口类型：全部由后端 OpenAPI 生成（npm run gen:api），不手写重复类型 ----
export type User = components['schemas']['UserOut']
export type UserCreate = components['schemas']['UserCreate']
export type UserUpdate = components['schemas']['UserUpdate']
export type AssignRolesIn = components['schemas']['AssignRolesIn']
export type ResetPasswordIn = components['schemas']['ResetPasswordIn']
export type Role = components['schemas']['RoleOut']
export type RoleCreate = components['schemas']['RoleCreate']
export type RoleUpdate = components['schemas']['RoleUpdate']
export type RolePermissionAssignIn = components['schemas']['RolePermissionAssignIn']
export type Permission = components['schemas']['PermissionOut']

// ---------------- 用户 ----------------
export function listUsers(params: Record<string, unknown> = {}) {
  return api.get<Page<User>>('/users', { page: 1, page_size: 20, ...params })
}
export function getUser(id: number) {
  return api.get<User>('/users/' + id)
}
export function createUser(payload: UserCreate) {
  return api.post<User>('/users', payload)
}
export function updateUser(id: number, payload: UserUpdate) {
  return api.put<User>('/users/' + id, payload)
}
export function assignUserRoles(id: number, payload: AssignRolesIn) {
  return api.post<User>('/users/' + id + '/roles', payload)
}
export function resetUserPassword(id: number, payload: ResetPasswordIn) {
  return api.post<User>('/users/' + id + '/reset-password', payload)
}

// ---------------- 角色 ----------------
export function listRoles() {
  return api.get<Role[]>('/roles')
}
export function getRole(id: number) {
  return api.get<Role>('/roles/' + id)
}
export function createRole(payload: RoleCreate) {
  return api.post<Role>('/roles', payload)
}
export function updateRole(id: number, payload: RoleUpdate) {
  return api.put<Role>('/roles/' + id, payload)
}
export function deleteRole(id: number) {
  return api.delete<null>('/roles/' + id)
}
export function saveRolePermissions(id: number, payload: RolePermissionAssignIn) {
  return api.put<number[]>('/roles/' + id + '/permissions', payload)
}
export function getRolePermissions(id: number) {
  return api.get<number[]>('/roles/' + id + '/permissions')
}

// ---------------- 权限 ----------------
export function listPermissions() {
  return api.get<Permission[]>('/permissions')
}
