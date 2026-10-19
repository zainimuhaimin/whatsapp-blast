<script setup>
/**
 * DataTable generik: header, baris, loading, empty state.
 * Kolom didefinisikan lewat slot agar fleksibel.
 */
import EmptyState from './EmptyState.vue'

defineProps({
  loading: { type: Boolean, default: false },
  emptyTitle: { type: String, default: 'Belum ada data' },
  emptyHint: { type: String, default: '' },
  emptyIcon: { type: String, default: '📭' },
})
</script>

<template>
  <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
    <div class="overflow-x-auto thin-scroll">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <slot name="head" />
          </tr>
        </thead>
        <tbody v-if="!loading && $slots.default">
          <slot />
        </tbody>
      </table>
    </div>

    <div v-if="loading" class="py-10 text-center text-slate-500 text-sm">
      <div class="animate-spin inline-block w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full mb-2"></div>
      <div>Memuat data…</div>
    </div>

    <slot name="empty">
      <EmptyState
        v-if="!loading && !$slots.default"
        :title="emptyTitle"
        :hint="emptyHint"
        :icon="emptyIcon"
      />
    </slot>
  </div>
</template>
