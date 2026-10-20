<script setup>
import { ref, computed, onMounted } from 'vue'
import { contactsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { normalizePhone, formatPhone, formatDateTime } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import StatusPill from '../components/StatusPill.vue'
import Pagination from '../components/Pagination.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import Icon from '../components/Icon.vue'

const toast = useToast()
const contacts = ref([])
const total = ref(0)
const loading = ref(false)

const search = ref('')
const tagFilter = ref('')
const blacklistFilter = ref('') // '', 'true', 'false'
const page = ref(1)
const limit = 20

const showModal = ref(false)
const editing = ref(null)
const form = ref({ name: '', phone: '', tag: '', notes: '' })
const dataRows = ref([]) // [{key, value}] editor atribut dinamis
const formErrors = ref({})
const saving = ref(false)

const confirmDelete = ref(null)
const deleting = ref(false)

const availableTags = computed(() => {
  const s = new Set()
  for (const c of contacts.value) if (c.tag) s.add(c.tag)
  return [...s].sort()
})

let searchTimer = null
function debouncedLoad() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 350)
}

async function load() {
  loading.value = true
  try {
    const q = { search: search.value, tag: tagFilter.value, page: page.value, limit }
    if (blacklistFilter.value !== '') q.blacklisted = blacklistFilter.value
    const { items, total: t } = await contactsApi.list(q)
    contacts.value = items
    total.value = t
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', phone: '', tag: '', notes: '' }
  dataRows.value = []
  formErrors.value = {}
  showModal.value = true
}

function openEdit(c) {
  editing.value = c
  form.value = { name: c.name || '', phone: c.phone || '', tag: c.tag || '', notes: c.notes || '' }
  dataRows.value = Object.entries(c.data || {}).map(([key, value]) => ({ key, value: String(value ?? '') }))
  formErrors.value = {}
  showModal.value = true
}

function validate() {
  const errs = {}
  if (!form.value.name.trim()) errs.name = 'Nama wajib diisi.'
  const { ok, phone, error } = normalizePhone(form.value.phone)
  if (!ok) errs.phone = error
  else form.value.phone = phone
  formErrors.value = errs
  return Object.keys(errs).length === 0
}

function buildDataObject() {
  const obj = {}
  for (const r of dataRows.value) {
    const k = String(r.key || '').trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '')
    if (k) obj[k] = String(r.value ?? '')
  }
  return obj
}
function addDataRow() { dataRows.value.push({ key: '', value: '' }) }
function removeDataRow(i) { dataRows.value.splice(i, 1) }

async function save() {
  if (!validate()) return
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      phone: form.value.phone,
      tag: form.value.tag.trim() || null,
      notes: form.value.notes.trim() || null,
      data: buildDataObject(),
    }
    if (editing.value) {
      await contactsApi.update(editing.value.id, payload)
      toast.success('Kontak berhasil diperbarui.')
    } else {
      await contactsApi.create(payload)
      toast.success('Kontak berhasil ditambahkan.')
    }
    showModal.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleBlacklist(c) {
  const next = !c.is_blacklisted
  try {
    await contactsApi.toggleBlacklist(c.id, next)
    c.is_blacklisted = next
    toast.success(next ? 'Kontak dimasukkan ke blacklist (tidak akan menerima blast).' : 'Kontak dikeluarkan dari blacklist.')
  } catch { /* toast error sudah ditangani client */ }
}

async function doDelete() {
  if (!confirmDelete.value) return
  deleting.value = true
  try {
    await contactsApi.remove(confirmDelete.value.id)
    toast.success('Kontak dihapus.')
    confirmDelete.value = null
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
        <h1 class="page-title">Kontak</h1>
        <p class="page-sub">Daftar penerima blast. Kontak blacklist otomatis dikecualikan.</p>
      </div>
      <button @click="openCreate" class="btn btn-accent">
        <Icon name="plus" :size="15" /> Tambah kontak
      </button>
    </div>

    <!-- Filter -->
    <div class="toolbar">
      <div class="search-wrap">
        <Icon name="search" :size="15" class="search-icon" />
        <input
          v-model="search"
          @input="debouncedLoad"
          type="search"
          placeholder="Cari nama / nomor…"
          class="field-input search-input"
        />
      </div>
      <select v-model="tagFilter" @change="page = 1; load()" class="field-input filter-select">
        <option value="">Semua tag</option>
        <option v-for="t in availableTags" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-model="blacklistFilter" @change="page = 1; load()" class="field-input filter-select">
        <option value="">Semua (termasuk blacklist)</option>
        <option value="false">Aktif saja</option>
        <option value="true">Blacklist saja</option>
      </select>
      <span class="toolbar-count">{{ total }} kontak</span>
    </div>

    <DataTable
      :loading="loading"
      stack
      empty-title="Belum ada kontak"
      empty-hint="Tambahkan kontak pertama Anda untuk mulai membuat campaign."
      empty-icon="users"
    >
      <template #head>
        <th>Nama</th>
        <th>Nomor</th>
        <th>Tag</th>
        <th>Status</th>
        <th>Diperbarui</th>
        <th class="num">Aksi</th>
      </template>
      <template v-if="contacts.length">
        <tr v-for="c in contacts" :key="c.id">
          <td>
            <div class="row-title">{{ c.name }}</div>
            <div class="cell-line2 mono">{{ formatPhone(c.phone) }}</div>
            <div v-if="c.data && Object.keys(c.data).length" class="cell-line2">
              <span v-for="(v, k) in c.data" :key="k" class="pill pill-neutral mr-1" :title="`${k}: ${v}`">{{ k }}</span>
            </div>
          </td>
          <td class="mono cell-desktop">{{ formatPhone(c.phone) }}</td>
          <td>
            <span v-if="c.tag" class="pill pill-neutral">{{ c.tag }}</span>
            <span v-else class="cell-muted">–</span>
          </td>
          <td>
            <StatusPill :status="c.is_blacklisted ? 'blacklisted' : 'active'" />
          </td>
          <td class="card-label text-xs">{{ formatDateTime(c.updated_at || c.created_at) }}</td>
          <td class="num whitespace-nowrap row-actions">
            <button
              @click="toggleBlacklist(c)"
              :title="c.is_blacklisted ? 'Keluarkan dari blacklist' : 'Masukkan ke blacklist'"
              class="icon-btn-sm"
              :class="{ 'is-on': c.is_blacklisted }"
            >
              <Icon name="ban" :size="15" />
            </button>
            <button @click="openEdit(c)" title="Ubah" class="icon-btn-sm">
              <Icon name="pencil" :size="15" />
            </button>
            <button @click="confirmDelete = c" title="Hapus" class="icon-btn-sm is-danger">
              <Icon name="trash" :size="15" />
            </button>
          </td>
        </tr>
      </template>
      <template #empty v-if="contacts.length === 0 && !loading">
        <!-- pakai slot default EmptyState dari DataTable -->
      </template>
    </DataTable>
    <Pagination v-if="total > limit" :page="page" :limit="limit" :total="total" @change="(p) => { page = p; load() }" />

    <!-- Modal tambah/ubah -->
    <Modal :open="showModal" :title="editing ? 'Ubah kontak' : 'Tambah kontak'" @close="showModal = false">
      <div class="form-grid">
        <div>
          <label class="field-label">Nama *</label>
          <input v-model="form.name" class="field-input" placeholder="Nama penerima (dipakai untuk {{name}})" />
          <div v-if="formErrors.name" class="field-error">{{ formErrors.name }}</div>
        </div>
        <div>
          <label class="field-label">Nomor WhatsApp *</label>
          <input v-model="form.phone" class="field-input mono" placeholder="6281234567890" />
          <div class="field-hint">Otomatis diseragamkan: <span class="mono">0812…</span> dan <span class="mono">+62812…</span> tersimpan sebagai satu nomor yang sama.</div>
          <div v-if="formErrors.phone" class="field-error">{{ formErrors.phone }}</div>
        </div>
        <div>
          <label class="field-label">Tag</label>
          <input v-model="form.tag" class="field-input" placeholder="mis. pelanggan, reseller" />
        </div>
        <div>
          <label class="field-label">Catatan</label>
          <textarea v-model="form.notes" rows="2" class="field-input" placeholder="Catatan opsional"></textarea>
        </div>
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="field-label mb-0">Data dinamis</label>
            <button @click="addDataRow" type="button" class="btn btn-tertiary text-sm">
              <Icon name="plus" :size="14" /> Tambah
            </button>
          </div>
          <p class="field-hint mb-2">Atribut bebas per kontak (mis. <span class="mono">alamat</span>, <span class="mono">nama_pos</span>) — bisa dipakai sebagai variabel campaign. Nomor telepon adalah kunci; key baru dari file/AI otomatis ditambahkan ke sini.</p>
          <div v-if="!dataRows.length" class="card-label">Belum ada data dinamis.</div>
          <div v-for="(r, i) in dataRows" :key="i" class="flex gap-2 mb-2">
            <input v-model="r.key" class="field-input mono" placeholder="key, mis. alamat" />
            <input v-model="r.value" class="field-input" placeholder="nilai" />
            <button @click="removeDataRow(i)" type="button" class="btn btn-tertiary" title="Hapus">
              <Icon name="trash" :size="14" />
            </button>
          </div>
        </div>
      </div>
      <template #footer>
        <button @click="showModal = false" class="btn btn-secondary">Batal</button>
        <button @click="save" :disabled="saving" class="btn btn-accent">
          {{ saving ? 'Menyimpan…' : 'Simpan' }}
        </button>
      </template>
    </Modal>

    <!-- Konfirmasi hapus -->
    <ConfirmDialog
      :open="!!confirmDelete"
      title="Hapus kontak?"
      :message="`Kontak “${confirmDelete?.name}” (${confirmDelete?.phone}) akan dihapus permanen. Kontak yang sudah dipakai campaign tidak bisa dihapus.`"
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
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
.search-wrap { position: relative; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--faint); pointer-events: none; }
.search-input { width: 240px; padding-left: 36px; min-height: 34px; }
.filter-select { width: auto; min-height: 34px; }
.toolbar-count { margin-left: auto; font-size: 13px; color: var(--muted); }
.form-grid { display: grid; gap: 16px; }
.cell-muted { color: var(--faint); font-size: 13px; }
.row-actions { min-width: 108px; }
.icon-btn-sm {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: var(--radius-control);
  color: var(--muted); background: transparent; border: 0; cursor: pointer;
}
.icon-btn-sm:hover { background: var(--raised); color: var(--text); }
.icon-btn-sm.is-danger:hover { background: var(--pill-negative-bg); color: var(--pill-negative-ink); }
.icon-btn-sm.is-on { color: var(--pill-negative-ink); background: var(--pill-negative-bg); }
.cell-desktop { display: table-cell; }
@media (max-width: 639px) {
  .cell-desktop { display: none; }
  .row-actions { text-align: left; }
  .search-input { width: 100%; }
  .search-wrap { flex: 1 1 100%; }
  .toolbar-count { margin-left: 0; }
}
</style>
