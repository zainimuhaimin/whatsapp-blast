<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { campaignsApi } from '../api/client'
import { formatDateTime, formatNumber } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import StatusPill from '../components/StatusPill.vue'

const campaigns = ref([])
const statsMap = ref({}) // campaign_id -> stats
const loading = ref(false)
const statusFilter = ref('')

const STATUSES = [
  { value: '', label: 'Semua status' },
  { value: 'draft', label: 'Draft' },
  { value: 'scheduled', label: 'Terjadwal' },
  { value: 'queued', label: 'Antre' },
  { value: 'sending', label: 'Mengirim' },
  { value: 'paused', label: 'Jeda' },
  { value: 'completed', label: 'Selesai' },
  { value: 'failed', label: 'Gagal' },
  { value: 'cancelled', label: 'Dibatalkan' },
]

const filtered = computed(() =>
  statusFilter.value
    ? campaigns.value.filter((c) => c.status === statusFilter.value)
    : campaigns.value
)

const totals = computed(() => {
  const t = { pending: 0, sent: 0, delivered: 0, read: 0, failed: 0, campaigns: campaigns.value.length }
  for (const c of campaigns.value) {
    const s = statsMap.value[c.id]
    if (!s) continue
    for (const k of ['pending', 'sent', 'delivered', 'read', 'failed']) {
      t[k] += Number(s[k] || 0)
    }
  }
  return t
})

async function load() {
  loading.value = true
  try {
    const { items } = await campaignsApi.list()
    campaigns.value = items
    // Ambil statistik per campaign (agregasi di backend, per design)
    statsMap.value = {}
    await Promise.all(
      items.map(async (c) => {
        try {
          statsMap.value[c.id] = await campaignsApi.stats(c.id)
        } catch {
          statsMap.value[c.id] = null
        }
      })
    )
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-bold">Dashboard</h1>
        <p class="text-sm text-slate-500">Ringkasan seluruh campaign broadcast WhatsApp</p>
      </div>
      <RouterLink
        to="/campaigns/new"
        class="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm transition-colors"
      >
        ➕ Campaign Baru
      </RouterLink>
    </div>

    <!-- Kartu statistik global -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs text-slate-500">Total Campaign</div>
        <div class="text-2xl font-bold mt-1">{{ formatNumber(totals.campaigns) }}</div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs text-slate-500">Menunggu</div>
        <div class="text-2xl font-bold mt-1 text-slate-600">{{ formatNumber(totals.pending) }}</div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs text-slate-500">Terkirim</div>
        <div class="text-2xl font-bold mt-1 text-blue-600">{{ formatNumber(totals.sent) }}</div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs text-slate-500">Diterima</div>
        <div class="text-2xl font-bold mt-1 text-emerald-600">{{ formatNumber(totals.delivered) }}</div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs text-slate-500">Dibaca</div>
        <div class="text-2xl font-bold mt-1 text-teal-600">{{ formatNumber(totals.read) }}</div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs text-slate-500">Gagal</div>
        <div class="text-2xl font-bold mt-1 text-red-600">{{ formatNumber(totals.failed) }}</div>
      </div>
    </div>

    <!-- Filter -->
    <div class="flex items-center gap-3 mb-4">
      <label class="text-sm text-slate-600">Filter status:</label>
      <select v-model="statusFilter" class="field-input !w-auto">
        <option v-for="s in STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
    </div>

    <!-- Daftar campaign -->
    <DataTable
      :loading="loading"
      empty-title="Belum ada campaign"
      empty-hint="Buat campaign pertama Anda lewat wizard 6 langkah."
      empty-icon="🚀"
    >
      <template #head>
        <th class="px-4 py-3 font-semibold">Nama</th>
        <th class="px-4 py-3 font-semibold">Status</th>
        <th class="px-4 py-3 font-semibold">Provider</th>
        <th class="px-4 py-3 font-semibold">Mode</th>
        <th class="px-4 py-3 font-semibold text-right">Menunggu</th>
        <th class="px-4 py-3 font-semibold text-right">Terkirim</th>
        <th class="px-4 py-3 font-semibold text-right">Diterima</th>
        <th class="px-4 py-3 font-semibold text-right">Dibaca</th>
        <th class="px-4 py-3 font-semibold text-right">Gagal</th>
        <th class="px-4 py-3 font-semibold">Jadwal</th>
      </template>
      <template v-if="filtered.length">
        <tr
          v-for="c in filtered"
          :key="c.id"
          class="border-t border-slate-100 hover:bg-slate-50"
        >
          <td class="px-4 py-3">
            <RouterLink :to="`/campaigns/${c.id}`" class="font-medium text-emerald-700 hover:underline">
              {{ c.name }}
            </RouterLink>
            <div class="text-xs text-slate-400">dibuat {{ formatDateTime(c.created_at) }}</div>
          </td>
          <td class="px-4 py-3"><StatusPill :status="c.status" /></td>
          <td class="px-4 py-3"><StatusPill :status="c.provider" /></td>
          <td class="px-4 py-3">
            <span v-if="c.is_test_mode" class="text-xs font-semibold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">🧪 TEST</span>
            <span v-else class="text-xs text-slate-400">Produksi</span>
          </td>
          <template v-if="statsMap[c.id]">
            <td class="px-4 py-3 text-right">{{ formatNumber(statsMap[c.id].pending) }}</td>
            <td class="px-4 py-3 text-right">{{ formatNumber(statsMap[c.id].sent) }}</td>
            <td class="px-4 py-3 text-right">{{ formatNumber(statsMap[c.id].delivered) }}</td>
            <td class="px-4 py-3 text-right">{{ formatNumber(statsMap[c.id].read) }}</td>
            <td class="px-4 py-3 text-right">{{ formatNumber(statsMap[c.id].failed) }}</td>
          </template>
          <template v-else>
            <td colspan="5" class="px-4 py-3 text-center text-xs text-slate-400">–</td>
          </template>
          <td class="px-4 py-3 text-xs text-slate-500">
            {{ c.send_at ? formatDateTime(c.send_at) : 'Langsung' }}
          </td>
        </tr>
      </template>
    </DataTable>
  </div>
</template>
