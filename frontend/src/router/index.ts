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
      redirect: { name: 'replenishment' },
      children: [
        // ---- 主数据 ----
        {
          path: 'master/materials',
          name: 'master-materials',
          component: masterView,
          meta: { title: '物资档案', entity: 'materials' },
        },
        {
          path: 'master/categories',
          name: 'master-categories',
          component: masterView,
          meta: { title: '物资分类', entity: 'categories' },
        },
        {
          path: 'master/units',
          name: 'master-units',
          component: masterView,
          meta: { title: '计量单位', entity: 'units' },
        },
        {
          path: 'master/warehouses',
          name: 'master-warehouses',
          component: masterView,
          meta: { title: '仓库', entity: 'warehouses' },
        },
        {
          path: 'master/locations',
          name: 'master-locations',
          component: masterView,
          meta: { title: '库位', entity: 'locations' },
        },
        {
          path: 'master/suppliers',
          name: 'master-suppliers',
          component: masterView,
          meta: { title: '供应商', entity: 'suppliers' },
        },
        // ---- 采购 ----
        {
          path: 'purchase/requisitions',
          name: 'purchase-requisitions',
          component: () => import('@/views/purchase/PurchaseRequisitionView.vue'),
          meta: { title: '请购单' },
        },
        {
          path: 'purchase/orders',
          name: 'purchase-orders',
          component: () => import('@/views/purchase/PurchaseOrderView.vue'),
          meta: { title: '采购订单' },
        },
        {
          path: 'purchase/deliveries',
          name: 'purchase-deliveries',
          component: () => import('@/views/purchase/SupplierDeliveryView.vue'),
          meta: { title: '到货/验收单' },
        },
        // ---- 库存 ----
        {
          path: 'inventory/query',
          name: 'inventory-query',
          component: () => import('@/views/inventory/InventoryQueryView.vue'),
          meta: { title: '库存查询' },
        },
        {
          path: 'inventory/inbound',
          name: 'inventory-inbound',
          component: () => import('@/views/inventory/InboundOrderView.vue'),
          meta: { title: '入库单' },
        },
        {
          path: 'inventory/outbound',
          name: 'inventory-outbound',
          component: () => import('@/views/inventory/OutboundOrderView.vue'),
          meta: { title: '出库单' },
        },
        {
          path: 'inventory/transfer',
          name: 'inventory-transfer',
          component: () => import('@/views/inventory/TransferOrderView.vue'),
          meta: { title: '调拨单' },
        },
        {
          path: 'inventory/stocktake',
          name: 'inventory-stocktake',
          component: () => import('@/views/inventory/StocktakeOrderView.vue'),
          meta: { title: '盘点单' },
        },
        {
          path: 'inventory/alerts',
          name: 'inventory-alerts',
          component: () => import('@/views/inventory/StockAlertView.vue'),
          meta: { title: '库存预警' },
        },
        // ---- 决策 ----
        {
          path: 'replenishment',
          name: 'replenishment',
          component: () => import('@/views/ReplenishmentView.vue'),
          meta: { title: '补货决策' },
        },
        {
          path: 'home',
          name: 'home',
          component: () => import('@/views/HomeView.vue'),
          meta: { title: '概览' },
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
  const { isAuthenticated } = useAuth()
  if (!to.meta.public && !isAuthenticated.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && isAuthenticated.value) {
    return { name: 'replenishment' }
  }
  return true
})

export default router
