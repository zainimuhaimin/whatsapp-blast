<script setup>
/**
 * Modal generik dengan ukuran yang bisa diatur.
 */
import Icon from './Icon.vue'

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
        class="modal-panel"
        :class="maxWidth"
      >
        <div class="modal-head">
          <h3 class="section-title">{{ title }}</h3>
          <button @click="$emit('close')" class="modal-x" aria-label="Tutup">
            <Icon name="x" :size="18" />
          </button>
        </div>
        <div class="modal-body thin-scroll">
          <slot />
        </div>
        <div v-if="$slots.footer" class="modal-foot">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
