<script setup>
/**
 * Modal generik dengan ukuran yang bisa diatur.
 */
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  maxWidth: { type: String, default: 'max-w-lg' },
})
defineEmits(['close'])
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="$emit('close')"></div>
      <div
        class="relative bg-white rounded-2xl shadow-xl w-full max-h-[90vh] flex flex-col"
        :class="maxWidth"
      >
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h3 class="text-lg font-semibold">{{ title }}</h3>
          <button @click="$emit('close')" class="text-slate-400 hover:text-slate-700 text-2xl leading-none" aria-label="Tutup">
            ×
          </button>
        </div>
        <div class="px-6 py-5 overflow-y-auto thin-scroll">
          <slot />
        </div>
        <div v-if="$slots.footer" class="px-6 py-4 border-t border-slate-200 flex justify-end gap-2">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
