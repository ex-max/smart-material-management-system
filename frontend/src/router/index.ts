import { createRouter, createWebHistory } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const masterView = () => import('@/views/master/MasterDataView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: { name: 'home' },
      children: [
        // ---- 概览（所有登录用户可见） ----
        {
          path: 'home',
          name: 'home',
          component: () => import('@/views/HomeView.vue'),
          meta: { title: '概览' },
        },
        // ---- 主数据 ----
        {
          path: 'master/materials',
          name: 'master-materials',
          component: masterView,
          meta: { title: '物资档案', entity: 'materials', permission: 'material:view' },
        },
        {
          path: 'master/categories',
          name: 'master-categories',
          component: masterView,
          meta: { title: '物资分类', entity: 'categories', permission: 'material:view' },
        },
        {
          path: 'master/units',
          name: 'master-units',
          component: masterView,
          meta: { title: '计量单位', entity: 'units', permission: 'material:view' },
        },
        {
          path: 'master/warehouses',
          name: 'master-warehouses',
          component: masterView,
          meta: { title: '仓库', entity: 'warehouses', permission: 'material:view' },
        },
        {
          path: 'master/locations',
          name: 'master-locations',
          component: masterView,
          meta: { title: '库位', entity: 'locations', permission: 'material:view' },
        },
        {
          path: 'master/suppliers',
          name: 'master-suppliers',
          component: masterView,
          meta: { title: '供应商', entity: 'suppliers', permission: 'material:view' },
        },
        // ---- 采购 ----
        {
          path: 'purchase/requisitions',
          name: 'purchase-requisitions',
          component: () => import('@/views/purchase/PurchaseRequisitionView.vue'),
          meta: { title: '请购单', permission: 'purchase:view' },
        },
        {
          path: 'purchase/orders',
          name: 'purchase-orders',
          component: () => import('@/views/purchase/PurchaseOrderView.vue'),
          meta: { title: '采购订单', permission: 'purchase:view' },
        },
        {
          path: 'purchase/deliveries',
          name: 'purchase-deliveries',
          component: () => import('@/views/purchase/SupplierDeliveryView.vue'),
          meta: { title: '到货/验收单', permission: 'purchase:view' },
        },
        // ---- 库存 ----
        {
          path: 'inventory/query',
          name: 'inventory-query',
          component: () => import('@/views/inventory/InventoryQueryView.vue'),
          meta: { title: '库存查询', permission: 'inventory:view' },
        },
        {
          path: 'inventory/inbound',
          name: 'inventory-inbound',
          component: () => import('@/views/inventory/InboundOrderView.vue'),
          meta: { title: '入库单', permission: 'inventory:view' },
        },
        {
          path: 'inventory/outbound',
          name: 'inventory-outbound',
          component: () => import('@/views/inventory/OutboundOrderView.vue'),
          meta: { title: '出库单', permission: 'inventory:view' },
        },
        {
          path: 'inventory/transfer',
          name: 'inventory-transfer',
          component: () => import('@/views/inventory/TransferOrderView.vue'),
          meta: { title: '调拨单', permission: 'inventory:view' },
        },
        {
          path: 'inventory/stocktake',
          name: 'inventory-stocktake',
          component: () => import('@/views/inventory/StocktakeOrderView.vue'),
          meta: { title: '盘点单', permission: 'inventory:view' },
        },
        {
          path: 'inventory/alerts',
          name: 'inventory-alerts',
          component: () => import('@/views/inventory/StockAlertView.vue'),
          meta: { title: '库存预警', permission: 'inventory:view' },
        },
        // ---- 决策 ----
        {
          path: 'forecast',
          name: 'forecast',
          component: () => import('@/views/ForecastView.vue'),
          meta: { title: '预测曲线', permission: 'forecast:view' },
        },
        {
          path: 'replenishment',
          name: 'replenishment',
          component: () => import('@/views/ReplenishmentView.vue'),
          meta: { title: '补货决策', permission: 'replenishment:view' },
        },
        // ---- 系统管理 ----
        {
          path: 'system/operation-logs',
          name: 'system-operation-logs',
          component: () => import('@/views/system/OperationLogsView.vue'),
          meta: { title: '操作日志', permission: 'operation:view' },
        },
        {
          path: 'system/dicts',
          name: 'system-dicts',
          component: () => import('@/views/system/DictView.vue'),
          meta: { title: '数据字典', permission: 'dict:view' },
        },
        {
          path: 'system/tasks',
          name: 'system-tasks',
          component: () => import('@/views/system/TaskLogsView.vue'),
          meta: { title: '定时任务', permission: 'task:view' },
        },
        {
          path: 'system/attachments',
          name: 'system-attachments',
          component: () => import('@/views/system/AttachmentsView.vue'),
          meta: { title: '附件管理', permission: 'attachment:view' },
        },
        // ---- 权限管理（P3 RBAC） ----
        {
          path: 'admin/users',
          name: 'admin-users',
          component: () => import('@/views/admin/UserManageView.vue'),
          meta: { title: '用户管理', permission: 'user:view' },
        },
        {
          path: 'admin/roles',
          name: 'admin-roles',
          component: () => import('@/views/admin/RoleManageView.vue'),
          meta: { title: '角色管理', permission: 'role:view' },
        },
        {
          path: 'admin/permissions',
          name: 'admin-permissions',
          component: () => import('@/views/admin/PermissionManageView.vue'),
          meta: { title: '权限管理', permission: 'role:view' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach((to) => {
  const { isAuthenticated, hasPerm } = useAuth()
  if (!to.meta.public && !isAuthenticated.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && isAuthenticated.value) {
    return { name: 'home' }
  }
  // 路由级权限校验：无权限跳回概览（菜单已按权限隐藏，这里兜底直接访问）
  const permission = to.meta.permission as string | undefined
  if (permission && isAuthenticated.value && !hasPerm(permission)) {
    return { name: 'home' }
  }
  return true
})

export default router
