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
      <el-table :data="job.hosts">
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
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button v-if="!row.known" link @click="openAdd(row)">添加</el-button>
            <span v-else class="added-mark">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="addVisible" title="添加设备" width="400px">
      <div class="add-info">
        <div class="add-line">IP: {{ addForm.ip }}</div>
        <div class="add-line">MAC: {{ addForm.mac || '-' }}</div>
      </div>
      <el-form label-position="top">
        <el-form-item label="Hostname">
          <el-input
            v-model="addForm.hostname"
            placeholder="缺省用反查名, 无则用 IP"
            @keyup.enter="confirmAdd"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="confirmAdd">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, ScanHost, ScanJob } from '../api'

const cidr = ref('')
const job = ref<ScanJob | null>(null)
const scanning = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let stopped = false

const addVisible = ref(false)
const adding = ref(false)
const addForm = ref<{ ip: string; mac: string | null; hostname: string; row: ScanHost | null }>({
  ip: '',
  mac: null,
  hostname: '',
  row: null,
})

function openAdd(row: ScanHost) {
  addForm.value = { ip: row.ip, mac: row.mac, hostname: row.hostname || '', row }
  addVisible.value = true
}

async function confirmAdd() {
  if (!job.value || !addForm.value.row) return
  adding.value = true
  try {
    const res = await api.addScanHost(
      job.value.job_id,
      addForm.value.ip,
      addForm.value.hostname || undefined,
    )
    // mark the row known immediately, then repoll once so the linked name lands
    addForm.value.row.known = true
    addForm.value.row.device_id = res.device_id
    addVisible.value = false
    ElMessage.success('已添加')
    await poll(job.value.job_id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    adding.value = false
  }
}

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
  if (stopped) return
  try {
    job.value = await api.getScan(jobId)
  } catch (e) {
    ElMessage.error((e as Error).message)
    scanning.value = false
    return
  }
  // the view may have been unmounted while the request was in flight
  if (stopped) return
  if (job.value.status === 'running') {
    pollTimer = setTimeout(() => poll(jobId), 1000)
  } else {
    scanning.value = false
  }
}

onUnmounted(() => {
  stopped = true
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<style scoped>
.card {
  margin-top: 12px;
}

.add-info {
  margin-bottom: 12px;
  font-size: 14px;
  color: var(--muted);
}

.add-line {
  line-height: 22px;
}

.added-mark {
  color: var(--muted);
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
