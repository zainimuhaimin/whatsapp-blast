<script setup>
/**
 * DataTable generik: header, baris, loading, empty state.
 * Kolom didefinisikan lewat slot agar fleksibel.
 * Di HP (<640px): thead disembunyikan, baris jadi dua baris
 * (identitas + angka kunci di baris 1 via .cell-main).
 */
import EmptyState from './EmptyState.vue'

defineProps({
  loading: { type: Boolean, default: false },
  emptyTitle: { type: String, default: 'Belum ada data' },
  emptyHint: { type: String, default: '' },
  emptyIcon: { type: String, default: 'inbox' },
  /** Bila true: di HP baris jadi blok dua baris (tanpa thead). */
  stack: { type: Boolean, default: false },
})
</script>

<template>
  <div class="tbl-wrap">
    <div class="thin-scroll" :class="stack ? '' : 'tbl-scroll'">
      <table class="tbl" :class="{ 'tbl-stack': stack }">
        <thead>
          <tr>
            <slot name="head" />
          </tr>
        </thead>
        <tbody v-if="!loading && $slots.default">
          <slot />
        </tbody>
      </table>
    </div>

    <div v-if="loading" class="tbl-loading">
      <div v-for="i in 4" :key="i" class="tbl-skeleton-row">
        <span class="skeleton" style="width: 32%; height: 14px"></span>
        <span class="skeleton" style="width: 14%; height: 14px"></span>
        <span class="skeleton" style="width: 20%; height: 14px"></span>
      </div>
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

<style scoped>
.tbl-loading { padding: 8px 0; }
.tbl-skeleton-row {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border-top: 1px solid var(--rule);
}
.tbl-skeleton-row:first-child { border-top: 0; }
</style>
