<script setup lang="ts">
import {
  Box,
  Coin,
  DataLine,
  Document,
  Goods,
  Grid,
  HomeFilled,
  List,
  Location,
  Menu as MenuIcon,
  OfficeBuilding,
  ShoppingCart,
  SwitchButton,
  Tickets,
  TrendCharts,
  User,
  Warning,
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { user, logout } = useAuth()

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
  } catch {
    return
  }
  logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">智能物资管理</div>
      <el-menu :default-active="String($route.name)" router class="menu">
        <el-sub-menu index="master">
          <template #title>
            <el-icon><Grid /></el-icon>
            <span>主数据</span>
          </template>
          <el-menu-item index="master-materials" :route="{ name: 'master-materials' }">
            <el-icon><Goods /></el-icon><span>物资档案</span>
          </el-menu-item>
          <el-menu-item index="master-categories" :route="{ name: 'master-categories' }">
            <el-icon><MenuIcon /></el-icon><span>物资分类</span>
          </el-menu-item>
          <el-menu-item index="master-units" :route="{ name: 'master-units' }">
            <el-icon><Coin /></el-icon><span>计量单位</span>
          </el-menu-item>
          <el-menu-item index="master-warehouses" :route="{ name: 'master-warehouses' }">
            <el-icon><OfficeBuilding /></el-icon><span>仓库</span>
          </el-menu-item>
          <el-menu-item index="master-locations" :route="{ name: 'master-locations' }">
            <el-icon><Location /></el-icon><span>库位</span>
          </el-menu-item>
          <el-menu-item index="master-suppliers" :route="{ name: 'master-suppliers' }">
            <el-icon><User /></el-icon><span>供应商</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="purchase">
          <template #title>
            <el-icon><ShoppingCart /></el-icon>
            <span>采购管理</span>
          </template>
          <el-menu-item index="purchase-requisitions" :route="{ name: 'purchase-requisitions' }">
            <el-icon><Tickets /></el-icon><span>请购单</span>
          </el-menu-item>
          <el-menu-item index="purchase-orders" :route="{ name: 'purchase-orders' }">
            <el-icon><Document /></el-icon><span>采购订单</span>
          </el-menu-item>
          <el-menu-item index="purchase-deliveries" :route="{ name: 'purchase-deliveries' }">
            <el-icon><List /></el-icon><span>到货/验收单</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="inventory">
          <template #title>
            <el-icon><Box /></el-icon>
            <span>库存管理</span>
          </template>
          <el-menu-item index="inventory-query" :route="{ name: 'inventory-query' }">
            <el-icon><DataLine /></el-icon><span>库存查询</span>
          </el-menu-item>
          <el-menu-item index="inventory-inbound" :route="{ name: 'inventory-inbound' }">
            <el-icon><Box /></el-icon><span>入库单</span>
          </el-menu-item>
          <el-menu-item index="inventory-outbound" :route="{ name: 'inventory-outbound' }">
            <el-icon><Box /></el-icon><span>出库单</span>
          </el-menu-item>
          <el-menu-item index="inventory-transfer" :route="{ name: 'inventory-transfer' }">
            <el-icon><Box /></el-icon><span>调拨单</span>
          </el-menu-item>
          <el-menu-item index="inventory-stocktake" :route="{ name: 'inventory-stocktake' }">
            <el-icon><Box /></el-icon><span>盘点单</span>
          </el-menu-item>
          <el-menu-item index="inventory-alerts" :route="{ name: 'inventory-alerts' }">
            <el-icon><Warning /></el-icon><span>库存预警</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="replenishment" :route="{ name: 'replenishment' }">
          <el-icon><TrendCharts /></el-icon><span>补货决策</span>
        </el-menu-item>
        <el-menu-item index="home" :route="{ name: 'home' }">
          <el-icon><HomeFilled /></el-icon><span>概览</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ $route.meta.title || '智能物资管理系统' }}</span>
        <div class="user">
          <span class="username">{{ user?.real_name || user?.username }}</span>
          <el-button link type="primary" :icon="SwitchButton" @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background: #1f2d3d;
  color: #fff;
  overflow-y: auto;
}
.brand {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  background: #16222f;
}
.menu {
  border-right: none;
  background: #1f2d3d;
}
.menu :deep(.el-menu-item),
.menu :deep(.el-sub-menu__title) {
  color: #c0c4cc;
}
.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #22344a;
}
.menu :deep(.el-menu) {
  background: #182533;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.user {
  display: flex;
  align-items: center;
  gap: 12px;
}
.username {
  color: #606266;
}
</style>
