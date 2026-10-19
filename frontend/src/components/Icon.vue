<script setup>
/**
 * Icon: set ikon outline 16px, stroke 1.5, mengikuti warna teks (currentColor).
 * Menggantikan emoji di navigasi & label (aturan anti-slop).
 */
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
})

const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  send: '<path d="M21 3 10.5 13.5"/><path d="M21 3 14 21l-3.5-7.5L3 10z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.6c2.8.3 4.9 2.1 5.5 5.4"/>',
  chat: '<path d="M21 12a8 8 0 0 1-8 8H4l2.3-2.9A8 8 0 1 1 21 12z"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01"/>',
  flask: '<path d="M9 3h6"/><path d="M10 3v5.5L4.8 17a2 2 0 0 0 1.8 3h10.8a2 2 0 0 0 1.8-3L14 8.5V3"/><path d="M7.5 14h9"/>',
  gear: '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.64 8.9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.09A1.7 1.7 0 0 0 11 3.09V3a2 2 0 1 1 4 0v.09c0 .68.4 1.3 1.01 1.56a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.09c.26.61.88 1.01 1.56 1.01H21a2 2 0 1 1 0 4h-.09c-.68 0-1.3.4-1.51 1z"/>',
  scroll: '<path d="M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6"/><path d="M6 3a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  check: '<path d="m4.5 12.5 5 5 10-11"/>',
  'check-double': '<path d="m2.5 12.5 4.5 4.5L14.5 9"/><path d="M11 16.5 13.5 19 21 10.5"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'chevron-right': '<path d="m9 6 6 6-6 6"/>',
  'chevron-left': '<path d="m15 6-6 6 6 6"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  logout: '<path d="M14 4H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h8"/><path d="m10 12 9 0"/><path d="m16 8 4 4-4 4"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/>',
  alert: '<path d="M12 3 2.5 20h19z"/><path d="M12 10v4.5"/><path d="M12 17.5h.01"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5"/><path d="M12 7.5h.01"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>',
  pencil: '<path d="M14.5 5.5 18.5 9.5 8 20l-5 1 1-5z"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  external: '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M20 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5"/>',
  wifi: '<path d="M2.5 9a15 15 0 0 1 19 0"/><path d="M5.5 12.5a10 10 0 0 1 13 0"/><path d="M8.6 16a5 5 0 0 1 6.8 0"/><path d="M12 19.5h.01"/>',
  'wifi-off': '<path d="m3 3 18 18"/><path d="M2.5 9a15 15 0 0 1 6.2-3.1M12.8 5.9A15 15 0 0 1 21.5 9"/><path d="M5.5 12.5a10 10 0 0 1 3.8-2.3M12 10.8a10 10 0 0 1 7.5 1.7"/><path d="M8.6 16a5 5 0 0 1 6.8 0"/><path d="M12 19.5h.01"/>',
  qr: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14h1M14 20h1M18 18h3v3h-3z"/>',
  inbox: '<path d="M3 13l2.5-8h13L21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 13h5.5l1 2h5l1-2H21"/>',
  ban: '<circle cx="12" cy="12" r="8.5"/><path d="M5.5 5.5l13 13"/>',
  play: '<path d="M7 4.5v15l12-7.5z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  zap: '<path d="M13 2 4.5 13.5H11L9.5 22 19 10h-6.5z"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  upload: '<path d="M12 16V4"/><path d="m6 10 6-6 6 6"/><path d="M4 20h16"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
}

const svg = computed(() => paths[props.name] || paths.info)
</script>

<template>
  <svg
    :width="size" :height="size" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true" v-html="svg"
  />
</template>
