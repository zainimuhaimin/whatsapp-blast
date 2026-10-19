<script setup>
/**
 * EmptyState: section kosong — bingkai + satu kalimat (aturan app-screen),
 * tanpa emoji. Ikon outline netral.
 */
import Icon from './Icon.vue'

defineProps({
  title: { type: String, default: 'Belum ada data' },
  hint: { type: String, default: '' },
  icon: { type: String, default: 'inbox' },
})
</script>

<template>
  <div class="empty">
    <span class="empty-icon"><Icon :name="icon" :size="22" /></span>
    <div class="empty-title">{{ title }}</div>
    <div v-if="hint" class="empty-hint">{{ hint }}</div>
    <div v-if="$slots.action" class="empty-action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.empty {
  padding: 40px 24px;
  text-align: center;
  border: 1px dashed var(--control);
  border-radius: var(--radius-card);
  margin: 16px;
}
.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px; height: 44px;
  border-radius: 50%;
  background: var(--raised);
  color: var(--faint);
  margin-bottom: 12px;
}
.empty-title { font-size: 14px; font-weight: 600; }
.empty-hint { font-size: 13px; color: var(--muted); margin-top: 4px; }
.empty-action { margin-top: 14px; }
</style>
