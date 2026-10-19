<script setup>
import { ref, onMounted } from 'vue'
import { auditLogsApi } from '../api/client'
import { formatDateTime, truncate } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Pagination from '../components/Pagination.vue'
import Icon from '../components/Icon.vue'

const logs = ref([])
const total = ref(0)
const loading = ref(false)

const actionFilter = ref('')
const fromDate = ref('')
const toDate = ref('')
const page = ref(1)
const limit = 20

const expanded = ref(null) // id log yang metadata-nya dibuka

function toISODateTimeLocal(v) {
  if (!v) return undefined
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString()
}

async function load() {
  loading.value = true
  try {
    const { items, total: t } = await auditLogsApi.list({
      action: actionFilter.value || undefined,
      from: toISODateTimeLocal(fromDate.value),
      to: toISODateTimeLocal(toDate.value),
      page: page.value,
      limit,
    })
    logs.value = items || []
    total.value = t
  } finally {
    loading.value = false
  }
}

function reset() {
  actionFilter.value = ''
  fromDate.value = ''
  toDate.value = ''
  page.value = 1
  load()
}

function toggleExpand(id) {
  expanded.value = expanded.value === id ? null : id
}

function prettyMeta(m) {
  if (!m) return '–'
  try {
    return JSON.stringify(m, null, 2)
  } catch {
    return String(m)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="title-row">
      <div>
        <h1 class="page-title">Audit log</h1>
        <p class="page-sub">Jejak aksi penting: login, CRUD, ekstraksi AI, konfirmasi/jeda/batal campaign, ubah pengaturan.</p>
      </div>
      <span class="toolbar-count">{{ total }} entri</span>
    </div>

    <!-- Filter -->
    <div class="toolbar">
      <div>
        <label class="field-label" for="f-aksi">Aksi</label>
        <input id="f-aksi" v-model="actionFilter" class="field-input filter-input" placeholder="mis. campaign.confirm_blast" @keyup.enter="page = 1; load()" />
      </div>
      <div>
        <label class="field-label" for="f-dari">Dari tanggal</label>
        <input id="f-dari" v-model="fromDate" type="date" class="field-input w-auto" />
      </div>
      <div>
        <label class="field-label" for="f-sampai">Sampai tanggal</label>
        <input id="f-sampai" v-model="toDate" type="date" class="field-input w-auto" />
      </div>
      <div class="toolbar-btns">
        <button @click="page = 1; load()" class="btn btn-accent btn-sm">
          <Icon name="search" :size="14" /> Filter
        </button>
        <button @click="reset" class="btn btn-secondary btn-sm">Reset</button>
      </div>
    </div>

    <DataTable
      :loading="loading"
      empty-title="Belum ada audit log"
      empty-hint="Aksi penting yang Anda lakukan akan tercatat di sini."
      empty-icon="scroll"
    >
      <template #head>
        <th>Waktu</th>
        <th>Aksi</th>
        <th>Entitas</th>
        <th>User</th>
        <th>IP</th>
        <th>Detail</th>
      </template>
      <template v-if="logs.length">
        <template v-for="l in logs" :key="l.id">
          <tr>
            <td class="card-label text-xs whitespace-nowrap">{{ formatDateTime(l.created_at) }}</td>
            <td><code class="mono-chip">{{ l.action }}</code></td>
            <td class="text-xs">
              <span v-if="l.entity_type">{{ l.entity_type }}</span>
              <span v-if="l.entity_id" class="mono card-label"> · {{ truncate(l.entity_id, 12) }}</span>
              <span v-else-if="!l.entity_type" class="cell-muted">–</span>
            </td>
            <td class="mono text-xs">{{ l.user_id ? truncate(l.user_id, 12) : '–' }}</td>
            <td class="mono text-xs">{{ l.ip_address || '–' }}</td>
            <td>
              <button
                v-if="l.metadata"
                @click="toggleExpand(l.id)"
                class="btn-tertiary text-xs"
              >
                {{ expanded === l.id ? 'Sembunyikan' : 'Lihat' }}
              </button>
              <span v-else class="cell-muted text-xs">–</span>
            </td>
          </tr>
          <tr v-if="expanded === l.id" class="meta-row">
            <td colspan="6">
              <pre class="mono text-xs whitespace-pre-wrap break-all meta-pre">{{ prettyMeta(l.metadata) }}</pre>
            </td>
          </tr>
        </template>
      </template>
    </DataTable>
    <Pagination v-if="total > limit" :page="page" :limit="limit" :total="total" @change="(p) => { page = p; load() }" />
  </div>
</template>

<style scoped>
.title-row {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 12px; margin-bottom: 24px;
}
.toolbar { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; margin-bottom: 12px; }
.filter-input { width: 224px; }
.toolbar-btns { display: flex; gap: 8px; align-items: center; }
.btn-sm { min-height: 34px; }
.toolbar-count { font-size: 13px; color: var(--muted); }
.mono-chip {
  font-family: var(--font-mono); font-size: 12px;
  background: var(--raised); padding: 2px 6px; border-radius: 4px;
  white-space: nowrap;
}
.cell-muted { color: var(--faint); }
.meta-row td { background: var(--ground); border-top: 1px solid var(--rule); }
.meta-pre { margin: 0; color: var(--muted); }
</style>
