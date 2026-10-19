<script setup>
import { ref, onMounted } from 'vue'
import { testNumbersApi } from '../api/client'
import { useToast } from '../stores/useToast'
import { normalizePhone, formatDateTime } from '../utils/format'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import StatusPill from '../components/StatusPill.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import Icon from '../components/Icon.vue'

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
    <div class="title-row">
      <div>
        <h1 class="page-title">Nomor test</h1>
        <p class="page-sub">Sandbox: campaign mode test hanya mengirim ke nomor aktif di sini.</p>
      </div>
      <button @click="openCreate" class="btn btn-accent">
        <Icon name="plus" :size="15" /> Tambah nomor test
      </button>
    </div>

    <DataTable
      :loading="loading"
      stack
      empty-title="Belum ada nomor test"
      empty-hint="Tambahkan nomor WhatsApp Anda sendiri untuk uji coba blast."
      empty-icon="flask"
    >
      <template #head>
        <th>Label</th>
        <th>Nomor</th>
        <th>Status</th>
        <th>Ditambahkan</th>
        <th class="num">Aksi</th>
      </template>
      <template v-if="numbers.length">
        <tr v-for="t in numbers" :key="t.id">
          <td class="row-title">{{ t.label }}</td>
          <td class="mono">{{ t.phone }}</td>
          <td><StatusPill :status="t.is_active === false ? 'inactive' : 'active'" /></td>
          <td class="card-label text-xs">{{ formatDateTime(t.created_at) }}</td>
          <td class="num whitespace-nowrap">
            <button
              @click="toggleActive(t)"
              :title="t.is_active === false ? 'Aktifkan' : 'Nonaktifkan'"
              class="icon-btn-sm"
            >
              <Icon :name="t.is_active === false ? 'play' : 'pause'" :size="15" />
            </button>
            <button @click="openEdit(t)" title="Ubah" class="icon-btn-sm">
              <Icon name="pencil" :size="15" />
            </button>
            <button @click="confirmDelete = t" title="Hapus" class="icon-btn-sm is-danger">
              <Icon name="trash" :size="15" />
            </button>
          </td>
        </tr>
      </template>
    </DataTable>

    <Modal :open="showModal" :title="editing ? 'Ubah nomor test' : 'Tambah nomor test'" @close="showModal = false">
      <div class="form-grid">
        <div>
          <label class="field-label">Label *</label>
          <input v-model="form.label" class="field-input" placeholder="mis. HP saya, HP istri" />
          <div v-if="formErrors.label" class="field-error">{{ formErrors.label }}</div>
        </div>
        <div>
          <label class="field-label">Nomor WhatsApp *</label>
          <input v-model="form.phone" class="field-input mono" placeholder="6281234567890" />
          <div class="field-hint">Format internasional tanpa spasi, mis. 6281234567890.</div>
          <div v-if="formErrors.phone" class="field-error">{{ formErrors.phone }}</div>
        </div>
        <label v-if="editing" class="check-row-sm">
          <input type="checkbox" v-model="form.is_active" class="check-accent" />
          <span class="text-sm">Nomor aktif (dipakai mode test)</span>
        </label>
      </div>
      <template #footer>
        <button @click="showModal = false" class="btn btn-secondary">Batal</button>
        <button @click="save" :disabled="saving" class="btn btn-accent">
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

<style scoped>
.title-row {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 12px; margin-bottom: 24px;
}
.form-grid { display: grid; gap: 16px; }
.check-row-sm { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.check-accent { accent-color: var(--accent); width: 16px; height: 16px; }
.icon-btn-sm {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: var(--radius-control);
  color: var(--muted); background: transparent; border: 0; cursor: pointer;
}
.icon-btn-sm:hover { background: var(--raised); color: var(--text); }
.icon-btn-sm.is-danger:hover { background: var(--pill-negative-bg); color: var(--pill-negative-ink); }
</style>
