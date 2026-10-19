<script setup>
import { ref, computed, onMounted } from 'vue'
import { settingsApi } from '../api/client'
import { useToast } from '../stores/useToast'

const toast = useToast()
const entries = ref([]) // [{key, value, updated_at}]
const loading = ref(false)
const search = ref('')
const editingKey = ref(null)
const draftValue = ref('')
const draftError = ref('')
const saving = ref(false)

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
  'gemini.model': { label: 'Model Gemini', desc: 'Nama model untuk ekstraksi variabel AI', type: 'text' },
}

function unwrap(entry) {
  // Backend menyimpan value sebagai JSONB — tampilkan nilai mentahnya
  if (entry && typeof entry === 'object' && 'key' in entry) {
    const v = entry.value
    return { key: entry.key, value: v?.value ?? v, updated_at: entry.updated_at }
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
  return entries.value.filter((e) => !q || e.key.toLowerCase().includes(q))
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
      <p class="text-sm text-slate-500">Konfigurasi operasional (bukan secret — secret disimpan via environment variable).</p>
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
