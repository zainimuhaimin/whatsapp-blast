<script setup>
import { ref, onMounted } from 'vue'
import { testNumbersApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { normalizePhone, formatDateTime } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const toast = useToast()
const numbers = ref([])
const loading = ref(false)

const showModal = ref(false)
const editing = ref(null)
const form = ref({ label: '', phone: '', is_active: true })
const formErrors = ref({})
const saving = ref(false)

const confirmDelete = ref(null)
const deleting = ref(false)

async function load() {
  loading.value = true
  try {
    const { items } = await testNumbersApi.list()
    numbers.value = items || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { label: '', phone: '', is_active: true }
  formErrors.value = {}
  showModal.value = true
}

function openEdit(t) {
  editing.value = t
  form.value = { label: t.label || '', phone: t.phone || '', is_active: t.is_active !== false }
  formErrors.value = {}
  showModal.value = true
}

function validate() {
  const errs = {}
  if (!form.value.label.trim()) errs.label = 'Label wajib diisi (mis. “HP saya”).'
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
      label: form.value.label.trim(),
      phone: form.value.phone,
      is_active: form.value.is_active,
    }
    if (editing.value) {
      await testNumbersApi.update(editing.value.id, payload)
      toast.success('Nomor test diperbarui.')
    } else {
      await testNumbersApi.create({ label: payload.label, phone: payload.phone })
      toast.success('Nomor test ditambahkan.')
    }
    showModal.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleActive(t) {
  try {
    await testNumbersApi.update(t.id, { is_active: !t.is_active })
    t.is_active = !t.is_active
    toast.success(t.is_active ? 'Nomor test diaktifkan.' : 'Nomor test dinonaktifkan.')
  } catch { /* toast ditangani client */ }
}

async function doDelete() {
  if (!confirmDelete.value) return
  deleting.value = true
  try {
    await testNumbersApi.remove(confirmDelete.value.id)
    toast.success('Nomor test dihapus.')
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
        <h1 class="text-2xl font-bold">Nomor Test</h1>
        <p class="text-sm text-slate-500">Daftar nomor untuk sandbox / mode test. Campaign mode test hanya mengirim ke nomor-nomor aktif di sini.</p>
      </div>
      <button
        @click="openCreate"
        class="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm transition-colors"
      >
        ➕ Tambah Nomor Test
      </button>
    </div>

    <DataTable
      :loading="loading"
      empty-title="Belum ada nomor test"
      empty-hint="Tambahkan nomor WhatsApp Anda sendiri untuk uji coba blast."
      empty-icon="🧪"
    >
      <template #head>
        <th class="px-4 py-3 font-semibold">Label</th>
        <th class="px-4 py-3 font-semibold">Nomor</th>
        <th class="px-4 py-3 font-semibold">Status</th>
        <th class="px-4 py-3 font-semibold">Ditambahkan</th>
        <th class="px-4 py-3 font-semibold text-right">Aksi</th>
      </template>
      <template v-if="numbers.length">
        <tr v-for="t in numbers" :key="t.id" class="border-t border-slate-100 hover:bg-slate-50">
          <td class="px-4 py-3 font-medium">{{ t.label }}</td>
          <td class="px-4 py-3 font-mono text-[13px]">{{ t.phone }}</td>
          <td class="px-4 py-3"><StatusPill :status="t.is_active === false ? 'inactive' : 'active'" /></td>
          <td class="px-4 py-3 text-xs text-slate-500">{{ formatDateTime(t.created_at) }}</td>
          <td class="px-4 py-3 text-right whitespace-nowrap">
            <button
              @click="toggleActive(t)"
              :title="t.is_active === false ? 'Aktifkan' : 'Nonaktifkan'"
              class="text-sm px-2 py-1 rounded hover:bg-slate-100"
            >
              {{ t.is_active === false ? '▶️' : '⏸️' }}
            </button>
            <button @click="openEdit(t)" title="Ubah" class="text-sm px-2 py-1 rounded hover:bg-slate-100">✏️</button>
            <button @click="confirmDelete = t" title="Hapus" class="text-sm px-2 py-1 rounded hover:bg-red-50">🗑️</button>
          </td>
        </tr>
      </template>
    </DataTable>

    <Modal :open="showModal" :title="editing ? 'Ubah Nomor Test' : 'Tambah Nomor Test'" @close="showModal = false">
      <div class="space-y-4">
        <div>
          <label class="field-label">Label *</label>
          <input v-model="form.label" class="field-input" placeholder="mis. HP saya, HP istri" />
          <div v-if="formErrors.label" class="field-error">{{ formErrors.label }}</div>
        </div>
        <div>
          <label class="field-label">Nomor WhatsApp *</label>
          <input v-model="form.phone" class="field-input font-mono" placeholder="6281234567890" />
          <div class="field-hint">Format internasional tanpa spasi, mis. 6281234567890.</div>
          <div v-if="formErrors.phone" class="field-error">{{ formErrors.phone }}</div>
        </div>
        <label v-if="editing" class="flex items-center gap-2 text-sm">
          <input type="checkbox" v-model="form.is_active" class="accent-emerald-600 w-4 h-4" />
          Nomor aktif (dipakai mode test)
        </label>
      </div>
      <template #footer>
        <button @click="showModal = false" class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-slate-50">Batal</button>
        <button @click="save" :disabled="saving" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50">
          {{ saving ? 'Menyimpan…' : 'Simpan' }}
        </button>
      </template>
    </Modal>

    <ConfirmDialog
      :open="!!confirmDelete"
      title="Hapus nomor test?"
      :message="`Nomor “${confirmDelete?.label}” (${confirmDelete?.phone}) akan dihapus dari daftar test.`"
      confirm-label="Ya, hapus"
      danger
      :loading="deleting"
      @cancel="confirmDelete = null"
      @confirm="doDelete"
    />
  </div>
</template>
