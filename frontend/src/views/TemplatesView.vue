<script setup>
import { ref, computed, onMounted } from 'vue'
import { templatesApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { formatDateTime, extractVariables, wrapVar, truncate } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const toast = useToast()
const templates = ref([])
const loading = ref(false)

const selected = ref(null)       // template terpilih (detail)
const versions = ref([])
const versionsLoading = ref(false)

const showModal = ref(false)
const editing = ref(null)
const form = ref({ name: '', description: '', body: '' })
const formErrors = ref({})
const saving = ref(false)

const showVersionModal = ref(false)
const newVersionBody = ref('')
const creatingVersion = ref(false)

const confirmDelete = ref(null)
const deleting = ref(false)

// Variabel dari body yang sedang diketik (preview live)
const liveVariables = computed(() => extractVariables(form.body))
const versionVariables = computed(() => extractVariables(newVersionBody.value))

async function load() {
  loading.value = true
  try {
    const { items } = await templatesApi.list()
    templates.value = items
    if (selected.value) {
      const fresh = items.find((t) => t.id === selected.value.id)
      if (fresh) selected.value = { ...selected.value, ...fresh }
    }
  } finally {
    loading.value = false
  }
}

async function select(t) {
  selected.value = t
  versionsLoading.value = true
  versions.value = []
  try {
    const { items } = await templatesApi.versions(t.id)
    versions.value = items
  } finally {
    versionsLoading.value = false
  }
}

/** Ambil info versi terbaru dari payload list/detail (defensif terhadap beberapa bentuk). */
function latestVersion(t) {
  return t.latest_version || t.current_version || t.version || null
}

function openCreate() {
  editing.value = null
  form.value = { name: '', description: '', body: '' }
  formErrors.value = {}
  showModal.value = true
}

function openEdit(t) {
  editing.value = t
  form.value = { name: t.name || '', description: t.description || '', body: '' }
  formErrors.value = {}
  showModal.value = true
}

function validate() {
  const errs = {}
  if (!form.value.name.trim()) errs.name = 'Nama template wajib diisi.'
  if (!editing.value && !form.value.body.trim()) errs.body = 'Isi pesan wajib diisi untuk versi pertama.'
  formErrors.value = errs
  return Object.keys(errs).length === 0
}

async function save() {
  if (!validate()) return
  saving.value = true
  try {
    if (editing.value) {
      // Kontrak: PUT hanya mengubah name/description, bukan body
      await templatesApi.update(editing.value.id, {
        name: form.value.name.trim(),
        description: form.value.description.trim() || null,
      })
      toast.success('Template diperbarui.')
    } else {
      await templatesApi.create({
        name: form.value.name.trim(),
        description: form.value.description.trim() || null,
        body: form.value.body,
      })
      toast.success('Template dibuat beserta versi 1.')
    }
    showModal.value = false
    await load()
    if (selected.value) select(selected.value)
  } finally {
    saving.value = false
  }
}

async function createVersion() {
  if (!newVersionBody.value.trim()) {
    toast.error('Isi pesan versi baru wajib diisi.')
    return
  }
  creatingVersion.value = true
  try {
    const v = await templatesApi.createVersion(selected.value.id, newVersionBody.value)
    toast.success(`Versi ${v.version_number ?? 'baru'} berhasil dibuat (variabel diekstrak otomatis).`)
    newVersionBody.value = ''
    showVersionModal.value = false
    await load()
    select(selected.value)
  } finally {
    creatingVersion.value = false
  }
}

async function doDelete() {
  if (!confirmDelete.value) return
  deleting.value = true
  try {
    await templatesApi.remove(confirmDelete.value.id)
    toast.success('Template dihapus.')
    confirmDelete.value = null
    if (selected.value?.id === confirmDelete.value?.id) selected.value = null
    load()
  } finally {
    deleting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-bold">Template</h1>
        <p class="text-sm text-slate-500">Template pesan dengan variabel {{nama}}. Setiap ubah isi = versi baru (immutable).</p>
      </div>
      <button
        @click="openCreate"
        class="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm transition-colors"
      >
        ➕ Template Baru
      </button>
    </div>

    <div class="grid lg:grid-cols-5 gap-4">
      <!-- Daftar template -->
      <div class="lg:col-span-2">
        <DataTable :loading="loading" empty-title="Belum ada template" empty-hint="Buat template pertama untuk dipakai campaign." empty-icon="📝">
          <template #head>
            <th class="px-4 py-3 font-semibold">Nama</th>
            <th class="px-4 py-3 font-semibold">Versi</th>
            <th class="px-4 py-3 font-semibold">Status</th>
          </template>
          <template v-if="templates.length">
            <tr
              v-for="t in templates"
              :key="t.id"
              @click="select(t)"
              class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
              :class="selected?.id === t.id ? 'bg-emerald-50' : ''"
            >
              <td class="px-4 py-3">
                <div class="font-medium">{{ t.name }}</div>
                <div class="text-xs text-slate-400">{{ truncate(t.description, 50) }}</div>
              </td>
              <td class="px-4 py-3 text-sm">
                v{{ latestVersion(t)?.version_number ?? '1' }}
              </td>
              <td class="px-4 py-3">
                <StatusPill :status="latestVersion(t)?.approval_status || 'draft'" />
              </td>
            </tr>
          </template>
        </DataTable>
      </div>

      <!-- Detail template -->
      <div class="lg:col-span-3">
        <div v-if="!selected" class="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-400 text-sm">
          Pilih template di sebelah kiri untuk melihat detail & riwayat versi.
        </div>

        <div v-else class="bg-white rounded-xl border border-slate-200 p-6">
          <div class="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div>
              <h2 class="text-xl font-bold">{{ selected.name }}</h2>
              <p v-if="selected.description" class="text-sm text-slate-500 mt-1">{{ selected.description }}</p>
              <div class="text-xs text-slate-400 mt-1">Diperbarui {{ formatDateTime(selected.updated_at) }}</div>
            </div>
            <div class="flex gap-2">
              <button @click="openEdit(selected)" class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50">✏️ Ubah</button>
              <button @click="confirmDelete = selected" class="px-3 py-1.5 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50">🗑️ Hapus</button>
            </div>
          </div>

          <div class="flex items-center justify-between mb-2">
            <h3 class="font-semibold">Riwayat Versi</h3>
            <button
              @click="showVersionModal = true"
              class="px-3 py-1.5 text-sm rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
            >
              ➕ Versi Baru
            </button>
          </div>

          <div v-if="versionsLoading" class="text-sm text-slate-500 py-4 text-center">Memuat versi…</div>
          <div v-else-if="!versions.length" class="text-sm text-slate-400 py-4 text-center">Belum ada versi.</div>
          <div v-else class="space-y-3">
            <details
              v-for="v in versions"
              :key="v.id || v.version_number"
              class="border border-slate-200 rounded-lg"
              :open="v.version_number === versions[0]?.version_number"
            >
              <summary class="px-4 py-3 cursor-pointer flex flex-wrap items-center gap-3 hover:bg-slate-50 rounded-lg">
                <span class="font-semibold text-sm">Versi {{ v.version_number }}</span>
                <StatusPill :status="v.approval_status || 'draft'" />
                <span v-if="v.provider_category" class="text-xs bg-slate-100 px-2 py-0.5 rounded-full">{{ v.provider_category }}</span>
                <span v-if="v.provider_template_name" class="text-xs text-slate-500 font-mono">{{ v.provider_template_name }}</span>
                <span class="ml-auto text-xs text-slate-400">{{ formatDateTime(v.created_at) }}</span>
              </summary>
              <div class="px-4 pb-4 pt-1 border-t border-slate-100">
                <pre class="whitespace-pre-wrap text-sm bg-slate-50 rounded-lg p-3 mt-3 font-sans">{{ v.body }}</pre>
                <div class="mt-3">
                  <div class="text-xs font-semibold text-slate-600 mb-1">Variabel terekstrak:</div>
                  <div v-if="(v.variables || extractVariables(v.body)).length" class="flex flex-wrap gap-1.5">
                    <code
                      v-for="name in (v.variables || extractVariables(v.body))"
                      :key="name"
                      class="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded"
                    >{{ wrapVar(name) }}</code>
                  </div>
                  <div v-else class="text-xs text-slate-400">Tidak ada variabel.</div>
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal tambah/ubah template -->
    <Modal :open="showModal" :title="editing ? 'Ubah Template' : 'Template Baru'" @close="showModal = false" maxWidth="max-w-2xl">
      <div class="space-y-4">
        <div>
          <label class="field-label">Nama *</label>
          <input v-model="form.name" class="field-input" placeholder="mis. Promo Diskon" />
          <div v-if="formErrors.name" class="field-error">{{ formErrors.name }}</div>
        </div>
        <div>
          <label class="field-label">Deskripsi</label>
          <textarea v-model="form.description" rows="2" class="field-input" placeholder="Kegunaan template ini"></textarea>
        </div>
        <div v-if="!editing">
          <label class="field-label">Isi pesan (versi 1) *</label>
          <textarea v-model="form.body" rows="6" class="field-input font-mono" placeholder="Halo {{name}}, ada promo {{promo}} khusus untukmu!"></textarea>
          <div class="field-hint">Gunakan {{nama_variabel}} untuk bagian yang dinamis.</div>
          <div v-if="formErrors.body" class="field-error">{{ formErrors.body }}</div>
          <div v-if="liveVariables.length" class="mt-2">
            <div class="text-xs font-semibold text-slate-600 mb-1">Variabel terdeteksi:</div>
            <div class="flex flex-wrap gap-1.5">
              <code v-for="name in liveVariables" :key="name" class="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded">{{ wrapVar(name) }}</code>
            </div>
          </div>
        </div>
        <div v-else class="text-sm text-slate-500 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          ℹ️ Isi pesan tidak bisa diubah langsung — buat <b>Versi Baru</b> dari panel detail untuk mengubah isi.
        </div>
      </div>
      <template #footer>
        <button @click="showModal = false" class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-slate-50">Batal</button>
        <button @click="save" :disabled="saving" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50">
          {{ saving ? 'Menyimpan…' : 'Simpan' }}
        </button>
      </template>
    </Modal>

    <!-- Modal versi baru -->
    <Modal :open="showVersionModal" title="Buat Versi Baru" @close="showVersionModal = false" maxWidth="max-w-2xl">
      <div class="space-y-3">
        <div class="text-sm text-slate-500">Versi lama bersifat immutable — campaign yang sudah memakai versi lama tidak berubah.</div>
        <label class="field-label">Isi pesan *</label>
        <textarea v-model="newVersionBody" rows="8" class="field-input font-mono" placeholder="Halo {{name}}, …"></textarea>
        <div v-if="versionVariables.length">
          <div class="text-xs font-semibold text-slate-600 mb-1">Variabel terdeteksi:</div>
          <div class="flex flex-wrap gap-1.5">
            <code v-for="name in versionVariables" :key="name" class="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded">{{ wrapVar(name) }}</code>
          </div>
        </div>
      </div>
      <template #footer>
        <button @click="showVersionModal = false" class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-slate-50">Batal</button>
        <button @click="createVersion" :disabled="creatingVersion" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50">
          {{ creatingVersion ? 'Membuat…' : 'Buat Versi' }}
        </button>
      </template>
    </Modal>

    <!-- Konfirmasi hapus -->
    <ConfirmDialog
      :open="!!confirmDelete"
      title="Hapus template?"
      :message="`Template “${confirmDelete?.name}” beserta seluruh versinya akan dihapus. Template yang sudah dipakai campaign tidak bisa dihapus.`"
      confirm-label="Ya, hapus"
      danger
      :loading="deleting"
      @cancel="confirmDelete = null"
      @confirm="doDelete"
    />
  </div>
</template>
