<script setup>
import { ref, computed, onMounted } from 'vue'
import { settingsApi } from '../api/client'
import { useToast } from '../stores/useToast'

const toast = useToast()
const entries = ref([]) // [{key, value, is_secret, updated_at}]
const loading = ref(false)
const search = ref('')
const editingKey = ref(null)
const draftValue = ref('')
const draftError = ref('')
const saving = ref(false)

/* ------------------------- Section AI (Gemini) ------------------------- */
const GEMINI_MODELS = [
  'gemini-2.5-flash',
  'gemini-2.5-flash-lite',
  'gemini-2.5-pro',
  'gemini-2.0-flash',
  'gemini-2.0-flash-lite',
  'gemini-1.5-flash',
  'gemini-1.5-pro',
]
const AI_KEYS = ['gemini.api_key', 'gemini.model']

const geminiKeyEntry = computed(() => entries.value.find((e) => e.key === 'gemini.api_key'))
const geminiModelEntry = computed(() => entries.value.find((e) => e.key === 'gemini.model'))
const geminiKeySet = computed(() => !!(geminiKeyEntry.value && geminiKeyEntry.value.value))

const keyInput = ref('')
const keyEditing = ref(false)
const keySaving = ref(false)
const modelValue = ref('')
const modelCustom = ref('')
const modelSaving = ref(false)
const testLoading = ref(false)
const testResult = ref(null)

const isCustomModel = computed(() => modelValue.value === '__custom')
const effectiveModel = computed(() => (isCustomModel.value ? modelCustom.value.trim() : modelValue.value))

function syncGeminiState() {
  const m = geminiModelEntry.value
  const v = String(m?.value ?? '')
  if (GEMINI_MODELS.includes(v)) {
    modelValue.value = v
    modelCustom.value = ''
  } else {
    modelValue.value = '__custom'
    modelCustom.value = v
  }
}

async function saveGeminiKey() {
  const v = keyInput.value.trim()
  if (!v) {
    toast.warning('Isi dulu API key-nya.')
    return
  }
  keySaving.value = true
  try {
    const updated = await settingsApi.update('gemini.api_key', v)
    const e = geminiKeyEntry.value
    if (e) e.value = updated.value
    keyInput.value = ''
    keyEditing.value = false
    toast.success('API key Gemini tersimpan ✓')
  } finally {
    keySaving.value = false
  }
}

async function clearGeminiKey() {
  keySaving.value = true
  try {
    const updated = await settingsApi.update('gemini.api_key', '')
    const e = geminiKeyEntry.value
    if (e) e.value = updated.value
    keyEditing.value = false
    toast.success('API key dihapus — kembali memakai GEMINI_API_KEY dari environment (bila ada).')
  } finally {
    keySaving.value = false
  }
}

async function saveGeminiModel() {
  const v = effectiveModel.value
  if (!v) {
    toast.warning('Pilih atau isi nama model dulu.')
    return
  }
  modelSaving.value = true
  try {
    await settingsApi.update('gemini.model', v)
    const e = geminiModelEntry.value
    if (e) e.value = v
    toast.success(`Model Gemini diubah ke "${v}" ✓`)
  } finally {
    modelSaving.value = false
  }
}

async function testGemini() {
  testLoading.value = true
  testResult.value = null
  try {
    testResult.value = await settingsApi.testGemini()
  } finally {
    testLoading.value = false
  }
}

/**
 * Metadata tampilan per key (dari design section 2.1).
 * Key yang tidak dikenal tetap bisa diedit sebagai JSON mentah.
 */
const KEY_META = {
  'wa.provider': { label: 'Provider default', desc: 'official atau unofficial — default tiap campaign baru', type: 'select', options: ['official', 'unofficial'] },
  'wa.rate_limit_per_hour': { label: 'Batas rate per jam', desc: 'Token bucket pengaman anti-ban (default 300)', type: 'number' },
  'wa.delay_min_sec': { label: 'Jeda minimum (detik)', desc: 'Jeda acak antar pesan, batas bawah (default 5)', type: 'number' },
  'wa.delay_max_sec': { label: 'Jeda maksimum (detik)', desc: 'Jeda acak antar pesan, batas atas (default 15)', type: 'number' },
  'wa.price_per_message_idr': { label: 'Tarif per pesan (Rp)', desc: 'JSON per kategori: marketing, utility, authentication, service', type: 'json' },
  'wa.daily_limit': { label: 'Limit harian nomor', desc: 'Batas tier nomor (250 → 2000 → …)', type: 'number' },
}

function unwrap(entry) {
  // Backend menyimpan value sebagai JSONB — tampilkan nilai mentahnya
  if (entry && typeof entry === 'object' && 'key' in entry) {
    const v = entry.value
    return { key: entry.key, value: v?.value ?? v, is_secret: !!entry.is_secret, updated_at: entry.updated_at }
  }
  return entry
}

function displayValue(v) {
  if (v === null || v === undefined) return '–'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function metaFor(key) {
  return KEY_META[key] || { label: key, desc: 'Pengaturan operasional', type: 'json' }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  // gemini.api_key & gemini.model dikelola di section AI khusus di atas
  return entries.value.filter(
    (e) => !AI_KEYS.includes(e.key) && (!q || e.key.toLowerCase().includes(q))
  )
})

async function load() {
  loading.value = true
  try {
    const data = await settingsApi.list()
    // Terima array [{key, value}] maupun object {key: value}
    if (Array.isArray(data)) {
      entries.value = data.map(unwrap)
    } else if (data && typeof data === 'object') {
      entries.value = Object.entries(data).map(([key, value]) => ({
        key,
        value: value?.value ?? value,
        updated_at: value?.updated_at,
      }))
    } else {
      entries.value = []
    }
    syncGeminiState()
  } finally {
    loading.value = false
  }
}

function startEdit(e) {
  editingKey.value = e.key
  draftError.value = ''
  const meta = metaFor(e.key)
  draftValue.value = meta.type === 'json' ? JSON.stringify(e.value, null, 2) : displayValue(e.value)
}

function cancelEdit() {
  editingKey.value = null
  draftValue.value = ''
  draftError.value = ''
}

async function saveEdit(e) {
  const meta = metaFor(e.key)
  let value
  try {
    if (meta.type === 'number') {
      value = Number(draftValue.value)
      if (Number.isNaN(value)) throw new Error('Harus berupa angka.')
    } else if (meta.type === 'json') {
      value = JSON.parse(draftValue.value)
    } else {
      value = draftValue.value
    }
  } catch (err) {
    draftError.value = 'Nilai tidak valid: ' + err.message
    return
  }
  saving.value = true
  try {
    await settingsApi.update(e.key, value)
    e.value = value
    toast.success(`Pengaturan “${e.key}” diperbarui.`)
    cancelEdit()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="max-w-4xl">
    <div class="mb-6">
      <h1 class="text-2xl font-bold">Pengaturan</h1>
      <p class="text-sm text-slate-500">Konfigurasi operasional. API key AI tidak pernah ditampilkan utuh & tidak masuk audit log.</p>
    </div>

    <!-- ============ AI: Google Gemini (Google AI Studio) ============ -->
    <div class="bg-white rounded-xl border border-slate-200 p-5 mb-6">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-1">
        <h2 class="text-lg font-semibold">🤖 AI — Google Gemini</h2>
        <button
          @click="testGemini"
          :disabled="testLoading"
          class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-50"
        >
          {{ testLoading ? 'Mengetes…' : '🔌 Test koneksi' }}
        </button>
      </div>
      <p class="text-xs text-slate-500 mb-4">
        Dipakai untuk ekstraksi variabel AI di wizard campaign. Ambil API key gratis di
        <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" class="text-emerald-700 underline">Google AI Studio → Get API Key</a>.
        Kosongkan key untuk kembali memakai <code class="font-mono">GEMINI_API_KEY</code> dari environment.
      </p>

      <div v-if="testResult" class="mb-4 text-sm rounded-lg px-3 py-2 border"
           :class="testResult.ok ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-red-50 border-red-200 text-red-800'">
        <span v-if="testResult.ok">✅ Koneksi OK — model <b class="font-mono">{{ testResult.model }}</b> (sumber: {{ testResult.source }}) merespons: “{{ testResult.reply }}”</span>
        <span v-else>❌ Gagal — model <b class="font-mono">{{ testResult.model }}</b> (sumber: {{ testResult.source }}): {{ testResult.error }}</span>
      </div>

      <div class="grid md:grid-cols-2 gap-5">
        <div>
          <label class="field-label">API Key</label>
          <div v-if="geminiKeySet && !keyEditing" class="flex flex-wrap items-center gap-2">
            <code class="font-mono text-sm bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">{{ geminiKeyEntry.value }}</code>
            <span class="text-xs text-emerald-700 font-medium">tersimpan ✓</span>
            <button @click="keyEditing = true; keyInput = ''" class="text-sm text-emerald-700 underline">Ganti</button>
            <button @click="clearGeminiKey" :disabled="keySaving" class="text-sm text-red-600 underline disabled:opacity-50">Hapus</button>
          </div>
          <div v-else class="flex flex-wrap gap-2">
            <input v-model="keyInput" type="password" placeholder="Tempel API key dari AI Studio…" class="field-input font-mono !w-72" autocomplete="off" />
            <button @click="saveGeminiKey" :disabled="keySaving || !keyInput.trim()" class="btn-primary disabled:opacity-50">
              {{ keySaving ? 'Menyimpan…' : 'Simpan' }}
            </button>
            <button v-if="geminiKeySet" @click="keyEditing = false; keyInput = ''" class="px-3 py-2 text-sm rounded-lg border border-slate-300 hover:bg-slate-50">Batal</button>
          </div>
          <p v-if="!geminiKeySet && !keyEditing" class="text-xs text-amber-700 mt-1.5">⚠️ Belum diatur — AI nonaktif sampai key diisi (atau via ENV).</p>
        </div>

        <div>
          <label class="field-label">Model</label>
          <div class="flex flex-wrap gap-2">
            <select v-model="modelValue" class="field-input !w-56 font-mono text-sm">
              <option v-for="m in GEMINI_MODELS" :key="m" :value="m">{{ m }}</option>
              <option value="__custom">Kustom…</option>
            </select>
            <input v-if="isCustomModel" v-model="modelCustom" type="text" placeholder="nama-model-kustom" class="field-input font-mono text-sm !w-56" />
            <button @click="saveGeminiModel" :disabled="modelSaving || !effectiveModel" class="btn-primary disabled:opacity-50">
              {{ modelSaving ? 'Menyimpan…' : 'Simpan' }}
            </button>
          </div>
          <p class="text-xs text-slate-500 mt-1.5">Model untuk ekstraksi variabel. <span class="font-mono">gemini-2.5-flash</span> cepat & murah untuk tugas ini.</p>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <input v-model="search" type="search" placeholder="🔍 Cari key…" class="field-input !w-64" />
    </div>

    <div v-if="loading" class="text-sm text-slate-500 text-center py-10">Memuat pengaturan…</div>
    <div v-else-if="!filtered.length" class="text-sm text-slate-400 text-center py-10">Tidak ada pengaturan yang cocok.</div>

    <div v-else class="space-y-3">
      <div v-for="e in filtered" :key="e.key" class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="font-mono text-sm font-semibold text-emerald-800">{{ e.key }}</div>
            <div class="text-sm font-medium mt-0.5">{{ metaFor(e.key).label }}</div>
            <div class="text-xs text-slate-500">{{ metaFor(e.key).desc }}</div>
          </div>
          <button
            v-if="editingKey !== e.key"
            @click="startEdit(e)"
            class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50"
          >
            ✏️ Ubah
          </button>
        </div>

        <div v-if="editingKey !== e.key" class="mt-2">
          <code class="text-sm bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 block break-all">{{ displayValue(e.value) }}</code>
        </div>

        <div v-else class="mt-3 space-y-2">
          <select
            v-if="metaFor(e.key).type === 'select'"
            v-model="draftValue"
            class="field-input !w-auto"
          >
            <option v-for="o in metaFor(e.key).options" :key="o" :value="o">{{ o }}</option>
          </select>
          <input
            v-else-if="metaFor(e.key).type === 'number' || metaFor(e.key).type === 'text'"
            v-model="draftValue"
            :type="metaFor(e.key).type === 'number' ? 'number' : 'text'"
            class="field-input"
          />
          <textarea
            v-else
            v-model="draftValue"
            rows="4"
            class="field-input font-mono text-sm"
            placeholder='{"marketing": 627.33}'
          ></textarea>
          <div v-if="draftError" class="field-error">{{ draftError }}</div>
          <div class="flex gap-2">
            <button
              @click="saveEdit(e)"
              :disabled="saving"
              class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50"
            >
              {{ saving ? 'Menyimpan…' : 'Simpan' }}
            </button>
            <button @click="cancelEdit" class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-slate-50">
              Batal
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
