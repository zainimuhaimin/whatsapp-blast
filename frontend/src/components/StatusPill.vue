<script setup>
/**
 * StatusPill: label status — pale tint + dark text se-hue (aturan app-screen).
 */
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' },
})

const map = {
  // campaign
  draft: ['Draft', 'pill-neutral'],
  review: ['Review', 'pill-info'],
  scheduled: ['Terjadwal', 'pill-warning'],
  queued: ['Antre', 'pill-warning'],
  sending: ['Mengirim', 'pill-info'],
  paused: ['Jeda', 'pill-warning'],
  completed: ['Selesai', 'pill-positive'],
  failed: ['Gagal', 'pill-negative'],
  cancelled: ['Dibatalkan', 'pill-neutral'],
  // penerima
  pending: ['Menunggu', 'pill-neutral'],
  sent: ['Terkirim', 'pill-info'],
  delivered: ['Diterima', 'pill-positive'],
  read: ['Dibaca', 'pill-accent'],
  skipped: ['Dilewati', 'pill-neutral'],
  // template approval
  approved: ['Disetujui', 'pill-positive'],
  submitted: ['Diajukan', 'pill-warning'],
  rejected: ['Ditolak', 'pill-negative'],
  // provider
  official: ['Resmi', 'pill-accent'],
  unofficial: ['Non-resmi', 'pill-warning'],
  // umum
  active: ['Aktif', 'pill-positive'],
  inactive: ['Nonaktif', 'pill-neutral'],
  blacklisted: ['Blacklist', 'pill-negative'],
}

const pill = computed(() => {
  const key = String(props.status || '').toLowerCase()
  const [label, cls] = map[key] || [props.status || '–', 'pill-neutral']
  return { label, cls }
})
</script>

<template>
  <span class="pill" :class="pill.cls">{{ pill.label }}</span>
</template>
