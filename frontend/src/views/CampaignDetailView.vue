<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { campaignsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { formatDateTime, formatNumber, truncate } from '../utils/format'
import StatusPill from '../components/StatusPill.vue'
import DataTable from '../components/DataTable.vue'
import Pagination from '../components/Pagination.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const id = route.params.id

const campaign = ref(null)
const stats = ref(null)
const loading = ref(false)

const recipients = ref([])
const recTotal = ref(0)
const recLoading = ref(false)
const recStatus = ref('')
const recPage = ref(1)
const recLimit = 20

const messages = ref([])
const msgTotal = ref(0)
const msgLoading = ref(false)
const msgStatus = ref('')
const msgPage = ref(1)

const confirmAction = ref(null) // 'pause' | 'resume' | 'cancel'
const acting = ref(false)
let pollTimer = null

const STATUS_FILTERS = [
  { value: '', label: 'Semua status' },
  { value: 'pending', label: 'Menunggu' },
  { value: 'sent', label: 'Terkirim' },
  { value: 'delivered', label: 'Diterima' },
  { value: 'read', label: 'Dibaca' },
  { value: 'failed', label: 'Gagal' },
]

const progress = computed(() => {
  if (!stats.value) return 0
  const done = ['sent', 'delivered', 'read', 'failed'].reduce((a, k) => a + Number(stats.value[k] || 0), 0)
  const total = done + Number(stats.value.pending || 0)
  return total ? Math.round((done / total) * 100) : 0
})

const canPause = computed(() => ['queued', 'sending'].includes(campaign.value?.status))
const canResume = computed(() => campaign.value?.status === 'paused')
const canCancel = computed(() => ['draft', 'scheduled', 'queued', 'sending', 'paused'].includes(campaign.value?.status))
const isLive = computed(() => ['queued', 'sending', 'paused'].includes(campaign.value?.status))

async function loadCampaign() {
  loading.value = true
  try {
    campaign.value = await campaignsApi.get(id)
  } catch {
    toast.error('Campaign tidak ditemukan.')
    router.push('/')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await campaignsApi.stats(id)
  } catch { /* abaikan saat polling */ }
}

async function loadRecipients() {
  recLoading.value = true
  try {
    const { items, total } = await campaignsApi.recipients(id, {
      status: recStatus.value, page: recPage.value, limit: recLimit,
    })
    recipients.value = items
    recTotal.value = total
  } finally {
    recLoading.value = false
  }
}

async function loadMessages() {
  msgLoading.value = true
  try {
    const { items, total } = await campaignsApi.messages(id, {
      status: msgStatus.value, page: msgPage.value, limit: recLimit,
    })
    messages.value = items
    msgTotal.value = total
  } finally {
    msgLoading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadCampaign(), loadStats(), loadRecipients(), loadMessages()])
}

const ACTION_LABEL = {
  pause: 'Jeda pengiriman campaign ini? Pesan yang belum terkirim akan ditahan.',
  resume: 'Lanjutkan pengiriman campaign ini?',
  cancel: 'Batalkan campaign ini? Penerima yang masih menunggu TIDAK akan dikirim.',
}

async function doAction() {
  if (!confirmAction.value) return
  acting.value = true
  try {
    if (confirmAction.value === 'pause') await campaignsApi.pause(id)
    if (confirmAction.value === 'resume') await campaignsApi.resume(id)
    if (confirmAction.value === 'cancel') await campaignsApi.cancel(id)
    const labels = { pause: 'dijeda', resume: 'dilanjutkan', cancel: 'dibatalkan' }
    toast.success(`Campaign ${labels[confirmAction.value]}.`)
    confirmAction.value = null
    await refreshAll()
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  await refreshAll()
  // Auto-refresh saat campaign sedang berjalan
  pollTimer = setInterval(async () => {
    if (isLive.value) {
      await loadStats()
      await loadRecipients()
    }
  }, 15000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div>
    <div class="flex flex-wrap items-start justify-between gap-3 mb-6">
      <div>
        <button @click="router.push('/')" class="text-sm text-slate-500 hover:text-slate-700 mb-1">← Dashboard</button>
        <h1 class="text-2xl font-bold flex items-center gap-3">
          {{ campaign?.name || 'Memuat…' }}
          <StatusPill v-if="campaign" :status="campaign.status" />
        </h1>
        <div class="text-sm text-slate-500 mt-1 flex flex-wrap gap-x-4 gap-y-1">
          <span>Provider: <StatusPill v-if="campaign" :status="campaign.provider" /></span>
          <span v-if="campaign?.is_test_mode" class="font-semibold text-amber-700">🧪 MODE TEST</span>
          <span v-if="campaign?.send_at">🗓️ {{ formatDateTime(campaign.send_at) }}</span>
        </div>
      </div>
      <div class="flex gap-2">
        <button v-if="canPause" @click="confirmAction = 'pause'" class="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium">⏸️ Jeda</button>
        <button v-if="canResume" @click="confirmAction = 'resume'" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium">▶️ Lanjutkan</button>
        <button v-if="canCancel" @click="confirmAction = 'cancel'" class="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium">⛔ Batalkan</button>
      </div>
    </div>

    <!-- Ringkasan statistik -->
    <div class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-semibold">Ringkasan Pengiriman</h2>
        <span v-if="isLive" class="text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full">● auto-refresh 15 dtk</span>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div class="rounded-lg bg-slate-50 p-3"><div class="text-xs text-slate-500">Menunggu</div><div class="text-xl font-bold">{{ formatNumber(stats?.pending) }}</div></div>
        <div class="rounded-lg bg-blue-50 p-3"><div class="text-xs text-blue-600">Terkirim</div><div class="text-xl font-bold text-blue-700">{{ formatNumber(stats?.sent) }}</div></div>
        <div class="rounded-lg bg-emerald-50 p-3"><div class="text-xs text-emerald-600">Diterima</div><div class="text-xl font-bold text-emerald-700">{{ formatNumber(stats?.delivered) }}</div></div>
        <div class="rounded-lg bg-teal-50 p-3"><div class="text-xs text-teal-600">Dibaca</div><div class="text-xl font-bold text-teal-700">{{ formatNumber(stats?.read) }}</div></div>
        <div class="rounded-lg bg-red-50 p-3"><div class="text-xs text-red-600">Gagal</div><div class="text-xl font-bold text-red-700">{{ formatNumber(stats?.failed) }}</div></div>
      </div>
      <div class="h-2.5 bg-slate-100 rounded-full overflow-hidden">
        <div class="h-full bg-emerald-500 transition-all" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="text-xs text-slate-500 mt-1">{{ progress }}% selesai diproses</div>
    </div>

    <!-- Tabel penerima -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden mb-4">
      <div class="px-4 py-3 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <h2 class="font-semibold">Penerima</h2>
        <select v-model="recStatus" @change="recPage = 1; loadRecipients()" class="field-input !w-auto !py-1.5 text-sm">
          <option v-for="s in STATUS_FILTERS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
      <DataTable :loading="recLoading" empty-title="Belum ada penerima" empty-hint="Tambahkan penerima lewat wizard campaign.">
        <template #head>
          <th class="px-4 py-3 font-semibold">Nama</th>
          <th class="px-4 py-3 font-semibold">Nomor</th>
          <th class="px-4 py-3 font-semibold">Status</th>
          <th class="px-4 py-3 font-semibold">Retry</th>
          <th class="px-4 py-3 font-semibold">Terkirim</th>
          <th class="px-4 py-3 font-semibold">Error</th>
        </template>
        <template v-if="recipients.length">
          <tr v-for="r in recipients" :key="r.id" class="border-t border-slate-100 hover:bg-slate-50">
            <td class="px-4 py-2.5">{{ r.name || r.contact_name || '–' }}</td>
            <td class="px-4 py-2.5 font-mono text-xs">{{ r.phone }}</td>
            <td class="px-4 py-2.5"><StatusPill :status="r.status" /></td>
            <td class="px-4 py-2.5 text-sm">{{ r.retry_count || 0 }}×</td>
            <td class="px-4 py-2.5 text-xs text-slate-500">{{ formatDateTime(r.sent_at) }}</td>
            <td class="px-4 py-2.5 text-xs text-red-600 max-w-56 truncate" :title="r.last_error">{{ r.last_error || '–' }}</td>
          </tr>
        </template>
      </DataTable>
      <Pagination v-if="recTotal > recLimit" :page="recPage" :limit="recLimit" :total="recTotal" @change="(p) => { recPage = p; loadRecipients() }" />
    </div>

    <!-- Daftar pesan per penerima -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div class="px-4 py-3 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <h2 class="font-semibold">Detail Pesan per Penerima</h2>
        <select v-model="msgStatus" @change="msgPage = 1; loadMessages()" class="field-input !w-auto !py-1.5 text-sm">
          <option v-for="s in STATUS_FILTERS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
      <DataTable :loading="msgLoading" empty-title="Belum ada pesan" empty-hint="Pesan muncul setelah pengiriman dimulai.">
        <template #head>
          <th class="px-4 py-3 font-semibold">Penerima</th>
          <th class="px-4 py-3 font-semibold">Isi pesan</th>
          <th class="px-4 py-3 font-semibold">Status</th>
          <th class="px-4 py-3 font-semibold">ID Provider</th>
        </template>
        <template v-if="messages.length">
          <tr v-for="m in messages" :key="m.id" class="border-t border-slate-100 hover:bg-slate-50 align-top">
            <td class="px-4 py-2.5 whitespace-nowrap">
              <div class="font-medium text-sm">{{ m.name || m.contact_name || '–' }}</div>
              <div class="font-mono text-xs text-slate-500">{{ m.phone }}</div>
            </td>
            <td class="px-4 py-2.5 text-sm max-w-md">
              <div class="whitespace-pre-wrap break-words">{{ truncate(m.rendered_message || m.body || m.message, 300) }}</div>
            </td>
            <td class="px-4 py-2.5"><StatusPill :status="m.status" /></td>
            <td class="px-4 py-2.5 font-mono text-xs text-slate-500">{{ m.provider_message_id || '–' }}</td>
          </tr>
        </template>
      </DataTable>
      <Pagination v-if="msgTotal > recLimit" :page="msgPage" :limit="recLimit" :total="msgTotal" @change="(p) => { msgPage = p; loadMessages() }" />
    </div>

    <ConfirmDialog
      :open="!!confirmAction"
      :title="{ pause: 'Jeda campaign?', resume: 'Lanjutkan campaign?', cancel: 'Batalkan campaign?' }[confirmAction]"
      :message="ACTION_LABEL[confirmAction]"
      :confirm-label="{ pause: 'Ya, jeda', resume: 'Ya, lanjutkan', cancel: 'Ya, batalkan' }[confirmAction]"
      :danger="confirmAction === 'cancel'"
      :loading="acting"
      @cancel="confirmAction = null"
      @confirm="doAction"
    />
  </div>
</template>
