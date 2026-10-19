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
import Icon from '../components/Icon.vue'

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
const retryTarget = ref(null) // recipient yang akan di-retry
const acting = ref(false)

// Kirim manual via wa.me (tanpa otomasi — paling aman dari banned)
const chatLinks = ref([])
const chatTotal = ref(0)
const chatLoading = ref(false)
const chatPage = ref(1)
const chatLimit = 20
const showChatLinks = ref(false)
let pollTimer = null

const STATUS_FILTERS = [
  { value: '', label: 'Semua status' },
  { value: 'pending', label: 'Menunggu' },
  { value: 'sent', label: 'Terkirim' },
  { value: 'delivered', label: 'Diterima' },
  { value: 'read', label: 'Dibaca' },
  { value: 'failed', label: 'Gagal' },
  { value: 'skipped', label: 'Dilewati' },
]

const progress = computed(() => {
  if (!stats.value) return 0
  const done = ['sent', 'delivered', 'read', 'failed', 'skipped'].reduce((a, k) => a + Number(stats.value[k] || 0), 0)
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

async function doRetryRecipient() {
  if (!retryTarget.value) return
  acting.value = true
  try {
    await campaignsApi.retryRecipient(id, retryTarget.value.id)
    toast.success(`Retry dikirim untuk ${retryTarget.value.phone}.`)
    retryTarget.value = null
    await refreshAll()
  } finally {
    acting.value = false
  }
}

async function loadChatLinks() {
  chatLoading.value = true
  try {
    const { items, total } = await campaignsApi.chatLinks(id, {
      page: chatPage.value, limit: chatLimit,
    })
    chatLinks.value = items
    chatTotal.value = total
  } finally {
    chatLoading.value = false
  }
}

async function toggleChatLinks() {
  showChatLinks.value = !showChatLinks.value
  if (showChatLinks.value && !chatLinks.value.length) await loadChatLinks()
}

// Tandai hasil pengiriman manual (audit): 'sent' = terkirim, 'skipped' = dilewatkan
const manualActing = ref(false)
async function markManual(link, result) {
  manualActing.value = true
  try {
    await campaignsApi.manualStatus(id, link.recipient_id, result)
    toast.success(
      result === 'sent'
        ? `${link.phone} ditandai terkirim.`
        : `${link.phone} dilewatkan.`
    )
    await loadChatLinks()
    await loadStats()
    await loadRecipients()
  } finally {
    manualActing.value = false
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
    <div class="title-row">
      <div class="min-w-0">
        <button @click="router.push('/')" class="back-link">
          <Icon name="chevron-left" :size="14" /> Dashboard
        </button>
        <h1 class="page-title title-with-pill">
          {{ campaign?.name || 'Memuat…' }}
          <StatusPill v-if="campaign" :status="campaign.status" />
        </h1>
        <div class="title-meta">
          <span>Provider <StatusPill v-if="campaign" :status="campaign.provider" /></span>
          <span v-if="campaign?.is_test_mode" class="pill pill-warning">Mode test</span>
          <span v-if="campaign?.send_at" class="meta-inline"><Icon name="calendar" :size="13" /> {{ formatDateTime(campaign.send_at) }}</span>
        </div>
      </div>
      <div class="title-actions">
        <button v-if="canPause" @click="confirmAction = 'pause'" class="btn btn-secondary">
          <Icon name="pause" :size="14" /> Jeda
        </button>
        <button v-if="canResume" @click="confirmAction = 'resume'" class="btn btn-accent">
          <Icon name="play" :size="14" /> Lanjutkan
        </button>
        <button v-if="canCancel" @click="confirmAction = 'cancel'" class="btn btn-danger">
          Batalkan
        </button>
      </div>
    </div>

    <!-- Ringkasan pengiriman -->
    <div class="card card-pad mb-4">
      <div class="summary-head">
        <h2 class="section-title">Ringkasan pengiriman</h2>
        <span v-if="isLive" class="live-dot"><span class="dot"></span> auto-refresh 15 dtk</span>
      </div>
      <div class="kpi-strip kpi-6">
        <div class="kpi-cell">
          <div class="kpi-label">Menunggu</div>
          <div class="kpi-value num">{{ formatNumber(stats?.pending) }}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Terkirim</div>
          <div class="kpi-value num">{{ formatNumber(stats?.sent) }}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Diterima</div>
          <div class="kpi-value num">{{ formatNumber(stats?.delivered) }}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Dibaca</div>
          <div class="kpi-value num">{{ formatNumber(stats?.read) }}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Gagal</div>
          <div class="kpi-value num kpi-bad">{{ formatNumber(stats?.failed) }}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Dilewati</div>
          <div class="kpi-value num">{{ formatNumber(stats?.skipped) }}</div>
        </div>
      </div>
      <div class="progress-track" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="card-label mt-1">{{ progress }}% selesai diproses</div>
    </div>

    <!-- Tabel penerima -->
    <div class="tbl-wrap mb-4">
      <div class="tbl-title-row">
        <h2 class="section-title">Penerima</h2>
        <select v-model="recStatus" @change="recPage = 1; loadRecipients()" class="field-input filter-select">
          <option v-for="s in STATUS_FILTERS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
      <DataTable :loading="recLoading" empty-title="Belum ada penerima" empty-hint="Tambahkan penerima lewat wizard campaign.">
        <template #head>
          <th>Nama</th>
          <th>Nomor</th>
          <th>Status</th>
          <th class="num">Retry</th>
          <th>Terkirim</th>
          <th>Error</th>
          <th><span class="sr-only">Aksi</span></th>
        </template>
        <template v-if="recipients.length">
          <tr v-for="r in recipients" :key="r.id">
            <td class="row-title">{{ r.name || r.contact_name || '–' }}</td>
            <td class="mono text-xs">{{ r.phone }}</td>
            <td><StatusPill :status="r.status" /></td>
            <td class="num">{{ r.retry_count || 0 }}×</td>
            <td class="card-label text-xs">{{ formatDateTime(r.sent_at) }}</td>
            <td class="text-xs max-w-56 truncate" style="color: var(--negative)" :title="r.last_error">{{ r.last_error || '–' }}</td>
            <td class="whitespace-nowrap">
              <button
                v-if="r.status === 'failed'"
                @click="retryTarget = r"
                class="icon-btn"
                title="Coba kirim ulang ke penerima ini"
                aria-label="Coba kirim ulang"
              >
                <Icon name="refresh" :size="15" />
              </button>
            </td>
          </tr>
        </template>
      </DataTable>
      <Pagination v-if="recTotal > recLimit" :page="recPage" :limit="recLimit" :total="recTotal" @change="(p) => { recPage = p; loadRecipients() }" />
    </div>

    <!-- Daftar pesan per penerima -->
    <div class="tbl-wrap">
      <div class="tbl-title-row">
        <h2 class="section-title">Detail pesan per penerima</h2>
        <select v-model="msgStatus" @change="msgPage = 1; loadMessages()" class="field-input filter-select">
          <option v-for="s in STATUS_FILTERS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
      <DataTable :loading="msgLoading" empty-title="Belum ada pesan" empty-hint="Pesan muncul setelah pengiriman dimulai.">
        <template #head>
          <th>Penerima</th>
          <th>Isi pesan</th>
          <th>Status</th>
          <th>ID provider</th>
        </template>
        <template v-if="messages.length">
          <tr v-for="m in messages" :key="m.id" class="align-top">
            <td class="whitespace-nowrap">
              <div class="row-title text-sm">{{ m.name || m.contact_name || '–' }}</div>
              <div class="mono text-xs card-label">{{ m.phone }}</div>
            </td>
            <td class="text-sm max-w-md">
              <div class="whitespace-pre-wrap break-words">{{ truncate(m.rendered_message || m.body || m.message, 300) }}</div>
            </td>
            <td><StatusPill :status="m.status" /></td>
            <td class="mono text-xs card-label">{{ m.provider_message_id || '–' }}</td>
          </tr>
        </template>
      </DataTable>
      <Pagination v-if="msgTotal > recLimit" :page="msgPage" :limit="recLimit" :total="msgTotal" @change="(p) => { msgPage = p; loadMessages() }" />
    </div>

    <!-- Kirim manual via WhatsApp (wa.me) -->
    <div class="tbl-wrap mt-4">
      <div class="tbl-title-row">
        <h2 class="section-title">Kirim manual via WhatsApp</h2>
        <button @click="toggleChatLinks" class="btn btn-secondary text-sm">
          <Icon name="chat" :size="14" /> {{ showChatLinks ? 'Sembunyikan' : 'Tampilkan' }}
        </button>
      </div>
      <div v-if="showChatLinks">
        <p class="card-label mb-3">
          Cara paling aman tanpa risiko banned otomasi: klik <b>Buka di WhatsApp</b> per penerima —
          WhatsApp terbuka dengan pesan yang sudah ter-render, tinggal tekan kirim di aplikasi.
          Tidak perlu Baileys terhubung.
        </p>
        <DataTable :loading="chatLoading" empty-title="Belum ada penerima" empty-hint="Tambahkan penerima lewat wizard campaign.">
          <template #head>
            <th>Penerima</th>
            <th>Status</th>
            <th>Pesan</th>
            <th><span class="sr-only">Aksi</span></th>
          </template>
          <template v-if="chatLinks.length">
            <tr v-for="l in chatLinks" :key="l.recipient_id" class="align-top">
              <td class="whitespace-nowrap">
                <div class="row-title text-sm">{{ l.name || '–' }}</div>
                <div class="mono text-xs card-label">{{ l.phone }}</div>
              </td>
              <td><StatusPill :status="l.status" /></td>
              <td class="text-sm max-w-md">
                <div class="whitespace-pre-wrap break-words">{{ truncate(l.message, 200) }}</div>
              </td>
              <td class="whitespace-nowrap">
                <div class="manual-actions">
                  <a :href="l.wa_url" target="_blank" rel="noopener" class="btn btn-secondary text-sm">
                    <Icon name="external" :size="14" /> Buka di WhatsApp
                  </a>
                  <div v-if="!['sent', 'delivered', 'read'].includes(l.status)" class="manual-mark">
                    <button @click="markManual(l, 'sent')" :disabled="manualActing" class="btn btn-tertiary text-sm" title="Tandai sudah terkirim manual (audit)">
                      <Icon name="check" :size="14" /> Terkirim
                    </button>
                    <button @click="markManual(l, 'skipped')" :disabled="manualActing" class="btn btn-tertiary text-sm" title="Lewati penerima ini (audit)">
                      <Icon name="x" :size="14" /> Lewati
                    </button>
                  </div>
                  <div v-else class="card-label text-xs manual-done"><Icon name="check" :size="12" /> hasil manual tercatat</div>
                </div>
              </td>
            </tr>
          </template>
        </DataTable>
        <Pagination v-if="chatTotal > chatLimit" :page="chatPage" :limit="chatLimit" :total="chatTotal" @change="(p) => { chatPage = p; loadChatLinks() }" />
      </div>
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
    <ConfirmDialog
      :open="!!retryTarget"
      title="Coba kirim ulang?"
      :message="`Kirim ulang pesan ke ${retryTarget?.phone}? Penerima akan dicoba lagi dari awal.`"
      confirm-label="Ya, coba lagi"
      :loading="acting"
      @cancel="retryTarget = null"
      @confirm="doRetryRecipient"
    />
  </div>
</template>

<style scoped>
.title-row {
  display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between;
  gap: 12px; margin-bottom: 24px;
}
.back-link {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 13px; color: var(--muted); background: none; border: 0; cursor: pointer;
  margin-bottom: 6px; padding: 0;
}
.back-link:hover { color: var(--text); }
.title-with-pill { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.title-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 8px; font-size: 13px; color: var(--muted); }
.meta-inline { display: inline-flex; align-items: center; gap: 6px; }
.title-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.manual-actions { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.manual-mark { display: flex; gap: 6px; flex-wrap: wrap; }
.manual-done { display: inline-flex; align-items: center; gap: 4px; }
.summary-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.live-dot { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--accent-ink); background: var(--accent-soft); padding: 4px 10px; border-radius: 999px; }
.live-dot .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); }
.kpi-6 { grid-template-columns: repeat(6, 1fr); margin-bottom: 16px; }
.kpi-bad { color: var(--negative); }
.progress-track {
  height: 8px; border-radius: 999px;
  background: var(--accent-track);
  overflow: hidden;
}
.progress-fill { height: 100%; background: var(--accent); border-radius: 999px; transition: width 0.4s ease; }
.tbl-title-row {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--rule);
}
.filter-select { width: auto; min-height: 32px; font-size: 13px; }
@media (max-width: 1023px) {
  .kpi-6 { grid-template-columns: repeat(3, 1fr); }
  .kpi-6 > .kpi-cell:nth-child(3n+1) { border-left: 0; }
  .kpi-6 > .kpi-cell:nth-child(n+4) { border-top: 1px solid var(--rule); }
}
@media (max-width: 639px) {
  .kpi-6 { grid-template-columns: repeat(2, 1fr); }
  .kpi-6 > .kpi-cell:nth-child(odd) { border-left: 0; }
  .kpi-6 > .kpi-cell:nth-child(n+3) { border-top: 1px solid var(--rule); }
  .title-actions .btn { flex: 1; }
}
</style>
