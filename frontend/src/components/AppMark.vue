<script setup>
/**
 * AppMark: mark produk WA Blast — bubble chat + paper plane (kirim),
 * digambar khusus untuk produk ini. Bukan kotak hitam berisi huruf.
 */
defineProps({
  size: { type: [Number, String], default: 32 },
})
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="var(--accent-soft)" />
    <path
      d="M16 6.5c-5.2 0-9.5 3.9-9.5 8.8 0 1.7.5 3.2 1.4 4.6L6.5 24.5l4.9-1.3c1.4.8 3 1.2 4.6 1.2 5.2 0 9.5-3.9 9.5-8.8S21.2 6.5 16 6.5z"
      fill="var(--accent)"
    />
    <path
      d="M20.8 12.2 14.4 18.6l-2.6-.4 1-2.6 4.5-4.5-4.9 3.9-2.4-.7 8-3.4c.5-.2 1 .2.8.7l-1.6 5.2"
      fill="#fff"
      opacity="0.95"
    />
  </svg>
</template>
