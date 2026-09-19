<script setup lang="ts">
import { HomeFilled, SwitchButton, TrendCharts } from '@element-plus/icons-vue'
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
        <el-menu-item index="replenishment" :route="{ name: 'replenishment' }">
          <el-icon><TrendCharts /></el-icon>
          <span>补货决策</span>
        </el-menu-item>
        <el-menu-item index="home" :route="{ name: 'home' }">
          <el-icon><HomeFilled /></el-icon>
          <span>概览</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">补货决策闭环</span>
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
.menu :deep(.el-menu-item) {
  color: #c0c4cc;
}
.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #22344a;
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
