<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { campaignsApi, templatesApi, contactsApi, testNumbersApi, settingsApi, fileUploadsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import {
  formatRupiah, formatNumber, formatDuration, extractVariables, wrapVar,
  estimateDuration, estimateCost, DEFAULT_PRICE_PER_MESSAGE_IDR, truncate, formatPhone,
} from '../utils/format'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import Icon from '../components/Icon.vue'

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
const aiMode = ref('recipients') // 'recipients' | 'general'

// --- Ubah pesan: fleksibel seperti Blast dari File ---
// Pesan tidak harus terpaku template — teksnya bisa diedit di sini,
// lalu disimpan sebagai versi template baru khusus campaign ini.
const showMsgEdit = ref(false)
const msgEdit = ref('')
const msgEditRef = ref(null)
const msgSaving = ref(false)
const msgEditVars = computed(() => extractVariables(msgEdit.value || ''))
const msgEditChips = computed(() => {
  const seen = []
  const fileVars = fileColumns.value.map((c) => c.variable).filter(Boolean)
  for (const v of [...selectedVariables.value, ...msgEditVars.value, ...fileVars]) {
    if (!seen.includes(v)) seen.push(v)
  }
  return seen
})

function openMsgEdit() {
  msgEdit.value = selectedVersion.value?.version?.body || ''
  showMsgEdit.value = true
}

function insertMsgVar(v) {
  const tag = wrapVar(v)
  const el = msgEditRef.value
  if (!el) {
    msgEdit.value += tag
    return
  }
  const start = el.selectionStart ?? msgEdit.value.length
  const end = el.selectionEnd ?? start
  msgEdit.value = msgEdit.value.slice(0, start) + tag + msgEdit.value.slice(end)
  nextTick(() => {
    el.focus()
    el.selectionStart = el.selectionEnd = start + tag.length
  })
}

async function saveMsgEdit() {
  if (!msgEdit.value.trim()) {
    toast.error('Isi pesan tidak boleh kosong.')
    return
  }
  if (!campaign.value) return
  msgSaving.value = true
  try {
    const res = await campaignsApi.updateMessageBody(campaign.value.id, msgEdit.value)
    // Arahkan wizard ke versi baru
    selectedVersion.value.version = {
      ...selectedVersion.value.version,
      id: res.template_version_id,
      version_number: res.version_number,
      variables: res.variables,
      body: msgEdit.value,
    }
    if (campaign.value.template_version) {
      campaign.value.template_version = {
        ...campaign.value.template_version,
        id: res.template_version_id,
        version_number: res.version_number,
        variables: res.variables,
        body: msgEdit.value,
      }
    }
    mappings.value = [] // paksa rebuild mapping di langkah 4
    showMsgEdit.value = false
    toast.success(`Pesan disimpan sebagai versi ${res.version_number}.`)
  } finally {
    msgSaving.value = false
  }
}

// --- Tab Upload file: terapkan CSV/XLSX ke campaign ini ---
const fileUpload = ref(null) // hasil /file-uploads/parse
const filePhoneVar = ref('')
const fileUploading = ref(false)
const filePreviewing = ref(false)
const filePreview = ref(null)
const fileApplying = ref(false)
const fileColumns = computed(() => fileUpload.value?.columns || [])

async function onFilePick(e) {
  const file = e.target.files?.[0]
  if (!file) return
  fileUploading.value = true
  filePreview.value = null
  try {
    const res = await fileUploadsApi.parse(file)
    fileUpload.value = res
    filePhoneVar.value = res.phone_variable_suggestion || ''
    if (!res.phone_variable_suggestion) {
      toast.error('Kolom nomor telepon tidak terdeteksi otomatis — pilih manual di bawah.')
    } else {
      toast.success(`${res.row_count} baris dibaca dari ${res.filename}.`)
    }
  } finally {
    fileUploading.value = false
    e.target.value = ''
  }
}

function resetFileUpload() {
  fileUpload.value = null
  filePhoneVar.value = ''
  filePreview.value = null
}

async function doFilePreview() {
  if (!selectedVersion.value) {
    toast.error('Pilih template di langkah 2 dulu.')
    return
  }
  if (!filePhoneVar.value) {
    toast.error('Pilih kolom nomor telepon.')
    return
  }
  filePreviewing.value = true
  try {
    filePreview.value = await fileUploadsApi.preview(fileUpload.value.upload_id, {
      message: msgEdit.value.trim() || selectedVersion.value.version.body,
      phone_variable: filePhoneVar.value,
    })
  } finally {
    filePreviewing.value = false
  }
}

async function doFileApply() {
  if (!campaign.value) return
  if (!filePhoneVar.value) {
    toast.error('Pilih kolom nomor telepon.')
    return
  }
  fileApplying.value = true
  try {
    const res = await campaignsApi.applyFile(campaign.value.id, {
      upload_id: fileUpload.value.upload_id,
      phone_variable: filePhoneVar.value,
    })
    const warns = []
    if (res.skipped?.length) warns.push(`${res.skipped.length} baris dilewati`)
    toast.success(
      `${res.added} penerima ditambahkan dari file.` + (warns.length ? ` (${warns.join('; ')})` : '')
    )
    existingRecipients.value += res.added
    filePreview.value = null
  } finally {
    fileApplying.value = false
  }
}

// --- Mode lama: nilai umum (sama untuk semua penerima) ---
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
      aiNote.value = data.note || 'Layanan AI tidak tersedia saat ini. Anda tetap bisa mengisi nilai variabel secara manual di langkah 4.'
    }
    const n = Object.keys(aiResult.value || {}).length
    toast.success(n ? `AI mengekstrak ${n} nilai variabel.` : 'AI tidak menemukan nilai yang cocok. Isi manual di langkah 4.')
  } catch (e) {
    aiNote.value = 'Layanan AI tidak tersedia saat ini. Anda tetap bisa mengisi nilai variabel secara manual di langkah 4.'
  } finally {
    aiLoading.value = false
  }
}

// --- Mode baru: daftar penerima (nilai berbeda per penerima) ---
const aiRecText = ref('')
const aiRecLoading = ref(false)
const aiRecApplying = ref(false)
const aiRecItems = ref([]) // [{phone, name, variables:{}, phone_valid, phone_normalized, contact_exists, contact_name}]
const aiRecNote = ref('')
const aiRecDone = ref(null) // ringkasan setelah apply

async function runAiParseRecipients() {
  if (!aiRecText.value.trim()) {
    toast.warning('Tempel dulu daftar penerima sebelum diproses AI.')
    return
  }
  if (!campaign.value) return
  aiRecLoading.value = true
  aiRecItems.value = []
  aiRecNote.value = ''
  aiRecDone.value = null
  try {
    const data = await campaignsApi.aiParseRecipients(campaign.value.id, aiRecText.value.trim())
    aiRecItems.value = (data.items || []).map((it) => ({
      phone: it.phone || '',
      name: it.name || '',
      variables: { ...(it.variables || {}) },
      phone_valid: !!it.phone_valid,
      phone_normalized: it.phone_normalized || '',
      contact_exists: !!it.contact_exists,
      contact_name: it.contact_name || '',
    }))
    if (data.ai_available === false) {
      aiRecNote.value = 'Layanan AI tidak tersedia. Periksa API key Gemini di Pengaturan.'
    } else if (!aiRecItems.value.length) {
      aiRecNote.value = 'AI tidak menemukan daftar penerima di teks. Coba format bernomor/bullet per baris.'
    } else {
      const invalid = aiRecItems.value.filter((r) => !r.phone_valid).length
      toast.success(`AI menemukan ${aiRecItems.value.length} penerima.` + (invalid ? ` ${invalid} nomor perlu diperbaiki.` : ''))
    }
  } catch (e) {
    aiRecNote.value = 'Gagal memproses dengan AI. Coba lagi.'
  } finally {
    aiRecLoading.value = false
  }
}

function removeAiRecRow(i) {
  aiRecItems.value.splice(i, 1)
}

function addAiRecRow() {
  const vars = {}
  for (const v of selectedVariables.value) vars[v] = ''
  aiRecItems.value.push({ phone: '', name: '', variables: vars, phone_valid: false, phone_normalized: '', contact_exists: false, contact_name: '' })
}

async function applyAiRecipients() {
  const rows = aiRecItems.value.filter((r) => r.phone.trim())
  if (!rows.length) {
    toast.warning('Tidak ada baris penerima untuk disimpan.')
    return
  }
  if (!campaign.value) return
  aiRecApplying.value = true
  try {
    const data = await campaignsApi.aiApplyRecipients(
      campaign.value.id,
      rows.map((r) => ({ phone: r.phone.trim(), name: r.name.trim(), variables: r.variables || {} })),
    )
    aiRecDone.value = data
    aiRecItems.value = []
    const parts = [`${data.added} penerima ditambahkan`]
    if (data.created_contacts) parts.push(`${data.created_contacts} kontak baru`)
    if (data.matched_contacts) parts.push(`${data.matched_contacts} kontak dikenali`)
    if (data.skipped?.length) parts.push(`${data.skipped.length} dilewati`)
    toast.success(parts.join(', ') + '.')
  } catch (e) {
    toast.error('Gagal menyimpan penerima.')
  } finally {
    aiRecApplying.value = false
  }
}

/* -------------------------- Langkah 4: mapping -------------------------- */
const mappings = ref([]) // [{variable_name, source: 'contact'|'campaign', contact_field, value}]

function smartDefault(varName) {
  // Hanya map ke field kontak bila yakin: nama variabel persis menunjuk
  // data orang. Selain itu default ke campaign (nilai manual/AI).
  // (Dulu: v.includes('nama') ikut menangkap 'nama_pos' → mapping ngaco.)
  const v = varName.toLowerCase().trim()
  if (['nama', 'name', 'nama_lengkap', 'fullname', 'full_name'].includes(v))
    return { source: 'contact', contact_field: 'name' }
  if (['phone', 'telp', 'telepon', 'nomor', 'nomor_hp', 'no_hp', 'nohp', 'hp', 'whatsapp', 'wa'].includes(v))
    return { source: 'contact', contact_field: 'phone' }
  if (v === 'tag' || v.includes('tag'))
    return { source: 'contact', contact_field: 'tag' }
  return { source: 'campaign', contact_field: null }
}

async function initMappings() {
  let existing = []
  try {
    const data = await campaignsApi.mappings(campaign.value.id)
    existing = Array.isArray(data) ? data : data.mappings || []
  } catch { /* biarkan default */ }
  // Nilai per-penerima hasil AI: variabel yang sudah terisi tidak perlu mapping manual
  try {
    const rv = await campaignsApi.recipientVariables(campaign.value.id)
    const map = {}
    for (const v of rv.variables || []) map[v.variable_name] = v
    recipientVars.value = map
    recipientVarsError.value = false
  } catch {
    recipientVars.value = {}
    // Jangan diam-diam fallback ke mapping manual: tandai agar UI menampilkan peringatan
    recipientVarsError.value = true
  }
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

/* Nilai per-penerima hasil AI (override): {variable_name: {recipient_count, entries}} */
const recipientVars = ref({})
const recipientVarsError = ref(false)
const aiFilledCount = (varName) => recipientVars.value[varName]?.recipient_count || 0

/* Edit inline nilai per-penerima */
const rvEditVar = ref(null) // variable_name yang sedang diedit
const rvEditRows = ref([])  // [{recipient_id, phone, name, value}]
const rvSaving = ref(false)

function startRvEdit(varName) {
  const summary = recipientVars.value[varName]
  if (!summary) return
  rvEditVar.value = varName
  rvEditRows.value = (summary.entries || []).map((e) => ({ ...e }))
}

function cancelRvEdit() {
  rvEditVar.value = null
  rvEditRows.value = []
}

async function saveRvEdit() {
  if (!rvEditVar.value || !campaign.value) return
  rvSaving.value = true
  try {
    const data = await campaignsApi.saveRecipientVariables(
      campaign.value.id,
      rvEditRows.value.map((r) => ({
        recipient_id: r.recipient_id,
        variable_name: rvEditVar.value,
        value: r.value ?? '',
      })),
    )
    const map = {}
    for (const v of data.variables || []) map[v.variable_name] = v
    recipientVars.value = map
    toast.success(`Nilai ${wrapVar(rvEditVar.value)} per penerima disimpan.`)
    cancelRvEdit()
  } catch {
    toast.error('Gagal menyimpan nilai per penerima.')
  } finally {
    rvSaving.value = false
  }
}

async function clearRvVar(varName) {
  if (!campaign.value) return
  if (!confirm(`Hapus ${recipientVars.value[varName]?.recipient_count || 0} nilai AI untuk ${wrapVar(varName)}? Variabel kembali ke mapping manual.`)) return
  try {
    await campaignsApi.clearRecipientVariable(campaign.value.id, varName)
    const next = { ...recipientVars.value }
    delete next[varName]
    recipientVars.value = next
    toast.success(`Nilai AI untuk ${wrapVar(varName)} dihapus. Silakan mapping manual.`)
  } catch {
    toast.error('Gagal menghapus nilai AI.')
  }
}

const mappingErrors = computed(() => {
  const errs = []
  for (const m of mappings.value) {
    // Variabel yang sudah terisi AI per penerima tidak butuh mapping manual
    if (aiFilledCount(m.variable_name) > 0) continue
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
      const { items } = await contactsApi.list({ limit: 100 })
      allContacts.value = items || []
    }
    // Penerima yang sudah ditambahkan (mis. via AI di langkah 3)
    if (campaign.value) {
      try {
        const res = await campaignsApi.recipients(campaign.value.id, { limit: 1 })
        existingRecipients.value = res.meta?.total ?? res.total ?? (res.items || []).length
      } catch { existingRecipients.value = 0 }
    }
  } finally {
    recipientsLoading.value = false
  }
}
const existingRecipients = ref(0)

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
    const { items } = await contactsApi.list({ limit: 100 })
    allContacts.value = items || []
    if (contact && !contact.is_blacklisted) {
      const s = new Set(selectedContacts.value)
      s.add(contact.id)
      selectedContacts.value = s
    }
    toast.success(
      created
        ? `Kontak "${contact.name}" tersimpan dan otomatis terpilih`
        : `Nomor sudah terdaftar. Kontak "${contact.name}" otomatis terpilih`
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
// Jam ala WhatsApp untuk pratinjau bubble (bukan data nyata)
const sampleTime = computed(() => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}.${String(d.getMinutes()).padStart(2, '0')}`
})
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
    if (selectedContacts.value.size === 0 && existingRecipients.value === 0) {
      errs.push('Pilih minimal satu penerima.')
    }
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
      // Variabel yang sudah terisi AI per penerima tidak perlu mapping manual
      const manual = mappings.value.filter((m) => aiFilledCount(m.variable_name) === 0)
      await campaignsApi.saveMappings(campaign.value.id, manual)
      toast.success('Mapping variabel disimpan.')
    }
    if (step.value === 5) {
      const ids = form.value.is_test_mode ? [] : [...selectedContacts.value]
      const res = await campaignsApi.buildRecipients(campaign.value.id, ids)
      const built = res.built ?? res.count ?? res.total ?? ids.length
      const existing = existingRecipients.value
      const skippedNoData = res.skipped_no_data || 0
      const noDataNote = skippedNoData
        ? ` ${skippedNoData} nomor test dilewati (tidak ada datanya dari AI/mapping).`
        : ''
      toast.success(
        form.value.is_test_mode
          ? `Penerima mode test dibangun (${testNums.value.length} nomor test).${noDataNote}`
          : existing > 0 && built === 0
            ? `${existing} penerima sudah ada dari langkah sebelumnya. Lanjut ke Review.`
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
  const provLabel = rvCampaign.value.provider === 'official' ? 'RESMI' : rvCampaign.value.provider === 'manual' ? 'MANUAL (via WhatsApp Web)' : 'NON-RESMI'
  const costPart = rvCampaign.value.provider === 'official' ? ` dengan estimasi biaya ${formatRupiah(rvCost.value)}` : ''
  const manualPart = rvCampaign.value.provider === 'manual' ? ' Pengiriman dilakukan manual per penerima dari halaman detail.' : ''
  if (confirmMode.value === 'schedule') {
    return `Campaign “${rvCampaign.value.name}” akan DIJADWALKAN ke ${total} penerima pada waktu yang ditentukan, via jalur ${provLabel}. Lanjutkan?`
  }
  return `Campaign “${rvCampaign.value.name}” akan DIKIRIM ke ${total} penerima via jalur ${provLabel}${costPart}${manualPart}. Tindakan ini tidak bisa dibatalkan untuk pesan yang sudah terkirim. Lanjutkan?`
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
      // Lompat ke langkah tertentu (mis. dari Blast File langsung ke review)
      const targetStep = parseInt(route.query.step || '0', 10)
      if (targetStep === 6) {
        step.value = 6
        await loadReview()
      }
    } catch { /* abaikan, mulai wizard baru */ }
  }
})
</script>

<template>
  <div class="wizard">
    <div class="mb-6">
      <h1 class="page-title">Campaign Baru</h1>
      <p class="page-sub">6 langkah: info, template, AI, mapping, penerima, review</p>
    </div>

    <!-- Step indicator: ticks ala WhatsApp untuk langkah selesai -->
    <ol class="steps">
      <li v-for="s in STEPS" :key="s.n" class="step" :class="{ current: s.n === step, done: s.n < step }">
        <button @click="goTo(s.n)" class="step-btn">
          <span class="step-mark">
            <Icon v-if="s.n < step" name="check-double" :size="14" class="wa-ticks" />
            <span v-else class="step-num">{{ s.n }}</span>
          </span>
          <span class="step-label">{{ s.label }}</span>
        </button>
        <span v-if="s.n < STEPS.length" class="step-sep" aria-hidden="true">›</span>
      </li>
    </ol>

    <div v-if="stepErrors.length" class="alert-negative mb-4">
      <div class="font-semibold text-sm mb-1">Perbaiki dulu:</div>
      <ul class="list-disc list-inside text-sm space-y-0.5">
        <li v-for="(e, i) in stepErrors" :key="i">{{ e }}</li>
      </ul>
    </div>

    <!-- ================= LANGKAH 1: INFO DASAR ================= -->
    <section v-if="step === 1" class="card card-pad form-grid">
      <h2 class="section-title">1. Info dasar campaign</h2>

      <div>
        <label class="field-label">Nama campaign *</label>
        <input v-model="form.name" class="field-input" placeholder="mis. Promo Akhir Tahun" />
      </div>

      <div>
        <label class="field-label">Jalur pengiriman (provider)</label>
        <div class="provider-grid">
          <label
            class="provider-card"
            :class="{ selected: form.provider === 'official' }"
          >
            <div class="provider-head">
              <input type="radio" v-model="form.provider" value="official" class="radio-accent" />
              <Icon name="check" :size="15" class="provider-check" />
              <span class="font-semibold text-sm">Resmi — Meta Cloud API</span>
            </div>
            <ul class="provider-points">
              <li>Biaya ± Rp 627,33/pesan marketing (per pesan ter-deliver)</li>
              <li>Wajib template yang disetujui Meta</li>
              <li>Risiko banned rendah bila penerima opt-in</li>
            </ul>
          </label>
          <label
            class="provider-card"
            :class="{ selected: form.provider === 'unofficial' }"
          >
            <div class="provider-head">
              <input type="radio" v-model="form.provider" value="unofficial" class="radio-accent" />
              <Icon name="zap" :size="15" class="provider-check" />
              <span class="font-semibold text-sm">Non-resmi — Baileys (gratis, self-hosted)</span>
            </div>
            <ul class="provider-points">
              <li><b>Rp 0</b> — gratis, tanpa perantara</li>
              <li>Teks bebas, tanpa approval template</li>
              <li>Cocok untuk testing template/variabel/AI</li>
            </ul>
          </label>
          <label
            class="provider-card"
            :class="{ selected: form.provider === 'manual' }"
          >
            <div class="provider-head">
              <input type="radio" v-model="form.provider" value="manual" class="radio-accent" />
              <Icon name="chat" :size="15" class="provider-check" />
              <span class="font-semibold text-sm">Manual — via WhatsApp Web</span>
            </div>
            <ul class="provider-points">
              <li><b>Rp 0</b> — tanpa otomasi sama sekali</li>
              <li>Klik per penerima → WA Web terbuka dengan pesan ter-render</li>
              <li>Nol risiko banned — kirim dari aplikasi resmi</li>
            </ul>
          </label>
        </div>

        <div v-if="form.provider === 'manual'" class="alert-info mt-3">
          <Icon name="info" :size="16" class="mt-0.5 shrink-0" />
          <div>
            <div class="alert-title">Cara kerja jalur manual</div>
            <p class="mt-1">
              Setelah konfirmasi, buka halaman detail campaign → seksi
              <b>Kirim manual via WhatsApp</b>. Klik <b>Buka di WhatsApp</b> per penerima —
              WhatsApp Web terbuka (pastikan sudah login) dengan pesan yang sudah ter-render,
              tinggal tekan kirim. Tandai <b>Terkirim</b> / <b>Lewati</b> per penerima untuk audit.
            </p>
          </div>
        </div>
        <div v-if="form.provider === 'unofficial'" class="alert-negative mt-3">
          <Icon name="alert" :size="16" class="mt-0.5 shrink-0" />
          <div>
            <div class="alert-title">Risiko banned</div>
            <p class="mt-1">
              Jalur non-resmi bukan API resmi WhatsApp. <b>Nomor yang dipakai bisa di-banned WhatsApp.</b>
              Jangan gunakan nomor WA utama/pribadi. Pakai nomor testing khusus. Disarankan hanya untuk testing,
              bukan blast produksi.
            </p>
          </div>
        </div>
        <div v-else class="alert-positive mt-3">
          <Icon name="info" :size="16" class="mt-0.5 shrink-0" />
          <div>
            Jalur resmi memakai tarif Meta per pesan ter-deliver (Marketing Rp 627,33 · Utility Rp 366,65 · Authentication Rp 366,65 · Service Rp 356,65).
            Estimasi biaya total dihitung di halaman review.
          </div>
        </div>
      </div>

      <label class="check-row">
        <input id="testmode" type="checkbox" v-model="form.is_test_mode" class="check-accent" />
        <span class="text-sm">
          <span class="font-semibold">Mode test</span>
          <span class="block card-label mt-0.5">Bila aktif, pesan hanya dikirim ke nomor test terdaftar (bukan ke kontak asli). Aman untuk uji coba.</span>
        </span>
      </label>

      <div>
        <label class="field-label">Jadwal kirim (opsional)</label>
        <input v-model="form.send_at" type="datetime-local" class="field-input w-auto" />
        <div class="field-hint">Kosongkan untuk kirim segera setelah konfirmasi. Bila diisi, campaign berstatus terjadwal.</div>
      </div>
    </section>

    <!-- ================= LANGKAH 2: TEMPLATE ================= -->
    <section v-if="step === 2" class="form-grid">
      <div class="card card-pad">
        <h2 class="section-title mb-1">2. Pilih versi template</h2>
        <p class="card-label mb-4">Versi yang dipilih di-pin ke campaign (tidak berubah walau template diedit).</p>

        <div v-if="!templates.length" class="empty-inline">
          Belum ada template. <RouterLink to="/templates" class="row-link">Buat template dulu</RouterLink>.
        </div>

        <div v-for="t in templates" :key="t.id" class="tpl-group">
          <button @click="toggleTemplate(t)" class="tpl-head">
            <Icon :name="expandedTemplate?.id === t.id ? 'chevron-down' : 'chevron-right'" :size="15" class="shrink-0" />
            <span class="font-medium">{{ t.name }}</span>
            <span v-if="t.description" class="card-label truncate">{{ truncate(t.description, 60) }}</span>
          </button>
          <div v-if="expandedTemplate?.id === t.id" class="tpl-versions">
            <div v-if="versionsLoading" class="card-label">Memuat versi…</div>
            <label
              v-for="v in (versionsCache[t.id] || [])"
              :key="v.id || v.version_number"
              class="version-card"
              :class="{ selected: selectedVersion?.version?.id === v.id }"
            >
              <div class="version-head">
                <input
                  type="radio"
                  :checked="selectedVersion?.version?.id === v.id"
                  @change="pickVersion(t, v)"
                  class="radio-accent"
                />
                <span class="font-semibold text-sm">Versi {{ v.version_number }}</span>
                <StatusPill :status="v.approval_status || 'draft'" />
                <span v-if="v.provider_category" class="pill pill-neutral">{{ v.provider_category }}</span>
                <span class="card-label ml-auto">{{ (v.variables || []).length }} variabel</span>
              </div>
              <pre class="version-body">{{ truncate(v.body, 220) }}</pre>
              <div
                v-if="form.provider === 'official' && (v.approval_status || 'draft') !== 'approved'"
                class="alert-negative mt-2"
              >
                <Icon name="alert" :size="14" class="mt-0.5 shrink-0" />
                <span>Jalur resmi mewajibkan template berstatus <b>approved</b> oleh Meta. Versi ini belum bisa dipakai blast produksi.</span>
              </div>
            </label>
          </div>
        </div>

        <div v-if="selectedVersion" class="alert-positive mt-4">
          <Icon name="check" :size="15" class="mt-0.5 shrink-0" />
          <div class="text-sm">
            Terpilih: <b>{{ selectedVersion.template.name }}</b> — versi {{ selectedVersion.version.version_number }}
            <span class="card-label">({{ selectedVariables.length }} variabel: {{ selectedVariables.map(v => wrapVar(v)).join(', ') || '–' }})</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ================= LANGKAH 3: INPUT DATA ================= -->
    <section v-if="step === 3" class="card card-pad form-grid">
      <div>
        <h2 class="section-title">3. Input data</h2>
        <div class="seg-toggle mt-2" role="tablist">
          <button :class="['seg-btn', { active: aiMode === 'recipients' }]" @click="aiMode = 'recipients'">
            <Icon name="users" :size="14" /> AI — Daftar penerima
          </button>
          <button :class="['seg-btn', { active: aiMode === 'general' }]" @click="aiMode = 'general'">
            <Icon name="zap" :size="14" /> AI — Nilai umum
          </button>
          <button :class="['seg-btn', { active: aiMode === 'file' }]" @click="aiMode = 'file'">
            <Icon name="upload" :size="14" /> Upload file
          </button>
        </div>
      </div>

      <!-- Ubah pesan: fleksibel seperti Blast dari File -->
      <div v-if="selectedVersion" class="msg-edit-card">
        <button @click="showMsgEdit ? (showMsgEdit = false) : openMsgEdit()" class="msg-edit-toggle" type="button">
          <Icon name="pencil" :size="14" />
          {{ showMsgEdit ? 'Tutup editor pesan' : 'Ubah pesan (fleksibel)' }}
        </button>
        <p class="card-label mt-1">Pesan tidak harus terpaku template — ubah teksnya di sini, variabel tetap bisa dipakai.</p>
        <div v-if="showMsgEdit" class="mt-3">
          <div class="chip-row mb-2">
            <span class="card-label">Klik untuk tempel di kursor:</span>
            <button
              v-for="v in msgEditChips"
              :key="v"
              @click="insertMsgVar(v)"
              class="chip-var chip-click mono"
              type="button"
            >
              {{ wrapVar(v) }}
            </button>
          </div>
          <textarea
            ref="msgEditRef"
            v-model="msgEdit"
            rows="6"
            class="field-input"
            placeholder="Tulis pesan…"
          />
          <div class="mt-2">
            <button @click="saveMsgEdit" :disabled="msgSaving" class="btn btn-accent text-sm" type="button">
              <Icon name="check" :size="14" /> {{ msgSaving ? 'Menyimpan…' : 'Simpan sebagai versi baru' }}
            </button>
          </div>
          <p class="card-label mt-2">
            Menyimpan membuat <b>versi template baru</b> khusus campaign ini — template aslinya tidak berubah,
            mapping yang sudah ada ikut terbawa.
          </p>
        </div>
      </div>

      <!-- ===== Mode: daftar penerima (nilai beda per orang) ===== -->
      <template v-if="aiMode === 'recipients'">
        <p class="card-label -mt-2">
          Tempel daftar penerima dalam bentuk teks bebas apa pun (satu entri per baris/blok: nama, nomor HP,
          dan data pendukungnya — AI membaca cerdas mengikuti variabel template Anda).
          AI akan memecahnya per penerima beserta nilai variabelnya. Periksa dan edit hasilnya
          sebelum disimpan. Satu nomor boleh muncul berkali-kali, tiap baris jadi satu pesan.
        </p>

        <div>
          <label class="field-label">Daftar penerima (teks bebas)</label>
          <textarea v-model="aiRecText" rows="7" class="field-input mono" placeholder="Contoh:&#10;1. POS Buol&#10;Ruben&#10;+62 877-2896-3152&#10;Jl. MA Turungku Kel. Kali Kec. Biau Kab. Buol&#10;&#10;2. POS Donggala&#10;Rivan&#10;+62 877-2896-3152&#10;Jl. Trans Sulawesi Palu - Sabang"></textarea>
        </div>

        <div>
          <button @click="runAiParseRecipients" :disabled="aiRecLoading" class="btn btn-secondary">
            <Icon name="users" :size="15" /> {{ aiRecLoading ? 'Menganalisis…' : 'Proses dengan AI' }}
          </button>
        </div>

        <div v-if="aiRecNote" class="alert-warning">
          <Icon name="alert" :size="15" class="mt-0.5 shrink-0" /> <span>{{ aiRecNote }}</span>
        </div>

        <div v-if="aiRecItems.length" class="tbl-wrap">
          <div class="tbl-title">Hasil parse AI: periksa dan edit sebelum disimpan ({{ aiRecItems.length }} penerima)</div>
          <div class="tbl-scroll thin-scroll">
            <table class="tbl min-w-[720px]">
              <thead>
                <tr>
                  <th class="w-10">No</th>
                  <th>Nama</th>
                  <th>Nomor HP</th>
                  <th v-for="vn in selectedVariables" :key="vn" class="mono">{{ wrapVar(vn) }}</th>
                  <th class="w-12"><span class="sr-only">Hapus</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in aiRecItems" :key="i" :class="{ 'row-invalid': !row.phone_valid }">
                  <td class="num">{{ i + 1 }}</td>
                  <td><input v-model="row.name" class="field-input field-sm" placeholder="Nama" /></td>
                  <td>
                    <input v-model="row.phone" class="field-input field-sm mono" placeholder="+62812…" />
                    <div v-if="!row.phone_valid && row.phone" class="field-err">Nomor tidak valid</div>
                    <div v-else-if="row.contact_exists" class="field-hint-ok">Kontak dikenali{{ row.contact_name ? ': ' + row.contact_name : '' }}</div>
                  </td>
                  <td v-for="vn in selectedVariables" :key="vn">
                    <input v-model="row.variables[vn]" class="field-input field-sm" :placeholder="wrapVar(vn)" />
                  </td>
                  <td class="num">
                    <button @click="removeAiRecRow(i)" class="icon-btn is-danger" title="Hapus baris">
                      <Icon name="trash" :size="15" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="tbl-foot">Dengan menekan tombol di bawah, Anda <b>menyetujui hasil ekstraksi &amp; rekomendasi mapping AI</b> di atas. Baris tanpa nomor valid tidak ikut disimpan. Kontak baru otomatis dibuat; kontak lama dikenali dari nomornya.</div>
        </div>

        <div v-if="aiRecItems.length" class="flex flex-wrap gap-2">
          <button @click="addAiRecRow" class="btn btn-tertiary text-sm">
            <Icon name="plus" :size="14" /> Tambah baris manual
          </button>
          <button @click="applyAiRecipients" :disabled="aiRecApplying" class="btn btn-accent">
            <Icon name="check" :size="15" /> {{ aiRecApplying ? 'Menyimpan…' : `Setuju — gunakan hasil AI (${aiRecItems.filter(r => r.phone.trim()).length} penerima)` }}
          </button>
        </div>

        <div v-if="aiRecDone" class="alert-success">
          <Icon name="check-double" :size="15" class="mt-0.5 shrink-0" />
          <span>
            {{ aiRecDone.added }} penerima ditambahkan
            ({{ aiRecDone.created_contacts }} kontak baru, {{ aiRecDone.matched_contacts }} kontak dikenali).
            <template v-if="aiRecDone.skipped?.length">Dilewati: {{ aiRecDone.skipped.join('; ') }}.</template>
            Cek hasil render tiap penerima di langkah Review.
          </span>
        </div>
      </template>

      <!-- ===== Mode: nilai umum (sama untuk semua penerima) ===== -->
      <template v-else>
        <p class="card-label -mt-2">
          Tulis info campaign dengan bahasa bebas (mis. “Promo akhir tahun diskon 50% berlaku sampai 31 Desember, kode: HEMAT50”).
          AI akan mengekstrak SATU nilai per variabel yang berlaku sama untuk semua penerima.
          Hasilnya bisa Anda edit di langkah berikutnya.
        </p>

        <div>
          <label class="field-label">Teks bebas</label>
          <textarea v-model="aiText" rows="6" class="field-input" placeholder="Contoh: Promo cuci gudang! Diskon 70% semua fashion, hanya tanggal 12-12. Gratis ongkir min. belanja 100rb."></textarea>
        </div>

        <div>
          <button @click="runAiExtract" :disabled="aiLoading" class="btn btn-secondary">
            <Icon name="zap" :size="15" /> {{ aiLoading ? 'Menganalisis…' : 'Ekstrak dengan AI' }}
          </button>
        </div>

        <div v-if="aiNote" class="alert-warning">
          <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
          <span>{{ aiNote }}</span>
        </div>

        <div v-if="aiResult && Object.keys(aiResult).length" class="tbl-wrap">
          <div class="tbl-title">Hasil ekstraksi AI</div>
          <table class="tbl">
            <tbody>
              <tr v-for="(val, key) in aiResult" :key="key">
                <td class="mono w-40" style="color: var(--accent-ink); font-weight: 600">{{ wrapVar(key) }}</td>
                <td>{{ val || '–' }}</td>
              </tr>
            </tbody>
          </table>
          <div class="tbl-foot">Nilai ini menjadi prefill di langkah Mapping dan masih bisa diubah.</div>
        </div>

        <div>
          <button @click="step = 4; initMappings()" class="btn-tertiary text-sm">
            Lewati, isi manual di langkah Mapping <Icon name="chevron-right" :size="14" />
          </button>
        </div>
      </template>

      <!-- ===== Mode: upload file (tiap baris = penerima) ===== -->
      <template v-if="aiMode === 'file'">
        <p class="card-label -mt-2">
          Upload CSV/Excel — tiap baris menjadi penerima, tiap kolom menjadi nilai variabel per baris.
          Kolom file bisa ditempel ke pesan lewat editor "Ubah pesan (fleksibel)" di atas.
        </p>

        <div v-if="!fileUpload" class="upload-drop">
          <Icon name="upload" :size="22" class="upload-icon" />
          <label class="btn btn-secondary">
            {{ fileUploading ? 'Mengunggah…' : 'Pilih file CSV / Excel' }}
            <input type="file" accept=".csv,.xlsx,.xls" class="file-hidden" :disabled="fileUploading" @change="onFilePick" />
          </label>
          <p class="card-label mt-2">Maks 10 MB, 5000 baris. Baris pertama dianggap header.</p>
        </div>

        <template v-else>
          <div class="upload-meta">
            <div>
              <div class="font-semibold text-sm">{{ fileUpload.filename }}</div>
              <div class="card-label">{{ fileUpload.row_count }} baris data</div>
            </div>
            <button @click="resetFileUpload" class="btn btn-tertiary text-sm" type="button">
              <Icon name="x" :size="14" /> Ganti file
            </button>
          </div>

          <div class="mt-3">
            <div class="card-label mb-2">Kolom terdeteksi:</div>
            <div class="chip-row">
              <span v-for="c in fileColumns" :key="c.variable" class="chip-var mono" :title="`Header asli: ${c.header}`">
                {{ wrapVar(c.variable) }}
              </span>
            </div>
          </div>

          <div class="mt-3 max-w-sm">
            <label class="card-label" for="wf-phone-col">Kolom nomor telepon</label>
            <select id="wf-phone-col" v-model="filePhoneVar" class="field-input mt-1">
              <option value="" disabled>\u2014 pilih kolom \u2014</option>
              <option v-for="c in fileColumns" :key="c.variable" :value="c.variable">
                {{ c.header }} \u2192 {{ wrapVar(c.variable) }}
              </option>
            </select>
          </div>

          <div class="mt-3 flex flex-wrap gap-2">
            <button @click="doFilePreview" :disabled="filePreviewing" class="btn btn-secondary text-sm" type="button">
              <Icon name="eye" :size="14" /> {{ filePreviewing ? 'Memproses…' : 'Preview 5 baris' }}
            </button>
            <button @click="doFileApply" :disabled="fileApplying || !filePhoneVar" class="btn btn-accent text-sm" type="button">
              <Icon name="check" :size="14" /> {{ fileApplying ? 'Menerapkan…' : 'Terapkan sebagai penerima' }}
            </button>
          </div>

          <div v-if="filePreview" class="mt-4">
            <div v-if="filePreview.unknown_variables?.length" class="alert-warning mb-3">
              <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
              <span>Variabel ini dipakai di pesan tapi <b>tidak ada</b> di file: {{ filePreview.unknown_variables.map(wrapVar).join(', ') }} \u2014 akan ter-render kosong.</span>
            </div>
            <div class="card-label mb-3">
              {{ filePreview.valid_rows }} baris bernomor valid
              <template v-if="filePreview.skipped_rows"> \u00b7 {{ filePreview.skipped_rows }} baris nomornya tidak valid (otomatis dilewati)</template>
            </div>
            <div class="preview-list">
              <div v-for="p in filePreview.previews" :key="p.row" class="preview-item">
                <div class="preview-head">
                  <span class="font-semibold text-sm">Baris {{ p.row }}</span>
                  <span class="mono text-xs card-label">{{ p.phone || 'nomor tidak valid' }}</span>
                  <span v-if="!p.phone_valid" class="pill pill-negative">dilewati</span>
                </div>
                <div class="sample-wa">{{ p.message }}</div>
              </div>
            </div>
          </div>
        </template>
      </template>
    </section>

    <!-- ================= LANGKAH 4: MAPPING ================= -->
    <section v-if="step === 4" class="card card-pad form-grid">
      <div>
        <h2 class="section-title">4. Mapping variabel</h2>
        <p class="card-label mt-1">
          Variabel yang <b>sudah diisi AI per penerima</b> di langkah 3 tidak perlu mapping manual.
          Sisanya tentukan sumbernya: <b>field kontak</b> (beda per penerima, dari data kontak)
          atau <b>nilai campaign</b> (sama untuk semua penerima).
        </p>
      </div>

      <div v-if="!mappings.length" class="empty-inline">Memuat variabel…</div>

      <div v-if="recipientVarsError" class="alert-warning">
        <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
        <span>Gagal memuat nilai AI per penerima dari server — kemungkinan <b>backend belum di-update</b>.
        Jalankan <span class="mono">git pull</span> lalu <span class="mono">docker compose up -d --build</span>,
        kemudian ulangi langkah ini. Selama backend lama, mapping harus diisi manual.</span>
      </div>

      <div v-for="m in mappings" :key="m.variable_name" class="mapping-card">
        <div class="mono font-semibold" style="color: var(--accent-ink)">{{ wrapVar(m.variable_name) }}</div>

        <!-- Sudah terisi AI per penerima: tampil info, bukan form manual -->
        <template v-if="aiFilledCount(m.variable_name) > 0">
          <div class="ai-filled-row">
            <span class="pill pill-accent"><Icon name="zap" :size="13" /> Terisi AI per penerima</span>
            <span class="card-label">{{ aiFilledCount(m.variable_name) }} penerima punya nilai sendiri-sendiri</span>
          </div>
          <div v-if="rvEditVar !== m.variable_name && recipientVars[m.variable_name]" class="preview-chips">
            <span v-for="(e, i) in recipientVars[m.variable_name].entries.slice(0, 3)" :key="i" class="chip" :title="`${e.name} (${e.phone})`">{{ e.value || '–' }}</span>
            <span v-if="recipientVars[m.variable_name].entries.length > 3" class="card-label">+{{ recipientVars[m.variable_name].entries.length - 3 }} lagi</span>
          </div>
          <div class="flex flex-wrap gap-2 mt-2">
            <button @click="rvEditVar === m.variable_name ? cancelRvEdit() : startRvEdit(m.variable_name)" class="btn btn-tertiary text-sm">
              <Icon name="pencil" :size="14" /> {{ rvEditVar === m.variable_name ? 'Tutup' : 'Lihat / ubah nilai' }}
            </button>
            <button @click="clearRvVar(m.variable_name)" class="btn btn-tertiary text-sm">
              <Icon name="trash" :size="14" /> Hapus, mapping manual
            </button>
          </div>
          <div v-if="rvEditVar === m.variable_name" class="tbl-wrap mt-3">
            <div class="tbl-scroll thin-scroll">
              <table class="tbl">
                <thead><tr><th>Penerima</th><th>Nomor</th><th>Nilai {{ wrapVar(m.variable_name) }}</th></tr></thead>
                <tbody>
                  <tr v-for="row in rvEditRows" :key="row.recipient_id">
                    <td>{{ row.name || '–' }}</td>
                    <td class="mono whitespace-nowrap">{{ row.phone }}</td>
                    <td><input v-model="row.value" class="field-input field-sm" /></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="flex gap-2 mt-2">
              <button @click="saveRvEdit" :disabled="rvSaving" class="btn btn-accent text-sm">{{ rvSaving ? 'Menyimpan…' : 'Simpan nilai' }}</button>
              <button @click="cancelRvEdit" class="btn btn-tertiary text-sm">Batal</button>
            </div>
          </div>
        </template>

        <!-- Mapping manual -->
        <template v-else>
          <div class="mapping-sources">
            <label class="radio-row">
              <input type="radio" v-model="m.source" value="contact" class="radio-accent" />
              Field kontak
            </label>
            <label class="radio-row">
              <input type="radio" v-model="m.source" value="campaign" class="radio-accent" />
              Nilai campaign
            </label>
          </div>
          <div v-if="m.source === 'contact'">
            <label class="field-label">Field kontak</label>
            <select v-model="m.contact_field" class="field-input w-auto">
              <option value="name">Nama (name)</option>
              <option value="phone">Nomor (phone)</option>
              <option value="tag">Tag</option>
            </select>
          </div>
          <div v-else>
            <label class="field-label">Nilai (berlaku untuk semua penerima)</label>
            <input v-model="m.value" class="field-input" :placeholder="`Nilai untuk {{${m.variable_name}}}`" />
            <div v-if="aiResult?.[m.variable_name]" class="field-hint">Prefill dari AI: “{{ aiResult[m.variable_name] }}”. Silakan ubah bila perlu.</div>
          </div>
        </template>
      </div>
    </section>

    <!-- ================= LANGKAH 5: PENERIMA ================= -->
    <section v-if="step === 5" class="card card-pad form-grid">
      <h2 class="section-title">5. Pilih penerima</h2>

      <div v-if="!form.is_test_mode && existingRecipients > 0" class="alert-info">
        <Icon name="info" :size="15" class="mt-0.5 shrink-0" />
        <div><b>{{ existingRecipients }} penerima sudah ada</b> (dari AI/file di langkah 3). Anda bisa tambah lagi di bawah, atau langsung lanjut — yang sudah ada ikut terkirim.</div>
      </div>

      <div v-if="form.is_test_mode">
        <div class="alert-warning mb-4">
          <Icon name="flask" :size="15" class="mt-0.5 shrink-0" />
          <div><b>Mode test aktif.</b> Penerima otomatis memakai nomor test terdaftar. Kontak asli tidak akan menerima pesan.</div>
        </div>
        <div v-if="recipientsLoading" class="card-label">Memuat nomor test…</div>
        <ul v-else class="test-list">
          <li v-for="t in testNums" :key="t.id" class="test-row">
            <Icon name="check" :size="14" class="test-check" />
            <span class="font-medium">{{ t.label }}</span>
            <span class="mono card-label">{{ formatPhone(t.phone) }}</span>
          </li>
        </ul>
        <div v-if="!recipientsLoading && !testNums.length" class="empty-inline">
          Belum ada nomor test aktif. Tambahkan di menu <RouterLink to="/test-numbers" class="row-link">Nomor Test</RouterLink>.
        </div>
      </div>

      <div v-else class="form-grid">
        <div class="recipients-toolbar">
          <div class="search-wrap">
            <Icon name="search" :size="15" class="search-icon" />
            <input v-model="contactSearch" type="search" placeholder="Cari nama / nomor…" class="field-input search-input" />
          </div>
          <span class="card-label">{{ selectedContacts.size }} dari {{ selectableCount }} kontak dipilih</span>
          <button @click="toggleAll(true)" class="btn-tertiary text-sm">Pilih semua</button>
          <button @click="toggleAll(false)" class="btn-tertiary text-sm">Batalkan semua</button>
        </div>
        <div class="card-label">Kontak blacklist otomatis dikecualikan dan tidak bisa dipilih.</div>

        <!-- Tambah nomor cepat: otomatis tersimpan sebagai kontak -->
        <div class="quickadd">
          <div class="text-sm font-medium mb-2">Tambah nomor cepat <span class="font-normal card-label">— langsung tersimpan sebagai kontak dan terpilih</span></div>
          <div class="quickadd-row">
            <input v-model="quickName" type="text" placeholder="Nama PIC (opsional)" class="field-input" />
            <input v-model="quickPhone" type="tel" placeholder="Nomor WA, mis. 0812…" class="field-input mono" @keyup.enter="quickAddContact" />
            <button @click="quickAddContact" :disabled="quickAdding || !quickPhone.trim()" class="btn btn-accent">
              <Icon name="plus" :size="14" /> {{ quickAdding ? 'Menyimpan…' : 'Tambah' }}
            </button>
          </div>
          <div class="field-hint">Nomor otomatis diseragamkan: <span class="mono">0812…</span>, <span class="mono">+62812…</span>, <span class="mono">62812…</span> dianggap nomor yang sama, tidak akan dobel.</div>
        </div>

        <div v-if="recipientsLoading" class="empty-inline">Memuat kontak…</div>
        <div v-else class="contact-list thin-scroll">
          <label
            v-for="c in visibleContacts"
            :key="c.id"
            class="contact-row"
            :class="{ disabled: c.is_blacklisted }"
          >
            <input
              type="checkbox"
              :checked="selectedContacts.has(c.id)"
              :disabled="c.is_blacklisted"
              @change="toggleContact(c.id)"
              class="check-accent"
            />
            <span class="contact-main">
              <span class="font-medium">{{ c.name }}</span>
              <span class="mono card-label">{{ formatPhone(c.phone) }}</span>
            </span>
            <span v-if="c.tag" class="pill pill-neutral">{{ c.tag }}</span>
            <span v-if="c.is_blacklisted" class="pill pill-negative">Blacklist</span>
          </label>
          <div v-if="!visibleContacts.length" class="empty-inline">
            Tidak ada kontak yang cocok.
          </div>
        </div>
      </div>
    </section>

    <!-- ================= LANGKAH 6: REVIEW ================= -->
    <section v-if="step === 6" class="form-grid">
      <h2 class="section-title">6. Review & konfirmasi</h2>

      <div v-if="reviewLoading" class="card card-pad">
        <div class="grid gap-3">
          <span class="skeleton" style="height: 24px; width: 40%"></span>
          <span class="skeleton" style="height: 14px; width: 90%"></span>
          <span class="skeleton" style="height: 14px; width: 70%"></span>
        </div>
      </div>

      <template v-else-if="review">
        <!-- Banner mode test -->
        <div v-if="rvCampaign.is_test_mode" class="alert-warning">
          <Icon name="flask" :size="15" class="mt-0.5 shrink-0" />
          <div><div class="alert-title">Mode test aktif</div><div class="text-sm mt-0.5">Pesan hanya dikirim ke nomor test terdaftar, bukan ke kontak asli.</div></div>
        </div>

        <!-- Banner risiko banned -->
        <div v-if="rvCampaign.provider === 'unofficial'" class="alert-negative">
          <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
          <div>
            <div class="alert-title">Jalur non-resmi: risiko banned</div>
            <div class="text-sm mt-0.5">
              Pengiriman via jalur tidak resmi. Nomor pengirim bisa di-banned WhatsApp. Pastikan memakai nomor testing khusus,
              bukan nomor utama/pribadi.
            </div>
          </div>
        </div>

        <!-- Ringkasan -->
        <div class="kpi-strip kpi-4">
          <div class="kpi-cell">
            <div class="kpi-label">Total penerima</div>
            <div class="kpi-value num">{{ formatNumber(rvTotal) }}</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-label">Estimasi durasi kirim</div>
            <div class="kpi-value num">{{ formatDuration(rvDurationSec) }}</div>
            <div class="kpi-cap">±10 dtk/pesan + batas rate</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-label">Estimasi biaya</div>
            <div class="kpi-value num" :class="{ 'kpi-free': rvCost === 0 }">
              {{ rvCampaign.provider === 'unofficial' ? 'Rp 0' : formatRupiah(rvCost) }}
            </div>
            <div class="kpi-cap">{{ rvCampaign.provider === 'unofficial' ? 'jalur gratis' : `${formatRupiah(rvPricePerMsg)}/pesan · ${rvCategory}` }}</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-label">Template</div>
            <div class="kpi-value truncate-1">{{ selectedVersion?.template?.name || '–' }}</div>
            <div class="kpi-cap">v{{ selectedVersion?.version?.version_number }} · <StatusPill :status="rvCampaign.provider" /></div>
          </div>
        </div>

        <!-- Error validasi -->
        <div v-if="rvErrors.length" class="alert-negative">
          <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
          <div>
            <div class="alert-title">Campaign belum bisa dikonfirmasi. Perbaiki dulu:</div>
            <ul class="list-disc list-inside text-sm mt-1 space-y-0.5">
              <li v-for="(e, i) in rvErrors" :key="i">{{ typeof e === 'string' ? e : e.message || JSON.stringify(e) }}</li>
            </ul>
          </div>
        </div>

        <!-- Tabel penerima × variabel -->
        <div class="tbl-wrap">
          <div class="tbl-title">
            Tabel penerima × nilai variabel
            <span class="font-normal card-label">({{ formatNumber(rvTotal) }} penerima)</span>
          </div>
          <div class="tbl-scroll thin-scroll max-h-96">
            <table class="tbl min-w-[600px]">
              <thead class="sticky top-0" style="background: var(--surface)">
                <tr>
                  <th>#</th>
                  <th>Nama</th>
                  <th>Nomor</th>
                  <th v-for="vn in rvVarNames" :key="vn" class="mono">{{ wrapVar(vn) }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in rvTable" :key="row.id || i">
                  <td class="card-label">{{ i + 1 }}</td>
                  <td class="row-title">{{ row.name || row.contact_name || '–' }}</td>
                  <td class="mono text-xs">{{ row.phone }}</td>
                  <td v-for="vn in rvVarNames" :key="vn" class="max-w-48 truncate" :title="String(row.values?.[vn] ?? '')">
                    {{ row.values?.[vn] ?? '–' }}
                  </td>
                </tr>
                <tr v-if="!rvTable.length">
                  <td :colspan="3 + rvVarNames.length" class="empty-inline" style="border:0">
                    Tidak ada data penerima pada pratinjau.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Sample pesan -->
        <div class="card card-pad">
          <div class="section-title mb-3">Contoh pesan ter-render (5 sample)</div>
          <div v-if="!rvSamples.length" class="card-label">Tidak ada sample dari backend.</div>
          <div class="sample-grid">
            <div v-for="(s, i) in rvSamples.slice(0, 5)" :key="i" class="sample-wa">
              <div class="card-label mb-2">Sample {{ i + 1 }} — {{ typeof s === 'object' ? (s.phone || s.name) : '' }}</div>
              <div class="wa-bubble text-sm whitespace-pre-wrap">{{ typeof s === 'object' ? (s.message || s.body || s.rendered) : s }}<span class="wa-time">{{ sampleTime }}</span></div>
            </div>
          </div>
        </div>

        <!-- Tombol aksi -->
        <div class="review-actions">
          <button
            v-if="hasSendAt"
            @click="openConfirm('schedule')"
            :disabled="rvErrors.length > 0"
            class="btn btn-secondary"
          >
            <Icon name="calendar" :size="15" /> Jadwalkan
          </button>
          <button
            @click="openConfirm('blast')"
            :disabled="rvErrors.length > 0"
            class="btn btn-accent"
          >
            <Icon name="send" :size="15" /> {{ hasSendAt ? 'Konfirmasi & blast (terjadwal)' : 'Konfirmasi & blast' }}
          </button>
        </div>
        <div v-if="rvErrors.length" class="field-error text-right">
          Tombol konfirmasi terkunci sampai semua error validasi diperbaiki.
        </div>
      </template>
    </section>

    <!-- Navigasi bawah -->
    <div v-if="step < 6" class="wizard-nav">
      <button @click="back" :disabled="step === 1 || loading" class="btn btn-secondary">
        <Icon name="chevron-left" :size="15" /> Kembali
      </button>
      <button @click="next" :disabled="loading" class="btn btn-accent">
        {{ loading ? 'Memproses…' : step === 5 ? 'Lanjut ke review' : 'Lanjut' }} <Icon v-if="!loading" name="chevron-right" :size="15" />
      </button>
    </div>
    <div v-else class="wizard-nav wizard-nav-start">
      <button @click="back" class="btn btn-secondary">
        <Icon name="chevron-left" :size="15" /> Kembali ke penerima
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

<style scoped>
.wizard { max-width: 1024px; margin: 0 auto; }
.form-grid { display: grid; gap: 20px; }

/* Step indicator */
.steps {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-bottom: 28px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.step { display: flex; align-items: center; flex: none; }
.step-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-control);
  background: transparent; border: 0; cursor: pointer;
  font-size: 13px; color: var(--faint);
  white-space: nowrap;
}
.step-btn:hover { background: var(--raised); }
.step.current .step-btn { background: var(--accent-soft); color: var(--accent-ink); font-weight: 600; }
.step.done .step-btn { color: var(--accent-ink); }
.step-mark {
  width: 24px; height: 24px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--raised); color: var(--faint); flex: none;
}
.step.current .step-mark { background: var(--accent); color: #fff; }
.step.done .step-mark { background: var(--accent-soft); }
.step-num { font-size: 12px; font-weight: 600; }
.step.current .step-num { color: #fff; }
.step-label { font-size: 13px; }
.step-sep { margin: 0 4px; color: var(--control); }

/* Provider cards */
.provider-grid { display: grid; gap: 12px; }
@media (min-width: 768px) { .provider-grid { grid-template-columns: 1fr 1fr; } }
.provider-card {
  border: 1px solid var(--control);
  border-radius: var(--radius-card);
  padding: 16px;
  cursor: pointer;
  display: block;
}
.provider-card:hover { border-color: var(--faint); }
.provider-card.selected { border-color: var(--accent); background: var(--accent-soft); }
.provider-card.selected .provider-check { color: var(--accent); }
.provider-head { display: flex; align-items: center; gap: 8px; }
.provider-check { color: var(--faint); flex: none; }
.provider-points {
  font-size: 12px; color: var(--muted);
  margin: 8px 0 0 26px; padding: 0;
  display: grid; gap: 4px; list-style: disc inside;
}
.radio-accent, .check-accent { accent-color: var(--accent); width: 16px; height: 16px; flex: none; }
.check-row {
  display: flex; align-items: flex-start; gap: 12px;
  border: 1px solid var(--border); border-radius: var(--radius-card);
  padding: 14px 16px; cursor: pointer;
}
.check-row:hover { border-color: var(--control); }

/* Template */
.tpl-group { border: 1px solid var(--border); border-radius: var(--radius-card); margin-bottom: 12px; overflow: hidden; }
.tpl-head {
  width: 100%; display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; background: transparent; border: 0; cursor: pointer;
  font-size: 14px; color: var(--text); text-align: left;
}
.tpl-head:hover { background: var(--ground); }
.tpl-versions { border-top: 1px solid var(--rule); padding: 12px 16px; display: grid; gap: 8px; background: var(--ground); }
.version-card {
  display: block; border: 1px solid var(--border); border-radius: var(--radius-card);
  padding: 12px; cursor: pointer; background: var(--surface);
}
.version-card:hover { border-color: var(--control); }
.version-card.selected { border-color: var(--accent); background: var(--accent-soft); }
.version-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.version-body {
  white-space: pre-wrap; font-size: 12px; color: var(--muted);
  margin: 8px 0 0; font-family: var(--font);
}

/* Mapping */
.mapping-card {
  border: 1px solid var(--border); border-radius: var(--radius-card);
  padding: 16px; display: grid; gap: 12px;
}
.mapping-sources { display: flex; flex-wrap: wrap; gap: 16px; font-size: 14px; }
.radio-row { display: flex; align-items: center; gap: 8px; cursor: pointer; }

/* Penerima */
.recipients-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.search-wrap { position: relative; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--faint); pointer-events: none; }
.search-input { width: 240px; padding-left: 36px; min-height: 34px; }
.quickadd {
  border: 1px dashed var(--accent-track);
  background: var(--accent-soft);
  border-radius: var(--radius-card);
  padding: 16px;
}
.quickadd-row { display: flex; flex-wrap: wrap; gap: 8px; }
.quickadd-row .field-input { flex: 1 1 160px; }
.test-list { display: grid; gap: 8px; list-style: none; margin: 0; padding: 0; }
.test-row {
  display: flex; align-items: center; gap: 12px;
  border: 1px solid var(--border); border-radius: var(--radius-card);
  padding: 10px 16px; font-size: 14px;
}
.test-check { color: var(--accent); flex: none; }
.contact-list {
  border: 1px solid var(--border); border-radius: var(--radius-card);
  max-height: 384px; overflow-y: auto;
}
.contact-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; font-size: 14px; cursor: pointer;
  border-top: 1px solid var(--rule);
}
.contact-row:first-child { border-top: 0; }
.contact-row:hover { background: var(--ground); }
.contact-row.disabled { opacity: 0.55; cursor: not-allowed; }
.contact-main { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }

/* Review */
.kpi-4 { grid-template-columns: repeat(4, 1fr); }
.kpi-free { color: var(--accent-ink); }
.truncate-1 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 18px; }
.sample-grid { display: grid; gap: 16px; }
@media (min-width: 768px) { .sample-grid { grid-template-columns: 1fr 1fr; } }
.sample-wa { background: #ece5dd; border-radius: var(--radius-card); padding: 16px; }
.review-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.wizard-nav { display: flex; justify-content: space-between; margin-top: 24px; gap: 8px; }
.wizard-nav-start { justify-content: flex-start; }

/* Tab upload file (langkah 3) */
.upload-drop {
  border: 1px dashed var(--rule); border-radius: var(--radius);
  padding: 28px 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.upload-icon { color: var(--faint); margin-bottom: 8px; }
.upload-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.file-hidden { display: none; }
.preview-list { display: flex; flex-direction: column; gap: 12px; }
.preview-item { border: 1px solid var(--rule); border-radius: var(--radius); padding: 12px; }
.preview-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.sample-wa { background: #ece5dd; border-radius: var(--radius-card); padding: 16px; white-space: pre-wrap; }

/* Editor pesan fleksibel (langkah 3) */
.msg-edit-card {
  border: 1px dashed var(--rule);
  border-radius: var(--radius);
  padding: 14px 16px;
  background: var(--ground);
}
.msg-edit-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  background: none; border: 0; cursor: pointer;
  color: var(--accent-ink); font-weight: 600; font-size: 14px; padding: 0;
}
.msg-edit-toggle:hover { text-decoration: underline; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip-var {
  display: inline-block; padding: 4px 10px; border-radius: var(--radius-pill);
  background: var(--accent-soft); color: var(--accent-ink);
  font-size: 13px; border: 1px solid transparent;
}
button.chip-var.chip-click { cursor: pointer; }
button.chip-var.chip-click:hover { border-color: var(--accent); }

@media (max-width: 1023px) {
  .kpi-4 { grid-template-columns: repeat(2, 1fr); }
  .kpi-4 > .kpi-cell:nth-child(odd) { border-left: 0; }
  .kpi-4 > .kpi-cell:nth-child(n+3) { border-top: 1px solid var(--rule); }
}
@media (max-width: 639px) {
  .wizard-nav { position: sticky; bottom: 0; background: var(--ground); padding: 12px 0; border-top: 1px solid var(--rule); }
  .wizard-nav .btn { flex: 1; }
  .review-actions .btn { flex: 1; }
  .search-input { width: 100%; }
  .search-wrap { flex: 1; }
}
</style>
