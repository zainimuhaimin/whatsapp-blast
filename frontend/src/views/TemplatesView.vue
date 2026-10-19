<script setup>
import { ref, computed, onMounted } from 'vue'
import { templatesApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { formatDateTime, extractVariables, wrapVar, truncate } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import Icon from '../components/Icon.vue'

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
    <div class="title-row">
      <div>
        <h1 class="page-title">Template</h1>
        <p class="page-sub">Template pesan dengan variabel {{nama}}. Setiap ubah isi = versi baru.</p>
      </div>
      <button @click="openCreate" class="btn btn-accent">
        <Icon name="plus" :size="15" /> Template baru
      </button>
    </div>

    <div class="tpl-layout">
      <!-- Daftar template -->
      <div class="tpl-list" :class="{ 'hidden-mobile': selected }">
        <DataTable :loading="loading" empty-title="Belum ada template" empty-hint="Buat template pertama untuk dipakai campaign." empty-icon="chat">
          <template #head>
            <th>Nama</th>
            <th>Versi</th>
            <th>Status</th>
          </template>
          <template v-if="templates.length">
            <tr
              v-for="t in templates"
              :key="t.id"
              @click="select(t)"
              class="row-selectable"
              :class="{ 'row-selected': selected?.id === t.id }"
            >
              <td>
                <div class="row-title">{{ t.name }}</div>
                <div class="row-sub">{{ truncate(t.description, 50) }}</div>
              </td>
              <td class="text-sm num">v{{ latestVersion(t)?.version_number ?? '1' }}</td>
              <td>
                <StatusPill :status="latestVersion(t)?.approval_status || 'draft'" />
              </td>
            </tr>
          </template>
        </DataTable>
      </div>

      <!-- Detail template -->
      <div class="tpl-detail" :class="{ 'show-mobile': selected }">
        <button v-if="selected" @click="selected = null" class="back-link back-mobile">
          <Icon name="chevron-left" :size="14" /> Daftar template
        </button>

        <div v-if="!selected" class="empty-inline">
          Pilih template di sebelah kiri untuk melihat detail & riwayat versi.
        </div>

        <div v-else class="card card-pad">
          <div class="detail-head">
            <div class="min-w-0">
              <h2 class="section-title text-lg">{{ selected.name }}</h2>
              <p v-if="selected.description" class="card-label mt-1">{{ selected.description }}</p>
              <div class="card-label mt-1 text-xs">Diperbarui {{ formatDateTime(selected.updated_at) }}</div>
            </div>
            <div class="detail-actions">
              <button @click="openEdit(selected)" class="btn btn-secondary btn-sm">
                <Icon name="pencil" :size="14" /> Ubah
              </button>
              <button @click="confirmDelete = selected" class="btn btn-danger btn-sm">Hapus</button>
            </div>
          </div>

          <div class="detail-head mt-6 mb-2">
            <h3 class="section-title">Riwayat versi</h3>
            <button @click="showVersionModal = true" class="btn btn-accent btn-sm">
              <Icon name="plus" :size="14" /> Versi baru
            </button>
          </div>

          <div v-if="versionsLoading" class="card-label py-4 text-center">Memuat versi…</div>
          <div v-else-if="!versions.length" class="empty-inline">Belum ada versi.</div>
          <div v-else class="version-list">
            <details
              v-for="v in versions"
              :key="v.id || v.version_number"
              class="version-item"
              :open="v.version_number === versions[0]?.version_number"
            >
              <summary class="version-summary">
                <span class="font-semibold text-sm">Versi {{ v.version_number }}</span>
                <StatusPill :status="v.approval_status || 'draft'" />
                <span v-if="v.provider_category" class="pill pill-neutral">{{ v.provider_category }}</span>
                <span v-if="v.provider_template_name" class="mono text-xs card-label">{{ v.provider_template_name }}</span>
                <span class="card-label text-xs ml-auto">{{ formatDateTime(v.created_at) }}</span>
              </summary>
              <div class="version-body-wrap">
                <pre class="version-pre">{{ v.body }}</pre>
                <div class="mt-3">
                  <div class="card-label mb-1">Variabel terekstrak:</div>
                  <div v-if="(v.variables || extractVariables(v.body)).length" class="chip-row">
                    <code
                      v-for="name in (v.variables || extractVariables(v.body))"
                      :key="name"
                      class="var-chip"
                    >{{ wrapVar(name) }}</code>
                  </div>
                  <div v-else class="card-label text-xs">Tidak ada variabel.</div>
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal tambah/ubah template -->
    <Modal :open="showModal" :title="editing ? 'Ubah template' : 'Template baru'" @close="showModal = false" maxWidth="max-w-2xl">
      <div class="form-grid">
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
          <textarea v-model="form.body" rows="6" class="field-input mono" placeholder="Halo {{name}}, ada promo {{promo}} khusus untukmu!"></textarea>
          <div class="field-hint">Gunakan {{nama_variabel}} untuk bagian yang dinamis.</div>
          <div v-if="formErrors.body" class="field-error">{{ formErrors.body }}</div>
          <div v-if="liveVariables.length" class="mt-2">
            <div class="card-label mb-1">Variabel terdeteksi:</div>
            <div class="chip-row">
              <code v-for="name in liveVariables" :key="name" class="var-chip">{{ wrapVar(name) }}</code>
            </div>
          </div>
        </div>
        <div v-else class="alert-warning">
          <Icon name="info" :size="15" class="mt-0.5 shrink-0" />
          <span class="text-sm">Isi pesan tidak bisa diubah langsung. Buat <b>Versi Baru</b> dari panel detail untuk mengubah isi.</span>
        </div>
      </div>
      <template #footer>
        <button @click="showModal = false" class="btn btn-secondary">Batal</button>
        <button @click="save" :disabled="saving" class="btn btn-accent">
          {{ saving ? 'Menyimpan…' : 'Simpan' }}
        </button>
      </template>
    </Modal>

    <!-- Modal versi baru -->
    <Modal :open="showVersionModal" title="Buat versi baru" @close="showVersionModal = false" maxWidth="max-w-2xl">
      <div class="form-grid">
        <div class="card-label text-sm">Versi lama bersifat immutable. Campaign yang sudah memakai versi lama tidak berubah.</div>
        <div>
          <label class="field-label">Isi pesan *</label>
          <textarea v-model="newVersionBody" rows="8" class="field-input mono" placeholder="Halo {{name}}, …"></textarea>
        </div>
        <div v-if="versionVariables.length">
          <div class="card-label mb-1">Variabel terdeteksi:</div>
          <div class="chip-row">
            <code v-for="name in versionVariables" :key="name" class="var-chip">{{ wrapVar(name) }}</code>
          </div>
        </div>
      </div>
      <template #footer>
        <button @click="showVersionModal = false" class="btn btn-secondary">Batal</button>
        <button @click="createVersion" :disabled="creatingVersion" class="btn btn-accent">
          {{ creatingVersion ? 'Membuat…' : 'Buat versi' }}
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

<style scoped>
.title-row {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 12px; margin-bottom: 24px;
}
.tpl-layout { display: grid; gap: 16px; }
@media (min-width: 1024px) { .tpl-layout { grid-template-columns: 2fr 3fr; } }
.row-selectable { cursor: pointer; }
.row-selectable.row-selected td { background: var(--accent-soft); }
.form-grid { display: grid; gap: 16px; }
.detail-head { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 12px; }
.detail-actions { display: flex; gap: 8px; }
.btn-sm { min-height: 32px; padding: 0 12px; font-size: 13px; }
.version-list { display: grid; gap: 12px; }
.version-item { border: 1px solid var(--border); border-radius: var(--radius-card); overflow: hidden; }
.version-summary {
  padding: 12px 16px; cursor: pointer;
  display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
  list-style: none;
}
.version-summary::-webkit-details-marker { display: none; }
.version-summary:hover { background: var(--ground); }
.version-body-wrap { padding: 4px 16px 16px; border-top: 1px solid var(--rule); }
.version-pre {
  white-space: pre-wrap; font-size: 14px;
  background: var(--ground); border-radius: var(--radius-control);
  padding: 12px; margin-top: 12px; font-family: var(--font);
}
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.var-chip {
  font-size: 12px; font-family: var(--font-mono);
  background: var(--accent-soft); color: var(--accent-ink);
  border: 1px solid var(--accent-track);
  padding: 2px 8px; border-radius: 4px;
}
.back-link {
  display: none; align-items: center; gap: 4px;
  font-size: 13px; color: var(--muted); background: none; border: 0; cursor: pointer;
  margin-bottom: 12px; padding: 0;
}
@media (max-width: 1023px) {
  .hidden-mobile { display: none; }
  .tpl-detail { display: none; }
  .tpl-detail.show-mobile { display: block; }
  .back-mobile { display: inline-flex; }
}
</style>
