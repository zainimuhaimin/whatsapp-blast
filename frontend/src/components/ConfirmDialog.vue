<script setup>
/**
 * ConfirmDialog: dialog konfirmasi dua pilihan, dipakai untuk aksi destruktif
 * maupun konfirmasi final (mis. "Konfirmasi & Blast").
 */
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
      <div class="relative bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div class="text-4xl mb-3">{{ danger ? '⚠️' : '❓' }}</div>
        <h3 class="text-lg font-semibold mb-2">{{ title }}</h3>
        <p class="text-sm text-slate-600 mb-6 whitespace-pre-line">{{ message }}</p>
        <div class="flex justify-end gap-2">
          <button
            @click="$emit('cancel')"
            :disabled="loading"
            class="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
          >
            {{ cancelLabel }}
          </button>
          <button
            @click="$emit('confirm')"
            :disabled="loading"
            class="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            :class="danger ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-600 hover:bg-emerald-700'"
          >
            {{ loading ? 'Memproses…' : confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
