<template>
  <div class="diff-detail">
    <template
      v-if="diff && (diff.fields.length || diff.nics.length || diff.memory?.length || diff.cpus?.length || diff.disks?.length || diff.psus?.length)"
    >
      <h4 class="section-title">主机字段</h4>
      <el-table :data="diff.fields" border size="small">
        <el-table-column resizable prop="field" label="字段" width="170" show-overflow-tooltip/>
        <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="old-val mono">{{ fmtValue(row.field, row.old) }}</span>
          </template>
        </el-table-column>
        <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="new-val mono">{{ fmtValue(row.field, row.new) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <h4 class="section-title">网卡</h4>
      <el-table :data="diff.nics" border size="small">
        <el-table-column resizable prop="name" label="网卡" width="170" show-overflow-tooltip/>
        <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
              <span class="change-field">{{ fieldLabel(c.field) }}</span>
              <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
            </div>
            <div v-if="!row.changes.length && row.kind === 'removed'" class="change-line mono">
              <span class="change-field">全部</span>
              <span class="old-val">{{ ident(row, [], 'name', '网卡') }}</span>
            </div>
            <span v-if="!row.changes.length && row.kind !== 'removed'" class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-for="(c, i) in row.changes" :key="i" class="val-line mono">
              <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
            </div>
            <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
              {{ emptyHint[row.kind] }}
            </span>
          </template>
        </el-table-column>
        <el-table-column resizable label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="kindTag[row.kind]" size="small">{{ kindLabel[row.kind] }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <template v-if="diff.memory?.length">
        <h4 class="section-title">内存</h4>
        <el-table :data="diff.memory" border size="small">
          <el-table-column resizable prop="slot" label="槽位" width="170" show-overflow-tooltip/>
          <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="change-field">{{ fieldLabel(c.field) }}</span>
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
              </div>
              <div v-if="!row.changes.length && row.kind === 'removed'" class="change-line mono">
                <span class="change-field">全部</span>
                <span class="old-val">{{ ident(row, [], 'slot', '槽位') }}</span>
              </div>
              <span v-if="!row.changes.length && row.kind !== 'removed'" class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="val-line mono">
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">{{ kindLabel[row.kind] }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.cpus?.length">
        <h4 class="section-title">CPU</h4>
        <el-table :data="diff.cpus" border size="small">
          <el-table-column resizable prop="slot" label="槽位" width="170" show-overflow-tooltip/>
          <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="change-field">{{ fieldLabel(c.field) }}</span>
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
              </div>
              <div v-if="!row.changes.length && row.kind === 'removed'" class="change-line mono">
                <span class="change-field">全部</span>
                <span class="old-val">{{ ident(row, [], 'slot', '槽位') }}</span>
              </div>
              <span v-if="!row.changes.length && row.kind !== 'removed'" class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="val-line mono">
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">{{ kindLabel[row.kind] }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.disks?.length">
        <h4 class="section-title">硬盘</h4>
        <el-table :data="diff.disks" border size="small">
          <el-table-column resizable label="SN" width="170" show-overflow-tooltip>
            <template #default="{ row }">{{ ident(row, ['manufacturer', 'model', 'type'], 'serial_number', 'SN') }}</template>
          </el-table-column>
          <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="change-field">{{ fieldLabel(c.field) }}</span>
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
              </div>
              <div v-if="!row.changes.length && row.kind === 'removed'" class="change-line mono">
                <span class="change-field">全部</span>
                <span class="old-val">{{ ident(row, [], 'serial_number', 'SN') }}</span>
              </div>
              <span v-if="!row.changes.length && row.kind !== 'removed'" class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="val-line mono">
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">{{ kindLabel[row.kind] }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.psus?.length">
        <h4 class="section-title">电源</h4>
        <el-table :data="diff.psus" border size="small">
          <el-table-column resizable label="SN" width="170" show-overflow-tooltip>
            <template #default="{ row }">{{ ident(row, ['manufacturer', 'model'], 'serial_number', 'SN') }}</template>
          </el-table-column>
          <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="change-field">{{ fieldLabel(c.field) }}</span>
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
              </div>
              <div v-if="!row.changes.length && row.kind === 'removed'" class="change-line mono">
                <span class="change-field">全部</span>
                <span class="old-val">{{ ident(row, [], 'serial_number', 'SN') }}</span>
              </div>
              <span v-if="!row.changes.length && row.kind !== 'removed'" class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="val-line mono">
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">{{ kindLabel[row.kind] }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="diff.gpus?.length">
        <h4 class="section-title">GPU</h4>
        <el-table :data="diff.gpus" border size="small">
          <el-table-column resizable label="UUID" width="170" show-overflow-tooltip>
            <template #default="{ row }">{{ ident(row, ['name'], 'uuid', 'UUID') }}</template>
          </el-table-column>
          <el-table-column resizable label="旧值(库中)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="change-line mono">
                <span class="change-field">{{ fieldLabel(c.field) }}</span>
                <span class="old-val">{{ fmtValue(c.field, c.old) }}</span>
              </div>
              <div v-if="!row.changes.length && row.kind === 'removed'" class="change-line mono">
                <span class="change-field">全部</span>
                <span class="old-val">{{ ident(row, [], 'uuid', 'UUID') }}</span>
              </div>
              <span v-if="!row.changes.length && row.kind !== 'removed'" class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column resizable label="新值(推送)" width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-for="(c, i) in row.changes" :key="i" class="val-line mono">
                <span class="new-val">{{ fmtValue(c.field, c.new) }}</span>
              </div>
              <span v-if="!row.changes.length" :class="row.kind === 'added' ? 'hint-added' : 'hint-removed'">
                {{ emptyHint[row.kind] }}
              </span>
            </template>
          </el-table-column>
          <el-table-column resizable label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="kindTag[row.kind]" size="small">{{ kindLabel[row.kind] }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </template>
    <el-empty v-else description="该记录无 diff 详情(历史数据)" :image-size="60" />
  </div>
</template>

<script setup lang="ts">
import { PendingChange } from '../api'
import { fieldLabel, fmtValue } from '../utils/diff'

const props = defineProps<{
  diff: PendingChange['diff'] | null
}>()

const kindLabel: Record<string, string> = {
  added: '新增',
  removed: '候删',
  changed: '有变化',
}
const kindTag: Record<string, string> = {
  added: 'success',
  removed: 'danger',
  changed: 'warning',
}
const emptyHint: Record<string, string> = {
  added: '新增, 无字段变化',
  removed: '库中多出, 裁决 new 即删除',
  changed: '-',
}

// Readable identity summary: added takes the new object, removed/changed takes the old object
// name/manufacturer/model first, SN/UUID as annotation (UUID/SN alone does not tell which hardware)
function ident(
  row: {
    kind: string
    uuid?: string
    serial_number?: string
    old: Record<string, unknown> | null
    new: Record<string, unknown> | null
  },
  names: string[],
  key: string,
  keyLabel: string,
): string {
  const o = (row.kind === 'added' ? row.new : row.old) ?? {}
  const parts = names.filter((n) => o[n]).map((n) => String(o[n]))
  const id = (row as Record<string, unknown>)[key] ?? o[key]
  return [...parts, id ? `${keyLabel}:${id}` : ''].filter(Boolean).join(' · ') || '-'
}
</script>

<style scoped>
.diff-detail {
  padding: 8px 16px;
}
.section-title {
  margin: 8px 0;
}
/* Every table shares one column grid: fixed 170px identity column, then the value columns,
   so the 旧值/新值/类型 boundaries align across sections */
.change-line {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 0 8px;
  align-items: baseline;
  padding: 1px 0;
  font-size: 12px;
}
.change-field {
  text-align: right;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.val-line {
  padding: 1px 0;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.old-val {
  color: var(--el-color-danger);
  background: #fef0f0;
  text-decoration: line-through;
  padding: 0 4px;
  border-radius: 3px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.new-val {
  color: var(--el-color-success);
  background: #f0f9eb;
  padding: 0 4px;
  border-radius: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.hint-added {
  color: var(--el-color-success);
  font-size: 12px;
}
.hint-removed {
  color: var(--el-color-danger);
  font-size: 12px;
}
</style>
