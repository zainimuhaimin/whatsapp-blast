<script setup>
import { useToast } from '../stores/useToast'
import Icon from './Icon.vue'

const { toasts, remove } = useToast()

const styles = {
  success: { bg: 'var(--pill-positive-bg)', ink: 'var(--pill-positive-ink)', icon: 'check' },
  error: { bg: 'var(--pill-negative-bg)', ink: 'var(--pill-negative-ink)', icon: 'alert' },
  warning: { bg: 'var(--pill-warning-bg)', ink: 'var(--pill-warning-ink)', icon: 'alert' },
  info: { bg: 'var(--pill-info-bg)', ink: 'var(--pill-info-ink)', icon: 'info' },
}
</script>

<template>
  <div class="toast-wrap">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast-in toast"
      :style="{ background: (styles[t.type] || styles.info).bg, color: (styles[t.type] || styles.info).ink }"
      role="alert"
    >
      <Icon :name="(styles[t.type] || styles.info).icon" :size="16" class="toast-icon" />
      <div class="min-w-0 flex-1">
        <div class="font-semibold text-sm">{{ t.title }}</div>
        <div class="text-sm break-words opacity-90">{{ t.message }}</div>
      </div>
      <button @click="remove(t.id)" class="toast-close" aria-label="Tutup">
        <Icon name="x" :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.toast-wrap {
  position: fixed;
  bottom: 16px; right: 16px;
  z-index: 100;
  display: flex; flex-direction: column; gap: 8px;
  width: 20rem; max-width: calc(100vw - 2rem);
}
.toast {
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 12px 14px;
  display: flex; gap: 10px; align-items: flex-start;
}
.toast-icon { flex: none; margin-top: 2px; }
.toast-close {
  background: transparent; border: 0; cursor: pointer;
  color: inherit; opacity: 0.6; padding: 2px;
}
.toast-close:hover { opacity: 1; }
</style>
