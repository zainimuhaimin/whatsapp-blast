<script setup>
import { ref, computed, onMounted } from 'vue'
import { settingsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import Icon from '../components/Icon.vue'

const toast = useToast()
const entries = ref([]) // [{key, value, is_secret, updated_at}]
const loading = ref(false)
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
    toast.success('API key Gemini tersimpan.')
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
    toast.success('API key dihapus. Kembali memakai GEMINI_API_KEY dari environment (bila ada).')
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
    toast.success(`Model Gemini diubah ke "${v}".`)
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

const filtered = computed(() =>
  // gemini.api_key & gemini.model dikelola di section AI khusus di atas
  entries.value.filter((e) => !AI_KEYS.includes(e.key))
)

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
  <div class="settings-col">
    <div class="mb-8">
      <h1 class="page-title">Pengaturan</h1>
      <p class="page-sub">Konfigurasi operasional. API key AI tidak pernah ditampilkan utuh & tidak masuk audit log.</p>
    </div>

    <div v-if="loading" class="card-label text-center py-10">Memuat pengaturan…</div>

    <template v-else>
      <!-- ============ AI: Google Gemini ============ -->
      <section class="setting-row">
        <div class="setting-label">
          <h2 class="setting-title">AI — Google Gemini</h2>
          <p class="setting-desc">
            Dipakai untuk ekstraksi variabel AI di wizard campaign. Ambil API key gratis di
            <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" class="row-link">Google AI Studio</a>.
            Kosongkan key untuk kembali memakai <code class="mono">GEMINI_API_KEY</code> dari environment.
          </p>
          <button @click="testGemini" :disabled="testLoading" class="btn btn-secondary btn-sm mt-3">
            <Icon name="zap" :size="14" /> {{ testLoading ? 'Mengetes…' : 'Test koneksi' }}
          </button>
        </div>
        <div class="setting-panel">
          <div v-if="testResult" class="mb-4 text-sm rounded-lg px-3 py-2 border"
               :class="testResult.ok ? 'alert-positive' : 'alert-negative'" style="display:block">
            <span v-if="testResult.ok">Koneksi OK. Model <b class="mono">{{ testResult.model }}</b> (sumber: {{ testResult.source }}) merespons: “{{ testResult.reply }}”</span>
            <span v-else>Gagal. Model <b class="mono">{{ testResult.model }}</b> (sumber: {{ testResult.source }}): {{ testResult.error }}</span>
          </div>

          <div class="ai-grid">
            <div>
              <label class="field-label">API key</label>
              <div v-if="geminiKeySet && !keyEditing" class="key-set">
                <code class="mono key-masked">{{ geminiKeyEntry.value }}</code>
                <span class="pill pill-positive">tersimpan</span>
                <button @click="keyEditing = true; keyInput = ''" class="btn-tertiary text-sm">Ganti</button>
                <button @click="clearGeminiKey" :disabled="keySaving" class="btn-tertiary text-sm" style="color: var(--negative)">Hapus</button>
              </div>
              <div v-else class="key-edit">
                <input v-model="keyInput" type="password" placeholder="Tempel API key dari AI Studio…" class="field-input mono" autocomplete="off" />
                <div class="key-actions">
                  <button @click="saveGeminiKey" :disabled="keySaving || !keyInput.trim()" class="btn btn-accent btn-sm">
                    {{ keySaving ? 'Menyimpan…' : 'Simpan' }}
                  </button>
                  <button v-if="geminiKeySet" @click="keyEditing = false; keyInput = ''" class="btn btn-secondary btn-sm">Batal</button>
                </div>
              </div>
              <p v-if="!geminiKeySet && !keyEditing" class="field-hint" style="color: var(--warning)">Belum diatur. AI nonaktif sampai key diisi (atau via ENV).</p>
            </div>

            <div>
              <label class="field-label">Model</label>
              <div class="key-edit">
                <select v-model="modelValue" class="field-input mono text-sm">
                  <option v-for="m in GEMINI_MODELS" :key="m" :value="m">{{ m }}</option>
                  <option value="__custom">Kustom…</option>
                </select>
                <input v-if="isCustomModel" v-model="modelCustom" type="text" placeholder="nama-model-kustom" class="field-input mono text-sm" />
                <div class="key-actions">
                  <button @click="saveGeminiModel" :disabled="modelSaving || !effectiveModel" class="btn btn-accent btn-sm">
                    {{ modelSaving ? 'Menyimpan…' : 'Simpan' }}
                  </button>
                </div>
              </div>
              <p class="field-hint"><span class="mono">gemini-2.5-flash</span> cepat & murah untuk ekstraksi variabel.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- ============ Pengaturan operasional ============ -->
      <section v-for="e in filtered" :key="e.key" class="setting-row">
        <div class="setting-label">
          <h2 class="setting-title">{{ metaFor(e.key).label }}</h2>
          <p class="setting-desc">{{ metaFor(e.key).desc }}</p>
          <code class="mono setting-key">{{ e.key }}</code>
        </div>
        <div class="setting-panel">
          <template v-if="editingKey !== e.key">
            <div class="setting-value">
              <code class="mono value-code">{{ displayValue(e.value) }}</code>
              <button @click="startEdit(e)" class="btn btn-secondary btn-sm">
                <Icon name="pencil" :size="13" /> Ubah
              </button>
            </div>
          </template>
          <template v-else>
            <select
              v-if="metaFor(e.key).type === 'select'"
              v-model="draftValue"
              class="field-input w-auto"
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
              class="field-input mono text-sm"
              placeholder='{"marketing": 627.33}'
            ></textarea>
            <div v-if="draftError" class="field-error">{{ draftError }}</div>
            <div class="key-actions mt-3">
              <button @click="saveEdit(e)" :disabled="saving" class="btn btn-accent btn-sm">
                {{ saving ? 'Menyimpan…' : 'Simpan' }}
              </button>
              <button @click="cancelEdit" class="btn btn-secondary btn-sm">Batal</button>
            </div>
          </template>
        </div>
      </section>

      <div v-if="!filtered.length" class="empty-inline">Tidak ada pengaturan operasional lain.</div>
    </template>
  </div>
</template>

<style scoped>
.settings-col { max-width: 1152px; margin: 0 auto; }
.setting-row {
  display: grid; gap: 16px;
  padding: 32px 0;
  border-top: 1px solid var(--border);
}
.setting-row:first-of-type { border-top: 0; padding-top: 0; }
@media (min-width: 900px) {
  .setting-row { grid-template-columns: 400px 1fr; gap: 32px; }
}
.setting-title { font-size: 16px; font-weight: 500; margin: 0; padding-top: 6px; }
.setting-desc { font-size: 14px; color: var(--muted); margin: 6px 0 0; line-height: 21px; }
.setting-key { display: inline-block; margin-top: 8px; font-size: 12px; color: var(--faint); }
.setting-panel {
  background: var(--raised);
  border-radius: 16px;
  padding: 16px;
}
.setting-value { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.value-code {
  font-size: 13px; background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-control); padding: 8px 12px; display: block;
  word-break: break-all; flex: 1;
}
.btn-sm { min-height: 32px; padding: 0 12px; font-size: 13px; }
.ai-grid { display: grid; gap: 20px; }
@media (min-width: 700px) { .ai-grid { grid-template-columns: 1fr 1fr; } }
.key-set { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.key-masked {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-control); padding: 8px 12px; font-size: 13px;
}
.key-edit { display: grid; gap: 8px; }
.key-actions { display: flex; gap: 8px; }
</style>
