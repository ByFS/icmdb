<template>
  <div>
    <el-card class="card">
      <template #header>网段扫描</template>
      <div class="controls">
        <el-input
          v-model="cidr"
          placeholder="CIDR,如 192.168.1.0/24"
          style="max-width: 260px"
          :disabled="scanning"
          @keyup.enter="start"
        />
        <el-button type="primary" :loading="scanning" @click="start">
          {{ scanning ? '扫描中' : '开始扫描' }}
        </el-button>
      </div>
      <div v-if="scanning" class="progress">
        <el-progress
          :percentage="job && job.total ? Math.round((job.scanned / job.total) * 100) : 0"
        />
        <span class="progress-text">
          {{ job ? `已探测 ${job.scanned}/${job.total}` : '准备中' }}
        </span>
      </div>
      <div v-if="job?.status === 'error'" class="error">{{ job.error }}</div>
    </el-card>

    <el-card v-if="job?.status === 'done'" class="card">
      <template #header>
        <span>扫描结果</span>
        <span class="summary">
          存活 {{ job.hosts.length }},已入库 {{ job.hosts.filter(h => h.known).length }},未入库
          {{ job.hosts.filter(h => !h.known).length }}
        </span>
      </template>
      <el-table :data="job.hosts" border>
        <el-table-column resizable prop="ip" label="IP" min-width="140" show-overflow-tooltip/>
        <el-table-column resizable prop="mac" label="MAC" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ row.mac || '-' }}</template>
        </el-table-column>
        <el-table-column resizable prop="hostname" label="主机名" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.hostname || '-' }}</template>
        </el-table-column>
        <el-table-column label="CMDB" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.known" type="success" size="small">
              <router-link :to="`/devices/${row.device_id}`" class="device-link">
                {{ row.device_hostname }}
              </router-link>
            </el-tag>
            <el-tag v-else type="warning" size="small">未入库</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, ScanJob } from '../api'

const cidr = ref('')
const job = ref<ScanJob | null>(null)
const scanning = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null

async function start() {
  const target = cidr.value.trim()
  if (!target) return
  scanning.value = true
  job.value = null
  try {
    const res = await api.startScan(target)
    await poll(res.job_id)
  } catch (e) {
    ElMessage.error((e as Error).message)
    scanning.value = false
  }
}

async function poll(jobId: string) {
  try {
    job.value = await api.getScan(jobId)
  } catch (e) {
    ElMessage.error((e as Error).message)
    scanning.value = false
    return
  }
  if (job.value.status === 'running') {
    pollTimer = setTimeout(() => poll(jobId), 1000)
  } else {
    scanning.value = false
  }
}

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<style scoped>
.card {
  margin-top: 16px;
}
.controls {
  display: flex;
  gap: 12px;
  align-items: center;
}
.progress {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 16px;
}
.progress :deep(.el-progress-bar) {
  flex: 1;
}
.progress-text {
  white-space: nowrap;
  color: var(--el-text-color-secondary);
}
.error {
  margin-top: 12px;
  color: var(--el-color-danger);
}
.summary {
  margin-left: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.device-link {
  color: inherit;
  text-decoration: none;
}
</style>
