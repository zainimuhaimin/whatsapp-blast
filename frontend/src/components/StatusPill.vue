<script setup>
/**
 * StatusPill: label status berwarna untuk campaign, penerima, template, dsb.
 */
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' },
})

const map = {
  // campaign
  draft: ['Draft', 'bg-slate-200 text-slate-700'],
  review: ['Review', 'bg-sky-100 text-sky-800'],
  scheduled: ['Terjadwal', 'bg-indigo-100 text-indigo-800'],
  queued: ['Antre', 'bg-amber-100 text-amber-800'],
  sending: ['Mengirim', 'bg-blue-100 text-blue-800'],
  paused: ['Jeda', 'bg-orange-100 text-orange-800'],
  completed: ['Selesai', 'bg-emerald-100 text-emerald-800'],
  failed: ['Gagal', 'bg-red-100 text-red-700'],
  cancelled: ['Dibatalkan', 'bg-slate-200 text-slate-600'],
  // penerima
  pending: ['Menunggu', 'bg-slate-200 text-slate-700'],
  sent: ['Terkirim', 'bg-blue-100 text-blue-800'],
  delivered: ['Diterima', 'bg-emerald-100 text-emerald-800'],
  read: ['Dibaca', 'bg-teal-100 text-teal-800'],
  // template approval
  approved: ['Disetujui', 'bg-emerald-100 text-emerald-800'],
  submitted: ['Diajukan', 'bg-amber-100 text-amber-800'],
  rejected: ['Ditolak', 'bg-red-100 text-red-700'],
  // provider
  official: ['Resmi', 'bg-emerald-100 text-emerald-800'],
  unofficial: ['Non-resmi', 'bg-red-100 text-red-700'],
  // umum
  active: ['Aktif', 'bg-emerald-100 text-emerald-800'],
  inactive: ['Nonaktif', 'bg-slate-200 text-slate-600'],
  blacklisted: ['Blacklist', 'bg-red-100 text-red-700'],
}

const pill = computed(() => {
  const key = String(props.status || '').toLowerCase()
  const [label, cls] = map[key] || [props.status || '–', 'bg-slate-100 text-slate-600']
  return { label, cls }
})
</script>

<template>
  <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap" :class="pill.cls">
    {{ pill.label }}
  </span>
</template>
