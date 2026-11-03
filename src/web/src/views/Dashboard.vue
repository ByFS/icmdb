<template>
  <div v-loading="loading" class="page">
    <div class="title-row">
      <h1 class="page-title">资产概览</h1>
      <p class="finding">{{ finding }}</p>
    </div>

    <div class="kpi-tray">
      <div class="kpi">
        <div class="kpi-label">资产总数</div>
        <div class="kpi-value" :class="{ zero: !totalCount }">
          {{ totalCount === null ? '-' : totalCount }}
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-label">活跃</div>
        <div class="kpi-value kpi-positive" :class="{ zero: !activeCount }">
          {{ activeCount === null ? '-' : activeCount }}
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-label">疑似下线</div>
        <div class="kpi-value kpi-warning" :class="{ zero: !offlineCount }">
          {{ offlineCount === null ? '-' : offlineCount }}
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-label">待裁决</div>
        <div class="kpi-value kpi-accent" :class="{ zero: !pendingCount }">
          {{ pendingCount === null ? '-' : pendingCount }}
        </div>
      </div>
    </div>

    <div v-if="pendingCount" class="pending-row">
      <span class="pending-text">{{ pendingCount }} 项字段变更等待裁决</span>
      <el-button type="primary" @click="$router.push('/conflicts')">去裁决</el-button>
    </div>

    <section class="section">
      <div class="section-head">
        <h2 class="section-title">最近变更</h2>
        <span class="section-note">裁决生效后写入变更历史</span>
      </div>
      <el-card class="card" :body-style="{ padding: '0 16px' }">
        <el-table
          ref="tableRef"
          :data="(stats?.recent_changes || []).slice(0, 5)"
          @row-click="toggleExpand"
        >
          <el-table-column type="expand" width="40">
            <template #default="{ row }">
              <DiffDetail :diff="row.diff" />
            </template>
          </el-table-column>
          <el-table-column label="设备" width="100">
            <template #default="{ row }">
              <router-link :to="`/devices/${row.device_id}`" class="link mono">
                #{{ row.device_id }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column label="变更内容" min-width="220">
            <template #default="{ row }">{{ digest(row) }}</template>
          </el-table-column>
          <el-table-column label="来源" width="120">
            <template #default="{ row }">{{ row.source || '-' }}</template>
          </el-table-column>
          <el-table-column label="时间" min-width="170" align="right">
            <template #default="{ row }">
              <span class="time">{{ fmt(row.created_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, TableInstance } from 'element-plus'
import { api, DashboardOut, HistoryRow } from '../api'
import DiffDetail from '../components/DiffDetail.vue'

const stats = ref<DashboardOut | null>(null)
const loading = ref(false)
const tableRef = ref<TableInstance>()

// Click anywhere on a row to expand/collapse details (except clicks on the device column link)
function toggleExpand(row: HistoryRow, _column: unknown, event: Event) {
  if ((event.target as HTMLElement).closest('a')) return
  tableRef.value?.toggleRowExpansion(row)
}

// Change content digest: only major categories (e.g. memory, CPU), full details in the expanded row
function digest(row: HistoryRow): string {
  const diff = row.diff as
    | {
        fields?: unknown[]
        nics?: unknown[]
        memory?: unknown[]
        cpus?: unknown[]
        disks?: unknown[]
        psus?: unknown[]
        gpus?: unknown[]
      }
    | null
  if (!diff) return '-'
  const parts: string[] = []
  if (diff.fields?.length) parts.push('主机字段')
  if (diff.nics?.length) parts.push('网卡')
  if (diff.memory?.length) parts.push('内存')
  if (diff.cpus?.length) parts.push('CPU')
  if (diff.disks?.length) parts.push('硬盘')
  if (diff.psus?.length) parts.push('电源')
  if (diff.gpus?.length) parts.push('GPU')
  return parts.length ? parts.join(',') : '-'
}

const totalCount = computed(() => stats.value?.total_devices ?? null)
const activeCount = computed(() => stats.value?.active ?? null)
const offlineCount = computed(() => stats.value?.suspected_offline ?? null)
const pendingCount = computed(() => stats.value?.pending_changes ?? null)

// The one finding: the fact in today's data that most needs attention
const finding = computed(() => {
  const offline = stats.value?.suspected_offline ?? 0
  const pending = stats.value?.pending_changes ?? 0
  if (!offline && !pending) return '暂无待处理事项'
  const parts: string[] = []
  if (offline) parts.push(`${offline} 台疑似下线`)
  if (pending) parts.push(`${pending} 项变更待裁决`)
  return parts.join(', ')
})

function fmt(ts: string | null): string {
  if (!ts) return '-'
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : ts + 'Z'
  return new Date(utc).toLocaleString()
}

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await api.dashboard()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-title {
  font-size: 24px;
  font-weight: 500;
  margin: 0;
}

.finding {
  margin: 4px 0 0;
  font-size: 14px;
  color: var(--muted);
}

/* KPIs are type, not tiles: labels over ink figures, one accent on the screen's question */
.kpi-tray {
  display: flex;
  background: #fafafa;
  border-radius: var(--radius-card);
  margin-top: 24px;
}

.kpi {
  flex: 1;
  padding: 14px 20px;
  border-right: 1px solid var(--rule);
}

.kpi:last-child {
  border-right: none;
}

.kpi-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--muted);
}

.kpi-value {
  margin-top: 2px;
  font-size: 24px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}

.kpi-accent {
  color: var(--hue);
}

/* status semantics: colour says what the number means, not decoration */
.kpi-positive {
  color: var(--positive);
}

.kpi-warning {
  color: #c2410c;
}

.kpi-value.zero {
  color: var(--muted);
}

/* The screen's one job, one click away */
.pending-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}

.pending-text {
  flex: 1;
  font-size: 14px;
}

.section {
  margin-top: 48px;
}

.section-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
}

.section-note {
  font-size: 14px;
  color: var(--muted);
}

.time {
  color: var(--muted);
}
</style>
