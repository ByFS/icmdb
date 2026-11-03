<template>
  <el-container v-if="$route.path === '/login'" class="bare">
    <router-view />
  </el-container>
  <el-container v-else class="layout">
    <el-aside :width="collapsed ? '64px' : '256px'" class="aside">
      <div class="brand" title="回到首页" @click="$router.push('/dashboard')">
        <svg class="mark" viewBox="0 0 16 16" aria-hidden="true">
          <rect x="1" y="2" width="14" height="3" rx="1" />
          <rect x="1" y="6.5" width="14" height="3" rx="1" />
          <rect x="1" y="11" width="14" height="3" rx="1" />
        </svg>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-name">iCMDB</div>
          <div class="brand-sub">硬件资产台账</div>
        </div>
      </div>
      <el-menu
        router
        :default-active="$route.path"
        class="menu"
        :collapse="collapsed"
        :collapse-transition="false"
      >
        <div v-if="!collapsed" class="nav-label">总览</div>
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>仪表盘</template>
        </el-menu-item>
        <el-menu-item index="/devices">
          <el-icon><Monitor /></el-icon>
          <template #title>资产列表</template>
        </el-menu-item>
        <el-menu-item index="/conflicts">
          <el-icon><EditPen /></el-icon>
          <template #title>
            <span>冲突裁决</span>
            <span v-if="pendingCount && !collapsed" class="pending-count">
              {{ pendingCount > 99 ? '99+' : pendingCount }}
            </span>
          </template>
        </el-menu-item>
        <el-menu-item v-if="role === 'admin'" index="/scan">
          <el-icon><Search /></el-icon>
          <template #title>网段扫描</template>
        </el-menu-item>
        <div v-if="!collapsed" class="nav-label nav-label-space">管理</div>
        <el-menu-item v-if="role === 'admin'" index="/users">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
        <el-menu-item v-if="role === 'admin'" index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
        <el-menu-item v-if="role === 'admin'" index="/audit-logs">
          <el-icon><Tickets /></el-icon>
          <template #title>操作日志</template>
        </el-menu-item>
      </el-menu>
      <div class="user">
        <span class="username">{{ username }}</span>
        <el-button link @click="openChangePassword">修改密码</el-button>
        <el-button link @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>

    <el-dialog v-model="pwdVisible" title="修改密码" width="400px">
      <el-form label-width="80px">
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.old" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" @click="changePassword">确认修改</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style>
/* Global reset: remove the browser's default 8px body margin (login gradient stays flush, main layout fills) */
body {
  margin: 0;
}
</style>

<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { Monitor, EditPen, Odometer, Search, Setting, Tickets, User } from '@element-plus/icons-vue'
import { api } from './api'

const route = useRoute()
const pendingCount = ref(0)
const username = ref('')
const role = ref('viewer')
const collapsed = ref(false)

// Fold the sidebar into an icon rail below 900px (phone and narrow windows)
const narrow = window.matchMedia('(max-width: 900px)')
function syncCollapsed() {
  collapsed.value = narrow.matches
}

syncCollapsed()
narrow.addEventListener('change', syncCollapsed)

// Pending count badge: refreshed on app entry and page switch (ConflictResolve calls loadPendingCount after a resolve is submitted)
async function loadPendingCount() {
  try {
    const res = await api.dashboard()
    pendingCount.value = res.pending_changes
  } catch {
    // Fail silently, page stays usable
  }
}

// Currently signed-in user and role; silent when not signed in
async function loadUsername() {
  try {
    const res = await api.me()
    username.value = res.username
    role.value = res.role
  } catch {
    // Fail silently
  }
}

async function logout() {
  try {
    await api.logout()
  } finally {
    window.location.href = '/login'
  }
}

// Change own password (available to all roles)
const pwdVisible = ref(false)
const pwdForm = ref({ old: '', new: '', confirm: '' })

function openChangePassword() {
  pwdForm.value = { old: '', new: '', confirm: '' }
  pwdVisible.value = true
}

async function changePassword() {
  if (!pwdForm.value.old || !pwdForm.value.new) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (pwdForm.value.new !== pwdForm.value.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  try {
    await api.changePassword(pwdForm.value.old, pwdForm.value.new)
    pwdVisible.value = false
    ElMessage.success('密码已修改')
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

watch(() => route.path, loadPendingCount)
loadPendingCount()
loadUsername()
provide('refreshPendingCount', loadPendingCount)
provide('userRole', role)
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.aside {
  position: relative;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 0.15s ease;
}

/* Product mark: a drawn rack of three bars, the hardware the product inventories */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px 16px;
  cursor: pointer;
}

.mark {
  width: 22px;
  height: 22px;
  fill: var(--accent);
  flex-shrink: 0;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  line-height: 20px;
}

.brand-sub {
  font-size: 12px;
  color: var(--muted);
  line-height: 16px;
}

.menu {
  border-right: none;
  flex: 1;
}

/* Fixed-width icon box so every menu label starts at the same x */
.menu :deep(.el-menu-item .el-icon) {
  width: 16px;
  font-size: 16px;
  margin-right: 8px;
  flex-shrink: 0;
}

/* Grey sentence-case group labels, air above the first */
.nav-label {
  font-size: 12px;
  color: var(--muted);
  padding: 8px 16px 6px;
  letter-spacing: 0;
}

.nav-label-space {
  margin-top: 22px;
}

/* The one hue on the screen: the pending-count signal in the chrome */
.pending-count {
  margin-left: 6px;
  background: var(--hue);
  color: #ffffff;
  border-radius: 9px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 18px;
  height: 18px;
  flex-shrink: 0;
}

.main {
  background: var(--ground);
  padding: 32px 32px 48px;
}

.bare {
  min-height: 100vh;
  display: block;
}

.user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--rule);
}

.username {
  color: var(--muted);
  font-size: 13px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
