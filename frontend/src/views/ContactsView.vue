<script setup>
import { ref, computed, onMounted } from 'vue'
import { contactsApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { normalizePhone, formatDateTime } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import StatusPill from '../components/StatusPill.vue'
import Pagination from '../components/Pagination.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

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
  formErrors.value = {}
  showModal.value = true
}

function openEdit(c) {
  editing.value = c
  form.value = { name: c.name || '', phone: c.phone || '', tag: c.tag || '', notes: c.notes || '' }
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

async function save() {
  if (!validate()) return
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      phone: form.value.phone,
      tag: form.value.tag.trim() || null,
      notes: form.value.notes.trim() || null,
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
    <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-bold">Kontak</h1>
        <p class="text-sm text-slate-500">Kelola daftar penerima blast. Kontak yang di-blacklist otomatis dikecualikan.</p>
      </div>
      <button
        @click="openCreate"
        class="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm transition-colors"
      >
        ➕ Tambah Kontak
      </button>
    </div>

    <!-- Filter -->
    <div class="flex flex-wrap gap-3 mb-4">
      <input
        v-model="search"
        @input="debouncedLoad"
        type="search"
        placeholder="🔍 Cari nama / nomor…"
        class="field-input !w-64"
      />
      <select v-model="tagFilter" @change="page = 1; load()" class="field-input !w-auto">
        <option value="">Semua tag</option>
        <option v-for="t in availableTags" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-model="blacklistFilter" @change="page = 1; load()" class="field-input !w-auto">
        <option value="">Semua (termasuk blacklist)</option>
        <option value="false">Aktif saja</option>
        <option value="true">Blacklist saja</option>
      </select>
    </div>

    <DataTable
      :loading="loading"
      empty-title="Belum ada kontak"
      empty-hint="Tambahkan kontak pertama Anda untuk mulai membuat campaign."
      empty-icon="👥"
    >
      <template #head>
        <th class="px-4 py-3 font-semibold">Nama</th>
        <th class="px-4 py-3 font-semibold">Nomor</th>
        <th class="px-4 py-3 font-semibold">Tag</th>
        <th class="px-4 py-3 font-semibold">Status</th>
        <th class="px-4 py-3 font-semibold">Diperbarui</th>
        <th class="px-4 py-3 font-semibold text-right">Aksi</th>
      </template>
      <template v-if="contacts.length">
        <tr v-for="c in contacts" :key="c.id" class="border-t border-slate-100 hover:bg-slate-50">
          <td class="px-4 py-3 font-medium">{{ c.name }}</td>
          <td class="px-4 py-3 font-mono text-[13px]">{{ c.phone }}</td>
          <td class="px-4 py-3">
            <span v-if="c.tag" class="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full">{{ c.tag }}</span>
            <span v-else class="text-xs text-slate-400">–</span>
          </td>
          <td class="px-4 py-3">
            <StatusPill :status="c.is_blacklisted ? 'blacklisted' : 'active'" />
          </td>
          <td class="px-4 py-3 text-xs text-slate-500">{{ formatDateTime(c.updated_at || c.created_at) }}</td>
          <td class="px-4 py-3 text-right whitespace-nowrap">
            <button
              @click="toggleBlacklist(c)"
              :title="c.is_blacklisted ? 'Keluarkan dari blacklist' : 'Masukkan ke blacklist'"
              class="text-sm px-2 py-1 rounded hover:bg-slate-100"
            >
              {{ c.is_blacklisted ? '↩️' : '🚫' }}
            </button>
            <button @click="openEdit(c)" title="Ubah" class="text-sm px-2 py-1 rounded hover:bg-slate-100">✏️</button>
            <button @click="confirmDelete = c" title="Hapus" class="text-sm px-2 py-1 rounded hover:bg-red-50">🗑️</button>
          </td>
        </tr>
      </template>
      <template #empty v-if="contacts.length === 0 && !loading">
        <!-- pakai slot default EmptyState dari DataTable -->
      </template>
    </DataTable>
    <Pagination v-if="total > limit" :page="page" :limit="limit" :total="total" @change="(p) => { page = p; load() }" />

    <!-- Modal tambah/ubah -->
    <Modal :open="showModal" :title="editing ? 'Ubah Kontak' : 'Tambah Kontak'" @close="showModal = false">
      <div class="space-y-4">
        <div>
          <label class="field-label">Nama *</label>
          <input v-model="form.name" class="field-input" placeholder="Nama penerima (dipakai untuk {{name}})" />
          <div v-if="formErrors.name" class="field-error">{{ formErrors.name }}</div>
        </div>
        <div>
          <label class="field-label">Nomor WhatsApp *</label>
          <input v-model="form.phone" class="field-input font-mono" placeholder="6281234567890" />
          <div class="field-hint">Format internasional tanpa spasi, mis. 6281234567890.</div>
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
      </div>
      <template #footer>
        <button @click="showModal = false" class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-slate-50">
          Batal
        </button>
        <button
          @click="save"
          :disabled="saving"
          class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50"
        >
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
