<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import QRCode from 'qrcode'
import { http } from '../api/client'
import { useToast } from '../stores/useToast'
import Icon from '../components/Icon.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const toast = useToast()
const status = ref(null)
const loading = ref(true)
const qrDataUrl = ref('')
const qrLoading = ref(false)
const confirmDisconnect = ref(false)
const disconnecting = ref(false)
let pollTimer = null

const senderApi = {
  status: () => http.get('/sender/status').then((r) => r.data),
  qrData: () => http.get('/sender/qr-data').then((r) => r.data),
  disconnect: () => http.post('/sender/disconnect').then((r) => r.data),
}

const stateLabel = computed(() => {
  if (!status.value) return 'Memuat…'
  if (!status.value.configured) return 'Belum dikonfigurasi'
  if (!status.value.reachable) return 'Sidecar mati'
  if (status.value.connected) return 'Terhubung'
  return 'Menunggu pairing'
})

const statePill = computed(() => {
  if (!status.value) return 'pill-neutral'
  if (status.value.connected) return 'pill-positive'
  if (!status.value.configured || !status.value.reachable) return 'pill-negative'
  return 'pill-warning'
})

const uptimeText = computed(() => {
  const s = status.value?.uptime_seconds || 0
  if (s < 60) return `${s} detik`
  if (s < 3600) return `${Math.floor(s / 60)} menit`
  return `${Math.floor(s / 3600)} jam ${Math.floor((s % 3600) / 60)} mnt`
})

async function loadStatus(silent = false) {
  if (!silent) loading.value = true
  try {
    status.value = await senderApi.status()
    if (status.value.connected) {
      stopPolling()
      qrDataUrl.value = ''
    } else if (status.value.configured && status.value.reachable) {
      await loadQr()
    }
  } catch {
    if (!silent) toast.error('Gagal memuat status koneksi.')
  } finally {
    if (!silent) loading.value = false
  }
}

async function loadQr() {
  qrLoading.value = true
  try {
    const data = await senderApi.qrData()
    if (data.qr) {
      qrDataUrl.value = await QRCode.toDataURL(data.qr, { width: 280, margin: 1 })
    } else {
      qrDataUrl.value = ''
    }
  } catch {
    qrDataUrl.value = ''
  } finally {
    qrLoading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const s = await senderApi.status()
      status.value = s
      if (s.connected) {
        stopPolling()
        qrDataUrl.value = ''
        toast.success(`WhatsApp terhubung${s.phone ? ' sebagai ' + s.phone : ''}.`)
      } else if (s.configured && s.reachable) {
        await loadQr()
      }
    } catch { /* abaikan saat polling */ }
  }, 8000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function doDisconnect() {
  disconnecting.value = true
  try {
    await senderApi.disconnect()
    confirmDisconnect.value = false
    toast.success('Koneksi diputus. Scan QR ulang untuk pairing kembali.')
    await loadStatus()
    startPolling()
  } catch (e) {
    toast.error(e?.response?.data?.detail || 'Gagal memutus koneksi.')
  } finally {
    disconnecting.value = false
  }
}

onMounted(async () => {
  await loadStatus()
  if (status.value && !status.value.connected) startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div>
    <div class="title-row">
      <div>
        <h1 class="page-title">Koneksi WA</h1>
        <p class="page-sub">Status pairing nomor pengirim untuk jalur non-resmi (Baileys).</p>
      </div>
      <div class="title-actions">
        <button @click="loadStatus()" :disabled="loading" class="btn btn-secondary">
          <Icon name="refresh" :size="14" /> {{ loading ? 'Memuat…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div class="card card-pad mb-4">
      <div class="summary-head">
        <h2 class="section-title">Jalur non-resmi — Baileys <span class="card-label">(gratis, self-hosted)</span></h2>
        <span v-if="status" class="pill" :class="statePill">{{ stateLabel }}</span>
      </div>

      <div v-if="loading" class="card-label">Memuat status…</div>

      <template v-else-if="status">
        <!-- Terhubung -->
        <div v-if="status.connected" class="kpi-strip kpi-3">
          <div class="kpi-cell">
            <div class="kpi-label">Nomor terhubung</div>
            <div class="kpi-value mono">{{ status.phone || '–' }}</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-label">Uptime sesi</div>
            <div class="kpi-value">{{ uptimeText }}</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-label">Aksi</div>
            <div><button @click="confirmDisconnect = true" class="btn btn-danger text-sm">Putuskan koneksi</button></div>
          </div>
        </div>

        <!-- Belum dikonfigurasi -->
        <div v-else-if="!status.configured" class="alert-warning">
          <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
          <span>{{ status.note }} Isi <b>BAILEYS_API_URL</b> di environment / docker-compose (default <span class="mono">http://baileys:3001</span>), lalu refresh halaman ini.</span>
        </div>

        <!-- Sidecar mati -->
        <div v-else-if="!status.reachable" class="alert-negative">
          <Icon name="wifi-off" :size="15" class="mt-0.5 shrink-0" />
          <span>{{ status.note }}</span>
        </div>

        <!-- Menunggu pairing: QR -->
        <div v-else class="qr-grid">
          <div class="qr-box">
            <div v-if="qrLoading && !qrDataUrl" class="card-label">Menyiapkan QR…</div>
            <img v-else-if="qrDataUrl" :src="qrDataUrl" alt="QR pairing WhatsApp" class="qr-img" />
            <div v-else class="card-label">QR belum tersedia — tunggu beberapa detik.</div>
            <div class="card-label mt-2">QR refresh otomatis. Status dicek tiap 8 detik.</div>
          </div>
          <div>
            <h3 class="section-title mb-2">Cara pairing</h3>
            <ol class="steps">
              <li>Buka WhatsApp di <b>HP nomor testing</b> (jangan nomor utama).</li>
              <li>Masuk ke <b>Pengaturan → Perangkat Tertaut → Tautkan Perangkat</b>.</li>
              <li>Scan QR di samping. Tunggu status berubah jadi <b>Terhubung</b>.</li>
            </ol>
            <button @click="loadStatus(); loadQr()" class="btn btn-tertiary text-sm mt-3">
              <Icon name="refresh" :size="14" /> Muat ulang QR
            </button>
          </div>
        </div>
      </template>

      <div class="alert-warning mt-4">
        <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
        <span>Jalur non-resmi memakai protokol WhatsApp Web — <b>jangan pakai nomor WA utama/pribadi</b>, gunakan nomor khusus testing (risiko banned permanen).</span>
      </div>
    </div>

    <div class="card card-pad">
      <h2 class="section-title mb-2">Jalur resmi — Meta Cloud API</h2>
      <p class="card-label">Jalur resmi tidak butuh pairing QR. Kredensial (token, phone number ID) diatur di <b>Pengaturan</b>. Selama kredensial valid, campaign dengan provider "Resmi" langsung bisa dikirim.</p>
    </div>

    <ConfirmDialog
      :open="confirmDisconnect"
      title="Putuskan koneksi WA?"
      message="Sesi Baileys akan dihapus. Pengiriman jalur non-resmi berhenti sampai Anda pairing ulang dengan scan QR."
      confirm-label="Ya, putuskan"
      danger
      :loading="disconnecting"
      @confirm="doDisconnect"
      @cancel="confirmDisconnect = false"
    />
  </div>
</template>

<style scoped>
.qr-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 24px;
  align-items: start;
  margin-top: 12px;
}
.qr-box {
  background: #fff;
  border: 1px solid var(--rule);
  border-radius: var(--radius-card);
  padding: 16px;
  text-align: center;
}
.qr-img {
  width: 280px;
  height: 280px;
  display: block;
}
.steps {
  margin: 0;
  padding-left: 20px;
  display: grid;
  gap: 8px;
  font-size: 14px;
  color: var(--muted);
}
.steps b { color: var(--text); }
@media (max-width: 640px) {
  .qr-grid { grid-template-columns: 1fr; }
  .qr-box { justify-self: center; }
}
</style>
