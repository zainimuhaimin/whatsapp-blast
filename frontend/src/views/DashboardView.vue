<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { campaignsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { formatDateTime, formatNumber } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import Icon from '../components/Icon.vue'

const toast = useToast()
const campaigns = ref([])
const statsMap = ref({}) // campaign_id -> stats
const loading = ref(false)
const statusFilter = ref('')
const deleteTarget = ref(null)
const deleting = ref(false)

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

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await campaignsApi.remove(deleteTarget.value.id)
    toast.success(`Campaign "${deleteTarget.value.name}" dihapus.`)
    deleteTarget.value = null
    await load()
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div>
    <div class="title-row">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-sub">Ringkasan seluruh campaign broadcast WhatsApp</p>
      </div>
      <RouterLink to="/campaigns/new" class="btn btn-accent">
        <Icon name="plus" :size="15" /> Campaign Baru
      </RouterLink>
    </div>

    <!-- KPI: satu wadah dibagi hairline -->
    <div class="kpi-strip kpi-6">
      <div class="kpi-cell">
        <div class="kpi-label">Total campaign</div>
        <div class="kpi-value num">{{ formatNumber(totals.campaigns) }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Menunggu</div>
        <div class="kpi-value num">{{ formatNumber(totals.pending) }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Terkirim</div>
        <div class="kpi-value num">{{ formatNumber(totals.sent) }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Diterima</div>
        <div class="kpi-value num">{{ formatNumber(totals.delivered) }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Dibaca</div>
        <div class="kpi-value num">{{ formatNumber(totals.read) }}</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Gagal</div>
        <div class="kpi-value num kpi-bad">{{ formatNumber(totals.failed) }}</div>
      </div>
    </div>

    <!-- Filter -->
    <div class="toolbar">
      <label class="toolbar-label" for="status-filter">Filter status</label>
      <select id="status-filter" v-model="statusFilter" class="field-input toolbar-select">
        <option v-for="s in STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
      <span class="toolbar-count">{{ filtered.length }} campaign</span>
    </div>

    <!-- Daftar campaign -->
    <DataTable
      :loading="loading"
      empty-title="Belum ada campaign"
      empty-hint="Buat campaign pertama lewat wizard 6 langkah."
      empty-icon="send"
    >
      <template #head>
        <th>Nama</th>
        <th>Status</th>
        <th>Provider</th>
        <th>Mode</th>
        <th class="num">Menunggu</th>
        <th class="num">Terkirim</th>
        <th class="num">Diterima</th>
        <th class="num">Dibaca</th>
        <th class="num">Gagal</th>
        <th>Jadwal</th>
        <th><span class="sr-only">Aksi</span></th>
      </template>
      <template v-if="filtered.length">
        <tr v-for="c in filtered" :key="c.id">
          <td>
            <RouterLink :to="`/campaigns/${c.id}`" class="row-link">
              {{ c.name }}
            </RouterLink>
            <div class="row-sub">dibuat {{ formatDateTime(c.created_at) }}</div>
          </td>
          <td><StatusPill :status="c.status" /></td>
          <td><StatusPill :status="c.provider" /></td>
          <td>
            <span v-if="c.is_test_mode" class="pill pill-warning">Test</span>
            <span v-else class="cell-muted">Produksi</span>
          </td>
          <template v-if="statsMap[c.id]">
            <td class="num">{{ formatNumber(statsMap[c.id].pending) }}</td>
            <td class="num">{{ formatNumber(statsMap[c.id].sent) }}</td>
            <td class="num">{{ formatNumber(statsMap[c.id].delivered) }}</td>
            <td class="num">{{ formatNumber(statsMap[c.id].read) }}</td>
            <td class="num">{{ formatNumber(statsMap[c.id].failed) }}</td>
          </template>
          <template v-else>
            <td colspan="5" class="cell-muted text-center">–</td>
          </template>
          <td class="cell-muted text-sm">
            {{ c.send_at ? formatDateTime(c.send_at) : 'Langsung' }}
          </td>
          <td class="whitespace-nowrap">
            <template v-if="c.status === 'draft'">
              <RouterLink
                :to="`/campaigns/new?campaign=${c.id}`"
                class="icon-btn"
                title="Lanjutkan / edit draft ini"
                aria-label="Edit draft"
              >
                <Icon name="pencil" :size="15" />
              </RouterLink>
              <button
                @click="deleteTarget = c"
                class="icon-btn is-danger"
                title="Hapus draft ini"
                aria-label="Hapus draft"
              >
                <Icon name="trash" :size="15" />
              </button>
            </template>
          </td>
        </tr>
      </template>
    </DataTable>
  </div>

  <ConfirmDialog
    :open="!!deleteTarget"
    title="Hapus campaign?"
    :message="`Hapus draft ${deleteTarget?.name}? Data penerima & mapping ikut terhapus. Tindakan ini tidak bisa dibatalkan.`"
    confirm-label="Ya, hapus"
    danger
    :loading="deleting"
    @cancel="deleteTarget = null"
    @confirm="doDelete"
  />
</template>

<style scoped>
.title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 24px;
}
.kpi-strip { margin-bottom: 24px; }
.kpi-6 { grid-template-columns: repeat(6, 1fr); }
.kpi-bad { color: var(--negative); }
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.toolbar-label { font-size: 13px; color: var(--muted); }
.toolbar-select { width: auto; min-height: 34px; }
.toolbar-count { margin-left: auto; font-size: 13px; color: var(--muted); }
.row-link {
  font-weight: 500;
  color: var(--accent-ink);
  text-decoration: none;
}
.row-link:hover { text-decoration: underline; }
.cell-muted { color: var(--muted); font-size: 13px; }
@media (max-width: 1023px) {
  .kpi-6 { grid-template-columns: repeat(3, 1fr); }
  .kpi-6 > .kpi-cell:nth-child(3n+1) { border-left: 0; }
  .kpi-6 > .kpi-cell:nth-child(n+4) { border-top: 1px solid var(--rule); }
}
@media (max-width: 639px) {
  .kpi-6 { grid-template-columns: repeat(2, 1fr); }
  .kpi-6 > .kpi-cell:nth-child(odd) { border-left: 0; }
  .kpi-6 > .kpi-cell:nth-child(n+3) { border-top: 1px solid var(--rule); }
}
</style>
