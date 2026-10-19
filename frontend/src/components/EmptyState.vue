<script setup>
defineProps({
  title: { type: String, default: 'Belum ada data' },
  hint: { type: String, default: '' },
  icon: { type: String, default: '📭' },
})
</script>

<template>
  <div class="py-12 px-6 text-center">
    <div class="text-5xl mb-3">{{ icon }}</div>
    <div class="font-semibold text-slate-700">{{ title }}</div>
    <div v-if="hint" class="text-sm text-slate-500 mt-1">{{ hint }}</div>
    <div v-if="$slots.action" class="mt-4">
      <slot name="action" />
    </div>
  </div>
</template>
