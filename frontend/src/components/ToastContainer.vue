<script setup>
import { useToast } from '../stores/useToast'

const { toasts, remove } = useToast()

const styles = {
  success: 'bg-emerald-600',
  error: 'bg-red-600',
  warning: 'bg-amber-500',
  info: 'bg-sky-600',
}
const icons = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
}
</script>

<template>
  <div class="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast-in text-white rounded-xl shadow-lg px-4 py-3 flex gap-3 items-start"
      :class="styles[t.type] || styles.info"
      role="alert"
    >
      <span class="text-lg leading-none mt-0.5">{{ icons[t.type] || icons.info }}</span>
      <div class="min-w-0 flex-1">
        <div class="font-semibold text-sm">{{ t.title }}</div>
        <div class="text-sm opacity-95 break-words">{{ t.message }}</div>
      </div>
      <button @click="remove(t.id)" class="opacity-70 hover:opacity-100 text-lg leading-none" aria-label="Tutup">
        ×
      </button>
    </div>
  </div>
</template>
