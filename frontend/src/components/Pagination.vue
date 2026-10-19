<script setup>
/**
 * Pagination sederhana: info halaman + tombol sebelum/berikutnya + lompat halaman.
 */
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, default: 1 },
  limit: { type: Number, default: 20 },
  total: { type: Number, default: 0 },
})
defineEmits(['change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.limit)))
const from = computed(() => (props.total === 0 ? 0 : (props.page - 1) * props.limit + 1))
const to = computed(() => Math.min(props.total, props.page * props.limit))

// Nomor halaman yang ditampilkan (maks 7, dengan halaman aktif di tengah)
const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = props.page
  const span = 3
  let start = Math.max(1, cur - span)
  let end = Math.min(total, start + span * 2)
  start = Math.max(1, end - span * 2)
  const arr = []
  for (let i = start; i <= end; i++) arr.push(i)
  return arr
})
</script>

<template>
  <div class="pg">
    <div class="pg-info">
      Menampilkan {{ from }}–{{ to }} dari {{ total }} data
    </div>
    <div class="pg-btns">
      <button
        @click="$emit('change', page - 1)"
        :disabled="page <= 1"
        class="pg-btn"
        aria-label="Halaman sebelumnya"
      >‹</button>
      <button
        v-for="n in pageNumbers"
        :key="n"
        @click="$emit('change', n)"
        class="pg-btn pg-num"
        :class="{ active: n === page }"
      >{{ n }}</button>
      <button
        @click="$emit('change', page + 1)"
        :disabled="page >= totalPages"
        class="pg-btn"
        aria-label="Halaman berikutnya"
      >›</button>
    </div>
  </div>
</template>

<style scoped>
.pg {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 12px; padding: 12px 16px;
  border-top: 1px solid var(--rule);
  font-size: 13px; color: var(--muted);
}
.pg-btns { display: flex; align-items: center; gap: 4px; }
.pg-btn {
  min-width: 34px; height: 34px; padding: 0 10px;
  border-radius: var(--radius-control);
  border: 1px solid var(--control);
  background: var(--surface); color: var(--text);
  font-size: 13px; cursor: pointer;
}
.pg-btn:hover:not(:disabled) { border-color: var(--faint); }
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-btn.active { background: var(--primary); border-color: var(--primary); color: #fff; font-weight: 600; }
</style>
