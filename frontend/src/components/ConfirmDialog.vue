<script setup>
/**
 * ConfirmDialog: dialog konfirmasi dua pilihan, dipakai untuk aksi destruktif
 * maupun konfirmasi final (mis. "Konfirmasi & Blast").
 */
import Icon from './Icon.vue'

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'Konfirmasi' },
  message: { type: String, default: '' },
  confirmLabel: { type: String, default: 'Ya, lanjutkan' },
  cancelLabel: { type: String, default: 'Batal' },
  danger: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})
defineEmits(['confirm', 'cancel'])
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[95] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="$emit('cancel')"></div>
      <div class="modal-panel max-w-md p-5">
        <div class="confirm-icon" :class="danger ? 'is-danger' : 'is-info'">
          <Icon :name="danger ? 'alert' : 'info'" :size="20" />
        </div>
        <h3 class="section-title mt-3 mb-2">{{ title }}</h3>
        <p class="text-sm whitespace-pre-line" style="color: var(--muted)">{{ message }}</p>
        <div class="flex justify-end gap-2 mt-6">
          <button @click="$emit('cancel')" :disabled="loading" class="btn btn-secondary">
            {{ cancelLabel }}
          </button>
          <button
            @click="$emit('confirm')"
            :disabled="loading"
            class="btn"
            :class="danger ? 'btn-danger-fill' : 'btn-accent'"
          >
            {{ loading ? 'Memproses…' : confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.confirm-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 50%;
}
.confirm-icon.is-danger { background: var(--pill-negative-bg); color: var(--pill-negative-ink); }
.confirm-icon.is-info { background: var(--pill-accent-bg); color: var(--accent-ink); }
.btn-danger-fill { background: var(--negative); color: #fff; }
.btn-danger-fill:hover:not(:disabled) { background: #a11e24; }
</style>
