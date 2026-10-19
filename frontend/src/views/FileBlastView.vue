<script setup>
/**
 * Blast dari File: tulis pesan bebas -> upload CSV/XLSX -> header kolom
 * menjadi variabel yang bisa ditempel ke pesan -> preview per baris ->
 * buat campaign (masuk ke review wizard seperti biasa).
 */
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { fileUploadsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import Icon from '../components/Icon.vue'
import DataTable from '../components/DataTable.vue'
import EmptyState from '../components/EmptyState.vue'

const router = useRouter()
const toast = useToast()

const message = ref('')
const msgRef = ref(null)

const uploading = ref(false)
const upload = ref(null) // hasil /parse
const phoneVariable = ref('')

const previewing = ref(false)
const previewData = ref(null)

const creating = ref(false)
const campaignName = ref('')
const provider = ref('unofficial')
const isTestMode = ref(true)

const VAR_RE = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g
const msgVars = computed(() => {
  const seen = []
  let m
  VAR_RE.lastIndex = 0
  while ((m = VAR_RE.exec(message.value || ''))) {
    if (!seen.includes(m[1])) seen.push(m[1])
  }
  return seen
})
const wrapVar = (v) => `{{${v}}}`

function insertVariable(v) {
  const tag = wrapVar(v)
  const el = msgRef.value
  if (!el) {
    message.value += tag
    return
  }
  const start = el.selectionStart ?? message.value.length
  const end = el.selectionEnd ?? start
  message.value = message.value.slice(0, start) + tag + message.value.slice(end)
  nextTick(() => {
    el.focus()
    el.selectionStart = el.selectionEnd = start + tag.length
  })
}

async function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  previewData.value = null
  try {
    const res = await fileUploadsApi.parse(file)
    upload.value = res
    phoneVariable.value = res.phone_variable_suggestion || ''
    if (!res.phone_variable_suggestion) {
      toast.error('Kolom nomor telepon tidak terdeteksi otomatis — pilih manual di bawah.')
    } else {
      toast.success(`${res.row_count} baris dibaca dari ${res.filename}.`)
    }
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

function resetUpload() {
  upload.value = null
  phoneVariable.value = ''
  previewData.value = null
}

async function doPreview() {
  if (!message.value.trim()) {
    toast.error('Tulis pesannya dulu.')
    return
  }
  if (!phoneVariable.value) {
    toast.error('Pilih kolom nomor telepon.')
    return
  }
  previewing.value = true
  try {
    previewData.value = await fileUploadsApi.preview(upload.value.upload_id, {
      message: message.value,
      phone_variable: phoneVariable.value,
    })
  } finally {
    previewing.value = false
  }
}

async function doCreate() {
  if (!campaignName.value.trim()) {
    toast.error('Isi nama campaign.')
    return
  }
  if (!message.value.trim()) {
    toast.error('Tulis pesannya dulu.')
    return
  }
  if (!phoneVariable.value) {
    toast.error('Pilih kolom nomor telepon.')
    return
  }
  creating.value = true
  try {
    const res = await fileUploadsApi.createCampaign(upload.value.upload_id, {
      name: campaignName.value.trim(),
      message: message.value,
      phone_variable: phoneVariable.value,
      provider: provider.value,
      is_test_mode: isTestMode.value,
    })
    const warns = []
    if (res.skipped?.length) warns.push(`${res.skipped.length} baris dilewati`)
    if (res.unknown_variables?.length) warns.push(`variabel tak dikenal: ${res.unknown_variables.map(wrapVar).join(', ')}`)
    toast.success(
      `Campaign dibuat: ${res.added} penerima ditambahkan.` + (warns.length ? ` (${warns.join('; ')})` : '')
    )
    router.push(`/campaigns/new?campaign=${res.campaign_id}&step=6`)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="page-title">Blast dari File</h1>
      <p class="page-sub">Tulis pesan bebas, upload CSV/Excel — header kolom otomatis jadi variabel yang bisa ditempel ke pesan.</p>
    </div>

    <!-- 1. Pesan -->
    <section class="card card-pad mb-4">
      <h2 class="section-title mb-1">1. Tulis pesan</h2>
      <p class="card-label mb-3">
        Klik chip kolom (setelah upload file) untuk menempelkan variabel di posisi kursor,
        atau ketik langsung <span class="mono">{{nama_variabel}}</span>.
      </p>
      <textarea
        ref="msgRef"
        v-model="message"
        rows="6"
        class="field-input"
        placeholder="Contoh:&#10;Halo {{nama}},&#10;&#10;Tagihan {{produk}} sebesar {{nominal}} jatuh tempo {{tanggal}}."
      />
      <div v-if="msgVars.length" class="chip-row mt-2">
        <span class="card-label">Variabel di pesan:</span>
        <span v-for="v in msgVars" :key="v" class="mono chip-var">{{ wrapVar(v) }}</span>
      </div>
    </section>

    <!-- 2. Upload -->
    <section class="card card-pad mb-4">
      <h2 class="section-title mb-1">2. Upload file data</h2>
      <p class="card-label mb-3">Format .csv atau .xlsx (maks 10 MB, 5000 baris). Baris pertama dianggap header.</p>

      <div v-if="!upload" class="upload-drop">
        <Icon name="upload" :size="22" class="upload-icon" />
        <label class="btn btn-secondary">
          {{ uploading ? 'Mengunggah…' : 'Pilih file CSV / Excel' }}
          <input type="file" accept=".csv,.xlsx,.xls" class="file-hidden" :disabled="uploading" @change="onFileChange" />
        </label>
        <p class="card-label mt-2">Contoh header: nama | no_hp | alamat — "No. HP" otomatis jadi {{no_hp}}</p>
      </div>

      <div v-else>
        <div class="upload-meta">
          <div>
            <div class="font-semibold text-sm">{{ upload.filename }}</div>
            <div class="card-label">{{ upload.row_count }} baris data</div>
          </div>
          <button @click="resetUpload" class="btn btn-tertiary text-sm">
            <Icon name="x" :size="14" /> Ganti file
          </button>
        </div>

        <div class="mt-3">
          <div class="card-label mb-2">Klik untuk menempel ke pesan:</div>
          <div class="chip-row">
            <button
              v-for="c in upload.columns"
              :key="c.variable"
              @click="insertVariable(c.variable)"
              class="chip-var chip-click"
              :title="`Header asli: ${c.header}`"
            >
              {{ wrapVar(c.variable) }}
            </button>
          </div>
        </div>

        <div class="mt-3 max-w-sm">
          <label class="card-label" for="phone-col">Kolom nomor telepon</label>
          <select id="phone-col" v-model="phoneVariable" class="field-input mt-1">
            <option value="" disabled>— pilih kolom —</option>
            <option v-for="c in upload.columns" :key="c.variable" :value="c.variable">
              {{ c.header }} → {{ wrapVar(c.variable) }}
            </option>
          </select>
        </div>

        <div class="mt-4">
          <div class="card-label mb-2">Contoh 5 baris pertama:</div>
          <DataTable>
            <template #head>
              <th v-for="c in upload.columns" :key="c.variable" class="mono">{{ wrapVar(c.variable) }}</th>
            </template>
            <tr v-for="(row, i) in upload.preview" :key="i">
              <td v-for="c in upload.columns" :key="c.variable" class="text-sm max-w-40 truncate" :title="row[c.variable]">
                {{ row[c.variable] || '–' }}
              </td>
            </tr>
          </DataTable>
        </div>
      </div>
    </section>

    <!-- 3. Preview -->
    <section v-if="upload" class="card card-pad mb-4">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 class="section-title">3. Preview pesan per baris</h2>
        <button @click="doPreview" :disabled="previewing" class="btn btn-secondary text-sm">
          <Icon name="eye" :size="14" /> {{ previewing ? 'Memproses…' : 'Preview 5 baris' }}
        </button>
      </div>

      <EmptyState
        v-if="!previewData"
        icon="chat"
        title="Belum ada preview"
        hint="Klik 'Preview 5 baris' untuk melihat hasil render pesan per baris data."
      />

      <div v-else>
        <div v-if="previewData.unknown_variables?.length" class="alert-warning mb-3">
          <Icon name="alert" :size="15" class="mt-0.5 shrink-0" />
          <span>Variabel ini dipakai di pesan tapi <b>tidak ada</b> di file: {{ previewData.unknown_variables.map(wrapVar).join(', ') }} — akan ter-render kosong.</span>
        </div>
        <div class="card-label mb-3">
          {{ previewData.valid_rows }} baris bernomor valid
          <template v-if="previewData.skipped_rows"> · {{ previewData.skipped_rows }} baris nomornya tidak valid (otomatis dilewati)</template>
        </div>
        <div class="preview-list">
          <div v-for="p in previewData.previews" :key="p.row" class="preview-item">
            <div class="preview-head">
              <span class="font-semibold text-sm">Baris {{ p.row }}</span>
              <span class="mono text-xs card-label">{{ p.phone || 'nomor tidak valid' }}</span>
              <span v-if="!p.phone_valid" class="pill pill-negative">dilewati</span>
            </div>
            <div class="sample-wa">{{ p.message }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 4. Buat campaign -->
    <section v-if="upload" class="card card-pad mb-4">
      <h2 class="section-title mb-3">4. Buat campaign</h2>
      <div class="max-w-md">
        <label class="card-label" for="fb-name">Nama campaign</label>
        <input id="fb-name" v-model="campaignName" class="field-input mt-1 mb-3" placeholder="mis. Blast tagihan Januari" />

        <div class="card-label mb-2">Jalur pengiriman</div>
        <div class="provider-grid mb-3">
          <label class="provider-card" :class="{ selected: provider === 'official' }">
            <div class="provider-head">
              <input type="radio" v-model="provider" value="official" class="radio-accent" />
              <span class="font-semibold text-sm">Resmi — Meta Cloud API</span>
            </div>
          </label>
          <label class="provider-card" :class="{ selected: provider === 'unofficial' }">
            <div class="provider-head">
              <input type="radio" v-model="provider" value="unofficial" class="radio-accent" />
              <span class="font-semibold text-sm">Non-resmi — Baileys (gratis)</span>
            </div>
          </label>
        </div>

        <label class="check-row mb-4">
          <input type="checkbox" v-model="isTestMode" class="check-accent" />
          <span class="text-sm">
            <span class="font-semibold">Mode test</span>
            <span class="block card-label mt-0.5">Bila aktif, pesan hanya dikirim ke nomor test terdaftar.</span>
          </span>
        </label>

        <button @click="doCreate" :disabled="creating" class="btn btn-accent">
          <Icon name="send" :size="15" /> {{ creating ? 'Membuat…' : 'Buat campaign & lanjut ke review' }}
        </button>
        <p class="card-label mt-2">Setelah dibuat, Anda diarahkan ke halaman review untuk memeriksa sebelum konfirmasi kirim.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip-var {
  display: inline-block; padding: 4px 10px; border-radius: var(--radius-pill);
  background: var(--accent-soft); color: var(--accent-ink);
  font-size: 13px; border: 1px solid transparent;
}
button.chip-var.chip-click { cursor: pointer; }
button.chip-var.chip-click:hover { border-color: var(--accent); }
.upload-drop {
  border: 1px dashed var(--rule); border-radius: var(--radius);
  padding: 28px 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.upload-icon { color: var(--faint); margin-bottom: 8px; }
.upload-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.preview-list { display: flex; flex-direction: column; gap: 12px; }
.preview-item { border: 1px solid var(--rule); border-radius: var(--radius); padding: 12px; }
.preview-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.provider-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
@media (max-width: 640px) { .provider-grid { grid-template-columns: 1fr; } }
.file-hidden { display: none; }
.sample-wa { background: #ece5dd; border-radius: var(--radius-card); padding: 16px; white-space: pre-wrap; }
</style>
