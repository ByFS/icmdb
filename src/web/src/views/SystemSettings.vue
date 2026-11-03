<template>
  <div>
    <el-card class="card" v-loading="loading">
      <template #header>
        <div class="header">
          <span>系统设置</span>
          <span v-if="isAdmin" class="hint" :class="{ failed: saveState === 'failed' }">
            {{ saveHint }}
          </span>
        </div>
      </template>
      <el-form label-width="160px" style="max-width: 520px" @submit.prevent>
        <!-- 无保存按钮: 数字输入防抖自动保存, 开关改完立即保存 -->
        <el-form-item label="疑似下线阈值">
          <el-input-number
            v-if="isAdmin"
            v-model="hours"
            :min="1"
            :max="8760"
            :step="1"
            controls-position="right"
            @change="scheduleSave()"
          />
          <span v-else class="value">{{ hours }}</span>
          <span class="unit">小时</span>
        </el-form-item>
        <el-form-item label="API 密钥">
          <el-switch v-if="isAdmin" v-model="apiKeyEnabled" @change="scheduleSave(0)" />
          <span v-else class="value">{{ apiKeyEnabled ? '已开启' : '已关闭' }}</span>
        </el-form-item>
        <el-form-item v-if="!isAdmin">
          <span class="hint">仅管理员可修改</span>
        </el-form-item>
      </el-form>
      <div class="desc">
        超过该时长未推送数据的设备将被标记为<span class="value">疑似下线</span>,
        数据不自动删除;重新推送即恢复活跃
      </div>
      <div class="desc">
        开启后采集器推送必须携带有效密钥(请求头 X-API-Key),否则返回 401
      </div>
    </el-card>

    <el-card v-if="isAdmin && apiKeyEnabled" class="card" v-loading="keysLoading">
      <template #header>
        <div class="header">
          <span>API 密钥</span>
          <el-button type="primary" size="small" @click="openCreate">新建密钥</el-button>
        </div>
      </template>
      <el-table :data="keys" border>
        <el-table-column resizable prop="name" label="名称" min-width="140" show-overflow-tooltip/>
        <el-table-column resizable prop="key" label="密钥" min-width="320">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
            <el-button link type="primary" size="small" @click="copyKey(row)">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column resizable prop="created_at" label="创建时间" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column resizable prop="last_used_at" label="最后使用" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.last_used_at ? fmt(row.last_used_at) : '从未使用' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="revoke(row)">吊销</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="desc">
        密钥用于采集器推送与只读 API 访问;吊销后使用该密钥的请求立即返回 401
      </div>
    </el-card>

    <el-dialog v-model="createVisible" title="新建密钥" width="400px">
      <el-input
        v-model="newName"
        placeholder="密钥名称, 如 iagent-prod"
        maxlength="64"
        @keyup.enter="create"
      />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, ApiKey } from '../api'

const userRole = inject('userRole', ref('viewer'))
const isAdmin = computed(() => userRole.value === 'admin')

const hours = ref(24)
const apiKeyEnabled = ref(false)
const loading = ref(false)

// Last values confirmed by the server: reverted edits are skipped, no redundant writes
const savedHours = ref(24)
const savedKeyEnabled = ref(false)
const saveState = ref<'idle' | 'saving' | 'saved' | 'failed'>('idle')
const saveHint = computed(() => {
  switch (saveState.value) {
    case 'saving':
      return '保存中…'
    case 'saved':
      return '已保存'
    case 'failed':
      return '保存失败'
    default:
      return '修改后自动保存'
  }
})

// Auto-save: number edits are debounced, switch flips save right away; requests are serialized so the latest values always win
let saveTimer: ReturnType<typeof setTimeout> | undefined
let saving = false
let queued = false

// API key management (shown in this page while the feature is on)
const keys = ref<ApiKey[]>([])
const keysLoading = ref(false)
const createVisible = ref(false)
const newName = ref('')

onMounted(async () => {
  loading.value = true
  try {
    await loadSettings()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
})

// Show the key list as soon as the feature is switched on
watch(apiKeyEnabled, (on) => {
  if (on) {
    void fetchKeys()
  } else {
    keys.value = []
  }
})

async function loadSettings() {
  const s = await api.getSystemSettings()
  hours.value = s.offline_threshold_hours
  savedHours.value = s.offline_threshold_hours
  apiKeyEnabled.value = s.api_key_enabled
  savedKeyEnabled.value = s.api_key_enabled
}

function scheduleSave(delay = 500) {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => void save(), delay)
}

// The API requires offline_threshold_hours, both fields ride along on every save; the backend keeps whichever one did not change
async function save() {
  // An emptied input yields NaN, wait for a committable value
  if (!Number.isFinite(hours.value)) return
  if (hours.value === savedHours.value && apiKeyEnabled.value === savedKeyEnabled.value) return
  if (saving) {
    queued = true
    return
  }
  saving = true
  saveState.value = 'saving'
  try {
    const s = await api.updateSystemSettings({
      offline_threshold_hours: hours.value,
      api_key_enabled: apiKeyEnabled.value,
    })
    savedHours.value = s.offline_threshold_hours
    savedKeyEnabled.value = s.api_key_enabled
    saveState.value = 'saved'
  } catch (e) {
    saveState.value = 'failed'
    ElMessage.error((e as Error).message)
  } finally {
    saving = false
    // A newer change landed while the request was in flight: persist it now
    if (queued) {
      queued = false
      void save()
    }
  }
}

function fmt(ts: string): string {
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

async function fetchKeys() {
  if (!isAdmin.value || !apiKeyEnabled.value) return
  keysLoading.value = true
  try {
    const res = await api.listApiKeys()
    keys.value = res.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    keysLoading.value = false
  }
}

function openCreate() {
  newName.value = ''
  createVisible.value = true
}

async function create() {
  const name = newName.value.trim()
  if (!name) {
    ElMessage.warning('请填写密钥名称')
    return
  }
  try {
    await api.createApiKey(name)
    createVisible.value = false
    ElMessage.success('密钥已创建')
    await fetchKeys()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function copyKey(row: ApiKey) {
  const ok = await copyText(row.key)
  if (ok) {
    ElMessage.success('已复制')
  } else {
    ElMessage.error('复制失败')
  }
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // HTTP (non-localhost) blocks the clipboard API, fall back to execCommand
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try {
      return document.execCommand('copy')
    } catch {
      return false
    } finally {
      document.body.removeChild(ta)
    }
  }
}

async function revoke(row: ApiKey) {
  try {
    await ElMessageBox.confirm(`确定吊销密钥"${row.name}"?吊销后立即失效`, '吊销密钥', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await api.deleteApiKey(row.id)
    ElMessage.success('密钥已吊销')
    await fetchKeys()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}
</script>

<style scoped>
.card {
  margin-top: 16px;
}
.unit {
  margin-left: 8px;
}
.value {
  font-weight: bold;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.failed {
  color: var(--el-color-danger);
}
.desc {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mono {
  font-family: monospace;
  font-size: 13px;
  margin-right: 8px;
}
</style>
