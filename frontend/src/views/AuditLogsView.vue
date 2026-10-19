<script setup>
import { ref, onMounted } from 'vue'
import { auditLogsApi } from '../api/client'
import { formatDateTime, truncate } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Pagination from '../components/Pagination.vue'

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
    <div class="mb-6">
      <h1 class="text-2xl font-bold">Audit Log</h1>
      <p class="text-sm text-slate-500">Jejak semua aksi penting: login, CRUD, ekstraksi AI, konfirmasi/jeda/batal campaign, ubah pengaturan.</p>
    </div>

    <!-- Filter -->
    <div class="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <label class="field-label">Aksi</label>
        <input v-model="actionFilter" class="field-input !w-56" placeholder="mis. campaign.confirm_blast" @keyup.enter="page = 1; load()" />
      </div>
      <div>
        <label class="field-label">Dari tanggal</label>
        <input v-model="fromDate" type="date" class="field-input !w-auto" />
      </div>
      <div>
        <label class="field-label">Sampai tanggal</label>
        <input v-model="toDate" type="date" class="field-input !w-auto" />
      </div>
      <button @click="page = 1; load()" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium">
        🔍 Filter
      </button>
      <button @click="reset" class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-white">
        Reset
      </button>
    </div>

    <DataTable
      :loading="loading"
      empty-title="Belum ada audit log"
      empty-hint="Aksi penting yang Anda lakukan akan tercatat di sini."
      empty-icon="🧾"
    >
      <template #head>
        <th class="px-4 py-3 font-semibold">Waktu</th>
        <th class="px-4 py-3 font-semibold">Aksi</th>
        <th class="px-4 py-3 font-semibold">Entitas</th>
        <th class="px-4 py-3 font-semibold">User</th>
        <th class="px-4 py-3 font-semibold">IP</th>
        <th class="px-4 py-3 font-semibold">Detail</th>
      </template>
      <template v-if="logs.length">
        <template v-for="l in logs" :key="l.id">
          <tr class="border-t border-slate-100 hover:bg-slate-50">
            <td class="px-4 py-2.5 text-xs text-slate-500 whitespace-nowrap">{{ formatDateTime(l.created_at) }}</td>
            <td class="px-4 py-2.5"><code class="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{{ l.action }}</code></td>
            <td class="px-4 py-2.5 text-xs">
              <span v-if="l.entity_type">{{ l.entity_type }}</span>
              <span v-if="l.entity_id" class="font-mono text-slate-500"> · {{ truncate(l.entity_id, 12) }}</span>
              <span v-else-if="!l.entity_type" class="text-slate-400">–</span>
            </td>
            <td class="px-4 py-2.5 text-xs font-mono">{{ l.user_id ? truncate(l.user_id, 12) : '–' }}</td>
            <td class="px-4 py-2.5 text-xs font-mono">{{ l.ip_address || '–' }}</td>
            <td class="px-4 py-2.5">
              <button
                v-if="l.metadata"
                @click="toggleExpand(l.id)"
                class="text-xs text-emerald-700 underline"
              >
                {{ expanded === l.id ? 'Sembunyikan' : 'Lihat' }}
              </button>
              <span v-else class="text-xs text-slate-400">–</span>
            </td>
          </tr>
          <tr v-if="expanded === l.id" class="border-t border-slate-100 bg-slate-50">
            <td colspan="6" class="px-4 py-2.5">
              <pre class="text-xs font-mono whitespace-pre-wrap break-all">{{ prettyMeta(l.metadata) }}</pre>
            </td>
          </tr>
        </template>
      </template>
    </DataTable>
    <Pagination v-if="total > limit" :page="page" :limit="limit" :total="total" @change="(p) => { page = p; load() }" />
  </div>
</template>
