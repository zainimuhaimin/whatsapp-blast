import { ref } from 'vue'

/**
 * Toast store sederhana (ref-based, tanpa Pinia).
 * Dipakai oleh api/client.js untuk penanganan error terpusat dan
 * oleh view mana pun yang ingin menampilkan notifikasi.
 */

const toasts = ref([])
let seq = 0

function push(type, message, title) {
  const id = ++seq
  toasts.value.push({ id, type, message, title })
  // Toast otomatis hilang setelah 5 detik
  setTimeout(() => remove(id), 5000)
}

function remove(id) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

export function useToast() {
  return {
    toasts,
    success: (message, title = 'Berhasil') => push('success', message, title),
    error: (message, title = 'Gagal') => push('error', message, title),
    warning: (message, title = 'Perhatian') => push('warning', message, title),
    info: (message, title = 'Info') => push('info', message, title),
    remove,
  }
}
