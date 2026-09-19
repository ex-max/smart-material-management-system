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
