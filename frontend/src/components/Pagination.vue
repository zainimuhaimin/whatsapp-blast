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
  <div class="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-white border-t border-slate-200 text-sm">
    <div class="text-slate-500">
      Menampilkan {{ from }}–{{ to }} dari {{ total }} data
    </div>
    <div class="flex items-center gap-1">
      <button
        @click="$emit('change', page - 1)"
        :disabled="page <= 1"
        class="px-2.5 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
        aria-label="Halaman sebelumnya"
      >‹</button>
      <button
        v-for="n in pageNumbers"
        :key="n"
        @click="$emit('change', n)"
        class="px-2.5 py-1.5 rounded-lg border text-sm min-w-9"
        :class="n === page
          ? 'bg-emerald-600 text-white border-emerald-600 font-semibold'
          : 'border-slate-300 hover:bg-slate-50'"
      >{{ n }}</button>
      <button
        @click="$emit('change', page + 1)"
        :disabled="page >= totalPages"
        class="px-2.5 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
        aria-label="Halaman berikutnya"
      >›</button>
    </div>
  </div>
</template>
