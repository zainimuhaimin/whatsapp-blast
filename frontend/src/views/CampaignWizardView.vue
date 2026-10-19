<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { campaignsApi, templatesApi, contactsApi, testNumbersApi, settingsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import {
  formatRupiah, formatNumber, formatDuration, extractVariables, wrapVar,
  estimateDuration, estimateCost, DEFAULT_PRICE_PER_MESSAGE_IDR, truncate, formatPhone,
} from '../utils/format'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const router = useRouter()
const route = useRoute()
const toast = useToast()

const STEPS = [
  { n: 1, label: 'Info Dasar' },
  { n: 2, label: 'Template' },
  { n: 3, label: 'Input AI' },
  { n: 4, label: 'Mapping' },
  { n: 5, label: 'Penerima' },
  { n: 6, label: 'Review' },
]

const step = ref(1)
const campaign = ref(null)
const loading = ref(false)
const stepErrors = ref([])

/* ------------------------- Langkah 1: info dasar ------------------------ */
const form = ref({
  name: '',
  provider: 'official', // 'official' | 'unofficial'
  is_test_mode: false,
  send_at: '', // datetime-local string
})

function sendAtISO() {
  if (!form.value.send_at) return null
  const d = new Date(form.value.send_at)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

/* ------------------------- Langkah 2: template -------------------------- */
const templates = ref([])
const expandedTemplate = ref(null)
const versionsCache = ref({}) // templateId -> versions[]
const selectedVersion = ref(null) // {template, version}
const versionsLoading = ref(false)

async function loadTemplates() {
  const { items } = await templatesApi.list()
  templates.value = items
}

async function toggleTemplate(t) {
  if (expandedTemplate.value?.id === t.id) {
    expandedTemplate.value = null
    return
  }
  expandedTemplate.value = t
  if (!versionsCache.value[t.id]) {
    versionsLoading.value = true
    try {
      const { items } = await templatesApi.versions(t.id)
      versionsCache.value[t.id] = items
    } finally {
      versionsLoading.value = false
    }
  }
}

function pickVersion(t, v) {
  selectedVersion.value = { template: t, version: v }
}

const selectedVariables = computed(() =>
  extractVariables(selectedVersion.value?.version?.body || '')
)

/* --------------------------- Langkah 3: AI ------------------------------ */
const aiText = ref('')
const aiLoading = ref(false)
const aiResult = ref(null) // {variable: value}
const aiNote = ref('')     // note bila AI tidak tersedia

async function runAiExtract() {
  if (!aiText.value.trim()) {
    toast.warning('Isi dulu teks bebas sebelum mengekstrak dengan AI.')
    return
  }
  if (!campaign.value) return
  aiLoading.value = true
  aiResult.value = null
  aiNote.value = ''
  try {
    const data = await campaignsApi.aiExtract(campaign.value.id, aiText.value.trim())
    aiResult.value = data.values || data.candidates || data.variables || data.mapping || {}
    if (data.ai_available === false || data.note) {
      aiNote.value = data.note || 'Layanan AI tidak tersedia saat ini — Anda tetap bisa mengisi nilai variabel secara manual di langkah 4.'
    }
    const n = Object.keys(aiResult.value || {}).length
    toast.success(n ? `AI mengekstrak ${n} nilai variabel.` : 'AI tidak menemukan nilai yang cocok — isi manual di langkah 4.')
  } catch (e) {
    aiNote.value = 'Layanan AI tidak tersedia saat ini — Anda tetap bisa mengisi nilai variabel secara manual di langkah 4.'
  } finally {
    aiLoading.value = false
  }
}

/* -------------------------- Langkah 4: mapping -------------------------- */
const mappings = ref([]) // [{variable_name, source: 'contact'|'campaign', contact_field, value}]

function smartDefault(varName) {
  const v = varName.toLowerCase()
  if (v.includes('name') || v.includes('nama')) return { source: 'contact', contact_field: 'name' }
  if (v.includes('phone') || v.includes('telp') || v === 'hp' || v.includes('nomor')) return { source: 'contact', contact_field: 'phone' }
  if (v.includes('tag')) return { source: 'contact', contact_field: 'tag' }
  return { source: 'campaign', contact_field: null }
}

async function initMappings() {
  let existing = []
  try {
    const data = await campaignsApi.mappings(campaign.value.id)
    existing = Array.isArray(data) ? data : data.mappings || []
  } catch { /* biarkan default */ }
  const byName = Object.fromEntries(existing.map((m) => [m.variable_name, m]))
  mappings.value = selectedVariables.value.map((varName) => {
    const prev = byName[varName]
    if (prev) {
      return {
        variable_name: varName,
        source: prev.source || 'campaign',
        contact_field: prev.contact_field || 'name',
        value: prev.value ?? (aiResult.value?.[varName] ?? ''),
      }
    }
    const d = smartDefault(varName)
    return {
      variable_name: varName,
      source: d.source,
      contact_field: d.contact_field || 'name',
      value: d.source === 'campaign' ? (aiResult.value?.[varName] ?? '') : '',
    }
  })
}

const mappingErrors = computed(() => {
  const errs = []
  for (const m of mappings.value) {
    if (m.source === 'contact' && !['name', 'phone', 'tag'].includes(m.contact_field)) {
      errs.push(`Variabel {{${m.variable_name}}}: pilih field kontak (nama/nomor/tag).`)
    }
    if (m.source === 'campaign' && !String(m.value ?? '').trim()) {
      errs.push(`Variabel {{${m.variable_name}}}: nilai campaign belum diisi.`)
    }
  }
  return errs
})

/* -------------------------- Langkah 5: penerima -------------------------- */
const allContacts = ref([])
const contactSearch = ref('')
const selectedContacts = ref(new Set())
const testNums = ref([])
const recipientsLoading = ref(false)

const visibleContacts = computed(() => {
  const q = contactSearch.value.trim().toLowerCase()
  return allContacts.value.filter((c) => {
    if (!q) return true
    return (c.name || '').toLowerCase().includes(q) || (c.phone || '').includes(q)
  })
})

const selectableCount = computed(() => allContacts.value.filter((c) => !c.is_blacklisted).length)

function toggleContact(id) {
  const s = new Set(selectedContacts.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedContacts.value = s
}

function toggleAll(checked) {
  if (checked) {
    selectedContacts.value = new Set(
      visibleContacts.value.filter((c) => !c.is_blacklisted).map((c) => c.id)
    )
  } else {
    selectedContacts.value = new Set()
  }
}

async function loadRecipientsData() {
  recipientsLoading.value = true
  try {
    if (form.value.is_test_mode) {
      const { items } = await testNumbersApi.list()
      testNums.value = (items || []).filter((t) => t.is_active !== false)
    } else {
      const { items } = await contactsApi.list({ limit: 1000 })
      allContacts.value = items || []
    }
  } finally {
    recipientsLoading.value = false
  }
}

/* Tambah nomor cepat: otomatis tersimpan sebagai kontak (dedup by nomor) */
const quickName = ref('')
const quickPhone = ref('')
const quickAdding = ref(false)

async function quickAddContact() {
  const phone = quickPhone.value.trim()
  if (!phone || quickAdding.value) return
  quickAdding.value = true
  try {
    const { contact, created } = await contactsApi.findOrCreate({
      phone,
      name: quickName.value.trim() || undefined,
    })
    const { items } = await contactsApi.list({ limit: 1000 })
    allContacts.value = items || []
    if (contact && !contact.is_blacklisted) {
      const s = new Set(selectedContacts.value)
      s.add(contact.id)
      selectedContacts.value = s
    }
    toast.success(
      created
        ? `Kontak "${contact.name}" tersimpan & otomatis terpilih ✓`
        : `Nomor sudah terdaftar — kontak "${contact.name}" otomatis terpilih ✓`
    )
    quickName.value = ''
    quickPhone.value = ''
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message || 'Gagal menambah nomor'
    toast.error(Array.isArray(msg) ? msg.map((m) => m.msg || m).join('; ') : msg)
  } finally {
    quickAdding.value = false
  }
}

/* --------------------------- Langkah 6: review -------------------------- */
const review = ref(null)
const reviewLoading = ref(false)
const settings = ref({})
const showConfirmDialog = ref(false)
const confirmMode = ref('blast') // 'blast' | 'schedule'
const confirming = ref(false)

async function loadReview() {
  reviewLoading.value = true
  try {
    const [rev, s] = await Promise.all([
      campaignsApi.review(campaign.value.id),
      settingsApi.list().catch(() => ({})),
    ])
    review.value = rev
    settings.value = s && typeof s === 'object' ? s : {}
  } finally {
    reviewLoading.value = false
  }
}

// Normalisasi payload review (defensif terhadap variasi bentuk backend)
const rv = computed(() => review.value || {})
const rvCampaign = computed(() => rv.value.campaign || campaign.value || {})
const rvTotal = computed(() => Number(rv.value.total_recipients ?? rv.value.total ?? 0))
const rvTable = computed(() => rv.value.recipient_preview || rv.value.table || rv.value.rows || rv.value.recipients || [])
const rvSamples = computed(() => rv.value.samples || rv.value.sample_messages || [])
const rvErrors = computed(() => rv.value.validation_errors || rv.value.errors || [])
const rvDurationSec = computed(() => {
  if (rv.value.duration_estimate_seconds != null) return Number(rv.value.duration_estimate_seconds)
  if (rv.value.eta_seconds != null) return Number(rv.value.eta_seconds)
  const rate = Number(settings.value['wa.rate_limit_per_hour']?.value ?? settings.value['wa.rate_limit_per_hour'])
  return estimateDuration(rvTotal.value, 10, rate || null)
})
const rvCategory = computed(() =>
  rv.value.provider_category || selectedVersion.value?.version?.provider_category || 'marketing'
)
const rvCost = computed(() => {
  if (rvCampaign.value.provider === 'unofficial') return 0
  if (rv.value.estimated_cost_idr != null) return Number(rv.value.estimated_cost_idr)
  if (rv.value.cost_estimate != null) return Number(rv.value.cost_estimate)
  const priceMap = settings.value['wa.price_per_message_idr']?.value
    || settings.value['wa.price_per_message_idr']
    || DEFAULT_PRICE_PER_MESSAGE_IDR
  return estimateCost(rvTotal.value, rvCategory.value, priceMap)
})
const rvPricePerMsg = computed(() => {
  if (rv.value.price_per_message != null) return Number(rv.value.price_per_message)
  const priceMap = settings.value['wa.price_per_message_idr']?.value
    || settings.value['wa.price_per_message_idr']
    || DEFAULT_PRICE_PER_MESSAGE_IDR
  return Number(priceMap?.[rvCategory.value] ?? 0)
})
const rvVarNames = computed(() => {
  const t = rvTable.value[0]
  if (t?.values) return Object.keys(t.values)
  return selectedVariables.value
})
const hasSendAt = computed(() => !!sendAtISO())

/* ------------------------------ navigasi ------------------------------- */
function validateStep(n) {
  const errs = []
  if (n === 1) {
    if (!form.value.name.trim()) errs.push('Nama campaign wajib diisi.')
  }
  if (n === 2) {
    if (!selectedVersion.value) errs.push('Pilih salah satu versi template.')
  }
  if (n === 4) {
    errs.push(...mappingErrors.value)
  }
  if (n === 5 && !form.value.is_test_mode) {
    if (selectedContacts.value.size === 0) errs.push('Pilih minimal satu penerima.')
  }
  if (n === 5 && form.value.is_test_mode) {
    if (!testNums.value.length) errs.push('Mode test aktif tetapi tidak ada nomor test yang aktif. Tambahkan di menu Nomor Test.')
  }
  return errs
}

async function ensureCampaign() {
  // Membuat/memperbarui draft campaign di langkah 2
  const payload = {
    name: form.value.name.trim(),
    template_version_id: selectedVersion.value.version.id,
    provider: form.value.provider,
    is_test_mode: form.value.is_test_mode,
    send_at: sendAtISO(),
  }
  if (!campaign.value) {
    campaign.value = await campaignsApi.create(payload)
    toast.success(`Draft campaign “${campaign.value.name}” dibuat.`)
  } else {
    try {
      campaign.value = await campaignsApi.update(campaign.value.id, payload)
    } catch {
      // Backend mungkin menolak field tertentu pada draft yang sudah ada;
      // lanjutkan dengan data lokal bila update gagal sebagian.
    }
  }
}

async function next() {
  stepErrors.value = validateStep(step.value)
  if (stepErrors.value.length) return
  loading.value = true
  try {
    if (step.value === 2) {
      await ensureCampaign()
    }
    if (step.value === 4) {
      await initMappingsIfNeeded()
      await campaignsApi.saveMappings(campaign.value.id, mappings.value)
      toast.success('Mapping variabel disimpan.')
    }
    if (step.value === 5) {
      const ids = form.value.is_test_mode ? [] : [...selectedContacts.value]
      const res = await campaignsApi.buildRecipients(campaign.value.id, ids)
      const built = res.built ?? res.count ?? res.total ?? ids.length
      toast.success(
        form.value.is_test_mode
          ? `Penerima mode test dibangun (${testNums.value.length} nomor test).`
          : `${built} penerima ditambahkan (blacklist & duplikat otomatis dilewati).`
      )
    }
    if (step.value < 6) {
      step.value += 1
      if (step.value === 4) await initMappings()
      if (step.value === 5) await loadRecipientsData()
      if (step.value === 6) await loadReview()
      window.scrollTo({ top: 0 })
    }
  } finally {
    loading.value = false
  }
}

async function initMappingsIfNeeded() {
  if (!mappings.value.length) await initMappings()
}

function back() {
  if (step.value > 1) {
    step.value -= 1
    window.scrollTo({ top: 0 })
  }
}

function goTo(n) {
  // Lompat ke langkah sebelumnya bebas; ke depan hanya bila sudah ada campaign
  if (n < step.value || (campaign.value && n <= 6)) {
    step.value = n
    window.scrollTo({ top: 0 })
  }
}

/* --------------------------- konfirmasi blast --------------------------- */
function openConfirm(mode) {
  confirmMode.value = mode
  showConfirmDialog.value = true
}

async function doConfirm() {
  confirming.value = true
  try {
    const res = await campaignsApi.confirm(campaign.value.id)
    const status = res.status || res.campaign?.status
    showConfirmDialog.value = false
    if (status === 'scheduled') {
      toast.success('Campaign dijadwalkan. Pengiriman dimulai otomatis pada waktunya.')
    } else {
      toast.success('Campaign dikonfirmasi — pengiriman dimulai.')
    }
    router.push(`/campaigns/${campaign.value.id}`)
  } finally {
    confirming.value = false
  }
}

const confirmDialogText = computed(() => {
  const total = rvTotal.value
  if (confirmMode.value === 'schedule') {
    return `Campaign “${rvCampaign.value.name}” akan DIJADWALKAN ke ${total} penerima pada waktu yang ditentukan, via jalur ${rvCampaign.value.provider === 'official' ? 'RESMI' : 'NON-RESMI'}. Lanjutkan?`
  }
  return `Campaign “${rvCampaign.value.name}” akan DIKIRIM ke ${total} penerima via jalur ${rvCampaign.value.provider === 'official' ? 'RESMI' : 'NON-RESMI'}${rvCampaign.value.provider === 'official' ? ` dengan estimasi biaya ${formatRupiah(rvCost.value)}` : ''}. Tindakan ini tidak bisa dibatalkan untuk pesan yang sudah terkirim. Lanjutkan?`
})

onMounted(async () => {
  await loadTemplates()
  // Lanjutkan draft yang sudah ada (mis. kembali dari detail campaign)
  if (route.query.campaign) {
    try {
      const c = await campaignsApi.get(route.query.campaign)
      campaign.value = c
      form.value.name = c.name || ''
      form.value.provider = c.provider || 'official'
      form.value.is_test_mode = !!c.is_test_mode
      form.value.send_at = c.send_at ? new Date(c.send_at).toISOString().slice(0, 16) : ''
    } catch { /* abaikan, mulai wizard baru */ }
  }
})
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <div class="mb-6">
      <h1 class="text-2xl font-bold">Campaign Baru</h1>
      <p class="text-sm text-slate-500">Wizard 6 langkah: info → template → AI → mapping → penerima → review</p>
    </div>

    <!-- Step indicator -->
    <ol class="flex items-center gap-1 mb-8 overflow-x-auto thin-scroll">
      <li v-for="s in STEPS" :key="s.n" class="flex items-center shrink-0">
        <button
          @click="goTo(s.n)"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
          :class="s.n === step
            ? 'bg-emerald-600 text-white font-semibold'
            : s.n < step
              ? 'text-emerald-700 hover:bg-emerald-50'
              : 'text-slate-400'"
        >
          <span
            class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
            :class="s.n === step ? 'bg-white text-emerald-700' : s.n < step ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'"
          >
            {{ s.n < step ? '✓' : s.n }}
          </span>
          {{ s.label }}
        </button>
        <span v-if="s.n < STEPS.length" class="mx-1 text-slate-300">›</span>
      </li>
    </ol>

    <div v-if="stepErrors.length" class="mb-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
      <div class="font-semibold text-red-700 text-sm mb-1">Perbaiki dulu:</div>
      <ul class="list-disc list-inside text-sm text-red-600 space-y-0.5">
        <li v-for="(e, i) in stepErrors" :key="i">{{ e }}</li>
      </ul>
    </div>

    <!-- ================= LANGKAH 1: INFO DASAR ================= -->
    <section v-if="step === 1" class="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
      <h2 class="text-lg font-semibold">1. Info Dasar Campaign</h2>

      <div>
        <label class="field-label">Nama campaign *</label>
        <input v-model="form.name" class="field-input" placeholder="mis. Promo Akhir Tahun" />
      </div>

      <div>
        <label class="field-label">Jalur pengiriman (provider)</label>
        <div class="grid md:grid-cols-2 gap-3">
          <label
            class="border rounded-xl p-4 cursor-pointer transition-colors"
            :class="form.provider === 'official' ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500' : 'border-slate-300 hover:border-slate-400'"
          >
            <div class="flex items-center gap-2 font-semibold text-sm">
              <input type="radio" v-model="form.provider" value="official" class="accent-emerald-600" />
              ✅ Resmi — Meta Cloud API
            </div>
            <ul class="text-xs text-slate-600 mt-2 space-y-1 ml-6">
              <li>• Biaya ± Rp 627,33/pesan marketing (per pesan ter-deliver)</li>
              <li>• Wajib template yang disetujui Meta</li>
              <li>• Risiko banned rendah bila penerima opt-in</li>
            </ul>
          </label>
          <label
            class="border rounded-xl p-4 cursor-pointer transition-colors"
            :class="form.provider === 'unofficial' ? 'border-red-500 bg-red-50 ring-1 ring-red-500' : 'border-slate-300 hover:border-slate-400'"
          >
            <div class="flex items-center gap-2 font-semibold text-sm">
              <input type="radio" v-model="form.provider" value="unofficial" class="accent-red-600" />
              ⚡ Non-resmi — Baileys (gratis, self-hosted)
            </div>
            <ul class="text-xs text-slate-600 mt-2 space-y-1 ml-6">
              <li>• <b>Rp 0</b> — free tier 1.000 pesan/bulan</li>
              <li>• Teks bebas, tanpa approval template</li>
              <li>• Cocok untuk testing template/variabel/AI</li>
            </ul>
          </label>
        </div>

        <div v-if="form.provider === 'unofficial'" class="mt-3 bg-red-50 border-2 border-red-300 rounded-xl px-4 py-3">
          <div class="font-bold text-red-700 text-sm">⚠️ PERINGATAN RISIKO BANNED</div>
          <p class="text-sm text-red-600 mt-1">
            Jalur non-resmi bukan API resmi WhatsApp. <b>Nomor yang dipakai bisa di-banned WhatsApp.</b>
            Jangan gunakan nomor WA utama/pribadi — pakai nomor testing khusus. Disarankan hanya untuk testing,
            bukan blast produksi.
          </p>
        </div>
        <div v-else class="mt-3 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm text-emerald-800">
          ℹ️ Jalur resmi memakai tarif Meta per pesan ter-deliver (Marketing Rp 627,33 · Utility Rp 366,65 · Authentication Rp 366,65 · Service Rp 356,65).
          Estimasi biaya total dihitung di halaman review.
        </div>
      </div>

      <div class="flex items-start gap-3 border border-slate-200 rounded-xl p-4">
        <input id="testmode" type="checkbox" v-model="form.is_test_mode" class="mt-1 accent-amber-500 w-4 h-4" />
        <label for="testmode" class="text-sm">
          <span class="font-semibold">🧪 Mode test</span>
          <span class="text-slate-600 block mt-0.5">Bila aktif, pesan HANYA dikirim ke nomor test terdaftar (bukan ke kontak asli). Aman untuk uji coba.</span>
        </label>
      </div>

      <div>
        <label class="field-label">Jadwal kirim (opsional)</label>
        <input v-model="form.send_at" type="datetime-local" class="field-input !w-auto" />
        <div class="field-hint">Kosongkan untuk kirim segera setelah konfirmasi. Bila diisi, campaign berstatus terjadwal.</div>
      </div>
    </section>

    <!-- ================= LANGKAH 2: TEMPLATE ================= -->
    <section v-if="step === 2" class="space-y-4">
      <div class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-lg font-semibold mb-1">2. Pilih Versi Template</h2>
        <p class="text-sm text-slate-500 mb-4">Versi yang dipilih di-pin ke campaign (immutable — tidak berubah walau template diedit).</p>

        <div v-if="!templates.length" class="text-sm text-slate-400 text-center py-6">
          Belum ada template. <RouterLink to="/templates" class="text-emerald-700 underline">Buat template dulu</RouterLink>.
        </div>

        <div v-for="t in templates" :key="t.id" class="border border-slate-200 rounded-xl mb-3 overflow-hidden">
          <button @click="toggleTemplate(t)" class="w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-50 text-left">
            <span class="text-lg">{{ expandedTemplate?.id === t.id ? '▾' : '▸' }}</span>
            <span class="font-medium">{{ t.name }}</span>
            <span v-if="t.description" class="text-xs text-slate-400 truncate">{{ truncate(t.description, 60) }}</span>
          </button>
          <div v-if="expandedTemplate?.id === t.id" class="border-t border-slate-100 px-4 py-3 space-y-2 bg-slate-50/50">
            <div v-if="versionsLoading" class="text-sm text-slate-500">Memuat versi…</div>
            <label
              v-for="v in (versionsCache[t.id] || [])"
              :key="v.id || v.version_number"
              class="block border rounded-xl p-3 cursor-pointer bg-white transition-colors"
              :class="selectedVersion?.version?.id === v.id ? 'border-emerald-500 ring-1 ring-emerald-500' : 'border-slate-200 hover:border-slate-300'"
            >
              <div class="flex flex-wrap items-center gap-2">
                <input
                  type="radio"
                  :checked="selectedVersion?.version?.id === v.id"
                  @change="pickVersion(t, v)"
                  class="accent-emerald-600"
                />
                <span class="font-semibold text-sm">Versi {{ v.version_number }}</span>
                <StatusPill :status="v.approval_status || 'draft'" />
                <span v-if="v.provider_category" class="text-xs bg-slate-100 px-2 py-0.5 rounded-full">{{ v.provider_category }}</span>
                <span class="ml-auto text-xs text-slate-400">{{ (v.variables || []).length }} variabel</span>
              </div>
              <pre class="whitespace-pre-wrap text-xs text-slate-600 mt-2 font-sans">{{ truncate(v.body, 220) }}</pre>
              <div
                v-if="form.provider === 'official' && (v.approval_status || 'draft') !== 'approved'"
                class="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-2 py-1"
              >
                ⚠️ Jalur resmi mewajibkan template berstatus <b>approved</b> oleh Meta — versi ini belum bisa dipakai blast produksi.
              </div>
            </label>
          </div>
        </div>

        <div v-if="selectedVersion" class="mt-4 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm">
          ✅ Terpilih: <b>{{ selectedVersion.template.name }}</b> — versi {{ selectedVersion.version.version_number }}
          <span class="text-slate-500">({{ selectedVariables.length }} variabel: {{ selectedVariables.map(v => wrapVar(v)).join(', ') || '–' }})</span>
        </div>
      </div>
    </section>

    <!-- ================= LANGKAH 3: INPUT AI ================= -->
    <section v-if="step === 3" class="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
      <h2 class="text-lg font-semibold">3. Input AI — Ekstraksi Variabel</h2>
      <p class="text-sm text-slate-500">
        Tulis info campaign dengan bahasa bebas (mis. “Promo akhir tahun diskon 50% berlaku sampai 31 Desember, kode: HEMAT50”).
        AI akan mengekstrak nilai untuk variabel template. Hasilnya bisa Anda edit di langkah berikutnya.
      </p>

      <div>
        <label class="field-label">Teks bebas</label>
        <textarea v-model="aiText" rows="6" class="field-input" placeholder="Contoh: Promo cuci gudang! Diskon 70% semua fashion, hanya tanggal 12-12. Gratis ongkir min. belanja 100rb."></textarea>
      </div>

      <button
        @click="runAiExtract"
        :disabled="aiLoading"
        class="px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white font-semibold text-sm disabled:opacity-50"
      >
        {{ aiLoading ? '🤖 Menganalisis…' : '🤖 Ekstrak dengan AI' }}
      </button>

      <div v-if="aiNote" class="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
        ⚠️ {{ aiNote }}
      </div>

      <div v-if="aiResult && Object.keys(aiResult).length" class="border border-slate-200 rounded-xl overflow-hidden">
        <div class="bg-slate-50 px-4 py-2 text-sm font-semibold">Hasil ekstraksi AI</div>
        <table class="w-full text-sm">
          <tbody>
            <tr v-for="(val, key) in aiResult" :key="key" class="border-t border-slate-100">
              <td class="px-4 py-2 font-mono text-emerald-800 w-40">{{ wrapVar(key) }}</td>
              <td class="px-4 py-2">{{ val || '–' }}</td>
            </tr>
          </tbody>
        </table>
        <div class="px-4 py-2 text-xs text-slate-500 bg-slate-50">Nilai ini menjadi prefill di langkah Mapping dan masih bisa diubah.</div>
      </div>

      <button @click="step = 4; initMappings()" class="text-sm text-slate-500 underline hover:text-slate-700">
        Lewati — isi manual di langkah Mapping →
      </button>
    </section>

    <!-- ================= LANGKAH 4: MAPPING ================= -->
    <section v-if="step === 4" class="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
      <h2 class="text-lg font-semibold">4. Mapping Variabel</h2>
      <p class="text-sm text-slate-500">
        Tentukan sumber tiap variabel: <b>field kontak</b> (diambil dari data tiap penerima — {{name}} dsb, bukan dari AI)
        atau <b>nilai campaign</b> (sama untuk semua penerima, dari hasil AI dan bisa diedit).
      </p>

      <div v-if="!mappings.length" class="text-sm text-slate-400 text-center py-6">Memuat variabel…</div>

      <div v-for="m in mappings" :key="m.variable_name" class="border border-slate-200 rounded-xl p-4 space-y-3">
        <div class="font-mono font-semibold text-emerald-800">{{ wrapVar(m.variable_name) }}</div>
        <div class="flex flex-wrap gap-4 text-sm">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" v-model="m.source" value="contact" class="accent-emerald-600" />
            👤 Field kontak
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" v-model="m.source" value="campaign" class="accent-emerald-600" />
            📣 Nilai campaign
          </label>
        </div>
        <div v-if="m.source === 'contact'">
          <label class="field-label">Field kontak</label>
          <select v-model="m.contact_field" class="field-input !w-auto">
            <option value="name">Nama (name)</option>
            <option value="phone">Nomor (phone)</option>
            <option value="tag">Tag</option>
          </select>
        </div>
        <div v-else>
          <label class="field-label">Nilai (berlaku untuk semua penerima)</label>
          <input v-model="m.value" class="field-input" :placeholder="`Nilai untuk {{${m.variable_name}}}`" />
          <div v-if="aiResult?.[m.variable_name]" class="field-hint">💡 Prefill dari AI: “{{ aiResult[m.variable_name] }}” — silakan ubah bila perlu.</div>
        </div>
      </div>
    </section>

    <!-- ================= LANGKAH 5: PENERIMA ================= -->
    <section v-if="step === 5" class="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
      <h2 class="text-lg font-semibold">5. Pilih Penerima</h2>

      <div v-if="form.is_test_mode">
        <div class="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800 mb-4">
          🧪 <b>Mode test aktif</b> — penerima otomatis memakai nomor test terdaftar. Kontak asli tidak akan menerima pesan.
        </div>
        <div v-if="recipientsLoading" class="text-sm text-slate-500">Memuat nomor test…</div>
        <ul v-else class="space-y-2">
          <li v-for="t in testNums" :key="t.id" class="flex items-center gap-3 border border-slate-200 rounded-lg px-4 py-2.5 text-sm">
            <span class="text-emerald-600">✓</span>
            <span class="font-medium">{{ t.label }}</span>
            <span class="font-mono text-slate-500">{{ formatPhone(t.phone) }}</span>
          </li>
        </ul>
        <div v-if="!recipientsLoading && !testNums.length" class="text-sm text-slate-400">
          Belum ada nomor test aktif. Tambahkan di menu <RouterLink to="/test-numbers" class="text-emerald-700 underline">Nomor Test</RouterLink>.
        </div>
      </div>

      <div v-else>
        <div class="flex flex-wrap items-center gap-3">
          <input v-model="contactSearch" type="search" placeholder="🔍 Cari nama / nomor…" class="field-input !w-64" />
          <span class="text-sm text-slate-500">{{ selectedContacts.size }} dari {{ selectableCount }} kontak dipilih</span>
          <button @click="toggleAll(true)" class="text-sm text-emerald-700 underline">Pilih semua</button>
          <button @click="toggleAll(false)" class="text-sm text-slate-500 underline">Batalkan semua</button>
        </div>
        <div class="text-xs text-slate-500">🚫 Kontak blacklist otomatis dikecualikan dan tidak bisa dipilih.</div>

        <!-- Tambah nomor cepat: otomatis tersimpan sebagai kontak (dedup 0812…/​+62812…) -->
        <div class="border border-dashed border-emerald-300 bg-emerald-50/50 rounded-xl p-4">
          <div class="text-sm font-medium mb-2">⚡ Tambah nomor cepat <span class="font-normal text-slate-500">— langsung tersimpan sebagai kontak & terpilih</span></div>
          <div class="flex flex-wrap gap-2">
            <input v-model="quickName" type="text" placeholder="Nama PIC (opsional)" class="field-input !w-52" />
            <input v-model="quickPhone" type="tel" placeholder="Nomor WA, mis. 0812…" class="field-input !w-52 font-mono" @keyup.enter="quickAddContact" />
            <button @click="quickAddContact" :disabled="quickAdding || !quickPhone.trim()" class="btn-primary disabled:opacity-50">
              {{ quickAdding ? 'Menyimpan…' : '+ Tambah' }}
            </button>
          </div>
          <div class="text-xs text-slate-500 mt-1.5">Nomor otomatis diseragamkan — <span class="font-mono">0812…</span>, <span class="font-mono">+62812…</span>, <span class="font-mono">62812…</span> dianggap nomor yang sama, tidak akan dobel.</div>
        </div>

        <div v-if="recipientsLoading" class="text-sm text-slate-500 text-center py-6">Memuat kontak…</div>
        <div v-else class="border border-slate-200 rounded-xl divide-y divide-slate-100 max-h-96 overflow-y-auto thin-scroll">
          <label
            v-for="c in visibleContacts"
            :key="c.id"
            class="flex items-center gap-3 px-4 py-2.5 text-sm"
            :class="c.is_blacklisted ? 'bg-slate-50 opacity-60' : 'hover:bg-slate-50 cursor-pointer'"
          >
            <input
              type="checkbox"
              :checked="selectedContacts.has(c.id)"
              :disabled="c.is_blacklisted"
              @change="toggleContact(c.id)"
              class="accent-emerald-600 w-4 h-4"
            />
            <span class="font-medium flex-1">{{ c.name }}</span>
            <span class="font-mono text-slate-500 text-xs">{{ formatPhone(c.phone) }}</span>
            <span v-if="c.tag" class="text-xs bg-slate-100 px-2 py-0.5 rounded-full">{{ c.tag }}</span>
            <span v-if="c.is_blacklisted" class="text-xs font-semibold text-red-600">🚫 blacklist — dikecualikan</span>
          </label>
          <div v-if="!visibleContacts.length" class="px-4 py-6 text-sm text-slate-400 text-center">
            Tidak ada kontak yang cocok.
          </div>
        </div>
      </div>
    </section>

    <!-- ================= LANGKAH 6: REVIEW ================= -->
    <section v-if="step === 6" class="space-y-4">
      <h2 class="text-lg font-semibold">6. Review & Konfirmasi</h2>

      <div v-if="reviewLoading" class="bg-white rounded-xl border border-slate-200 p-10 text-center text-sm text-slate-500">
        Menyusun pratinjau campaign…
      </div>

      <template v-else-if="review">
        <!-- Banner mode test -->
        <div v-if="rvCampaign.is_test_mode" class="bg-amber-100 border-2 border-amber-400 rounded-xl px-4 py-3">
          <div class="font-bold text-amber-800">🧪 MODE TEST AKTIF</div>
          <div class="text-sm text-amber-700">Pesan hanya dikirim ke nomor test terdaftar — bukan ke kontak asli.</div>
        </div>

        <!-- Banner risiko banned -->
        <div v-if="rvCampaign.provider === 'unofficial'" class="bg-red-100 border-2 border-red-400 rounded-xl px-4 py-3">
          <div class="font-bold text-red-700">⚠️ JALUR NON-RESMI — RISIKO BANNED</div>
          <div class="text-sm text-red-600">
            Pengiriman via jalur tidak resmi. Nomor pengirim bisa di-banned WhatsApp. Pastikan memakai nomor testing khusus,
            bukan nomor utama/pribadi.
          </div>
        </div>

        <!-- Ringkasan -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div class="bg-white rounded-xl border border-slate-200 p-4">
            <div class="text-xs text-slate-500">Total penerima</div>
            <div class="text-2xl font-bold mt-1">{{ formatNumber(rvTotal) }}</div>
          </div>
          <div class="bg-white rounded-xl border border-slate-200 p-4">
            <div class="text-xs text-slate-500">Estimasi durasi kirim</div>
            <div class="text-2xl font-bold mt-1">{{ formatDuration(rvDurationSec) }}</div>
            <div class="text-xs text-slate-400 mt-0.5">±10 dtk/pesan + batas rate</div>
          </div>
          <div class="bg-white rounded-xl border border-slate-200 p-4">
            <div class="text-xs text-slate-500">Estimasi biaya</div>
            <div class="text-2xl font-bold mt-1" :class="rvCost === 0 ? 'text-emerald-600' : ''">
              {{ rvCampaign.provider === 'unofficial' ? 'Rp 0 (jalur gratis)' : formatRupiah(rvCost) }}
            </div>
            <div v-if="rvCampaign.provider === 'official'" class="text-xs text-slate-400 mt-0.5">
              {{ formatRupiah(rvPricePerMsg) }}/pesan · kategori {{ rvCategory }}
            </div>
          </div>
          <div class="bg-white rounded-xl border border-slate-200 p-4">
            <div class="text-xs text-slate-500">Template</div>
            <div class="font-semibold mt-1 truncate">{{ selectedVersion?.template?.name || '–' }}</div>
            <div class="text-xs text-slate-400 mt-0.5">
              v{{ selectedVersion?.version?.version_number }} · <StatusPill :status="rvCampaign.provider" />
            </div>
          </div>
        </div>

        <!-- Error validasi -->
        <div v-if="rvErrors.length" class="bg-red-50 border-2 border-red-300 rounded-xl px-4 py-3">
          <div class="font-bold text-red-700 text-sm mb-1">⛔ Campaign belum bisa dikonfirmasi — perbaiki dulu:</div>
          <ul class="list-disc list-inside text-sm text-red-600 space-y-0.5">
            <li v-for="(e, i) in rvErrors" :key="i">{{ typeof e === 'string' ? e : e.message || JSON.stringify(e) }}</li>
          </ul>
        </div>

        <!-- Tabel penerima × variabel -->
        <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-200 font-semibold text-sm">
            Tabel penerima × nilai variabel
            <span class="font-normal text-slate-400">({{ formatNumber(rvTotal) }} penerima)</span>
          </div>
          <div class="overflow-auto thin-scroll max-h-96">
            <table class="w-full text-sm min-w-[600px]">
              <thead class="sticky top-0 bg-slate-50">
                <tr class="text-left text-xs uppercase tracking-wide text-slate-500">
                  <th class="px-4 py-2 font-semibold">#</th>
                  <th class="px-4 py-2 font-semibold">Nama</th>
                  <th class="px-4 py-2 font-semibold">Nomor</th>
                  <th v-for="vn in rvVarNames" :key="vn" class="px-4 py-2 font-semibold font-mono normal-case">{{ wrapVar(vn) }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in rvTable" :key="row.id || i" class="border-t border-slate-100 hover:bg-slate-50">
                  <td class="px-4 py-2 text-slate-400">{{ i + 1 }}</td>
                  <td class="px-4 py-2">{{ row.name || row.contact_name || '–' }}</td>
                  <td class="px-4 py-2 font-mono text-xs">{{ row.phone }}</td>
                  <td v-for="vn in rvVarNames" :key="vn" class="px-4 py-2 max-w-48 truncate" :title="String(row.values?.[vn] ?? '')">
                    {{ row.values?.[vn] ?? '–' }}
                  </td>
                </tr>
                <tr v-if="!rvTable.length">
                  <td :colspan="3 + rvVarNames.length" class="px-4 py-8 text-center text-sm text-slate-400">
                    Tidak ada data penerima pada pratinjau.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Sample pesan -->
        <div class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="font-semibold text-sm mb-3">Contoh pesan ter-render (5 sample)</div>
          <div v-if="!rvSamples.length" class="text-sm text-slate-400">Tidak ada sample dari backend.</div>
          <div class="grid md:grid-cols-2 gap-4">
            <div v-for="(s, i) in rvSamples.slice(0, 5)" :key="i" class="bg-[#ece5dd] rounded-xl p-4">
              <div class="text-xs text-slate-500 mb-2">Sample {{ i + 1 }} — {{ typeof s === 'object' ? (s.phone || s.name) : '' }}</div>
              <div class="wa-bubble text-sm whitespace-pre-wrap">{{ typeof s === 'object' ? (s.message || s.body || s.rendered) : s }}</div>
            </div>
          </div>
        </div>

        <!-- Tombol aksi -->
        <div class="flex flex-wrap justify-end gap-2">
          <button
            v-if="hasSendAt"
            @click="openConfirm('schedule')"
            :disabled="rvErrors.length > 0"
            class="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            🗓️ Jadwalkan
          </button>
          <button
            @click="openConfirm('blast')"
            :disabled="rvErrors.length > 0"
            class="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {{ hasSendAt ? 'Konfirmasi & Blast (terjadwal)' : 'Konfirmasi & Blast' }}
          </button>
        </div>
        <div v-if="rvErrors.length" class="text-xs text-red-500 text-right">
          Tombol konfirmasi terkunci sampai semua error validasi diperbaiki.
        </div>
      </template>
    </section>

    <!-- Navigasi bawah -->
    <div v-if="step < 6" class="flex justify-between mt-6">
      <button
        @click="back"
        :disabled="step === 1 || loading"
        class="px-5 py-2.5 rounded-lg border border-slate-300 text-sm font-medium hover:bg-white disabled:opacity-40"
      >
        ← Kembali
      </button>
      <button
        @click="next"
        :disabled="loading"
        class="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm disabled:opacity-50"
      >
        {{ loading ? 'Memproses…' : step === 5 ? 'Lanjut ke Review →' : 'Lanjut →' }}
      </button>
    </div>
    <div v-else class="flex justify-start mt-6">
      <button @click="back" class="px-5 py-2.5 rounded-lg border border-slate-300 text-sm font-medium hover:bg-white">
        ← Kembali ke Penerima
      </button>
    </div>

    <!-- Dialog konfirmasi kedua -->
    <ConfirmDialog
      :open="showConfirmDialog"
      :title="confirmMode === 'schedule' ? 'Jadwalkan campaign?' : 'Konfirmasi blast?'"
      :message="confirmDialogText"
      :confirm-label="confirmMode === 'schedule' ? 'Ya, jadwalkan' : 'Ya, kirim sekarang'"
      :danger="rvCampaign.provider === 'unofficial'"
      :loading="confirming"
      @cancel="showConfirmDialog = false"
      @confirm="doConfirm"
    />
  </div>
</template>
