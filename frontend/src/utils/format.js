/**
 * Helper format & validasi dipakai di banyak view.
 */

export function formatRupiah(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '–'
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number(value))
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '–'
  return new Intl.NumberFormat('id-ID').format(Number(value))
}

/**
 * Tampilkan nomor E.164 dengan awalan '+' agar familiar dibaca
 * (disimpan di DB tanpa '+', mis. 62812… -> ditampilkan +62812…).
 */
export function formatPhone(value) {
  if (!value) return '–'
  const s = String(value).trim()
  return s.startsWith('+') ? s : `+${s}`
}

export function formatDateTime(value) {
  if (!value) return '–'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '–'
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

export function formatDate(value) {
  if (!value) return '–'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '–'
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(d)
}

export function formatDuration(seconds) {
  const s = Math.max(0, Math.round(Number(seconds) || 0))
  if (s < 60) return `± ${s} detik`
  const m = Math.floor(s / 60)
  if (m < 60) return `± ${m} menit`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `± ${h} jam ${rest} menit` : `± ${h} jam`
}

/**
 * Normalisasi + validasi nomor telepon ke format E.164-ish.
 * Kontrak backend: phone unik, format E.164 (mis. 6281234567890).
 * Return: { ok, phone, error }
 */
export function normalizePhone(raw) {
  const digits = String(raw || '').replace(/\D/g, '')
  if (!digits) return { ok: false, phone: '', error: 'Nomor telepon wajib diisi.' }
  // Hapus leading 0 → ganti kode negara Indonesia bila tampak lokal
  let phone = digits
  if (phone.startsWith('0')) phone = '62' + phone.slice(1)
  if (!/^\+?[1-9]\d{7,14}$/.test(phone)) {
    return {
      ok: false,
      phone,
      error: 'Format nomor tidak valid. Gunakan format internasional, mis. 6281234567890.',
    }
  }
  return { ok: true, phone, error: '' }
}

/** Bungkus nama variabel menjadi {{nama}} untuk tampilan.
 * Dipakai di template Vue agar tidak ada literal '{{' di dalam interpolasi. */
export function wrapVar(name) {
  return '{{' + name + '}}'
}

/** Ekstrak nama variabel {{...}} dari body template (mirror regex backend). */
export function extractVariables(body) {
  const vars = []
  const re = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g
  let m
  while ((m = re.exec(String(body || ''))) !== null) {
    if (!vars.includes(m[1])) vars.push(m[1])
  }
  return vars
}

/** Render preview body template dengan nilai mapping (untuk sample pesan). */
export function renderTemplate(body, values = {}) {
  return String(body || '').replace(
    /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g,
    (_, name) => (values[name] !== undefined && values[name] !== null ? values[name] : `{{${name}}}`)
  )
}

/** Potong teks panjang untuk tampilan tabel. */
export function truncate(text, max = 80) {
  const s = String(text ?? '')
  return s.length > max ? s.slice(0, max) + '…' : s
}

/**
 * Hitung estimasi durasi & biaya review di sisi frontend (fallback bila
 * backend belum mengembalikan field ini di payload review).
 * Rumus sesuai design section 4 & 6:
 *   eta_detik = penerima × rata-rata delay 10 dtk (rentang 5–15)
 *   biaya     = penerima × tarif kategori template
 */
export function estimateDuration(totalRecipients, avgDelaySec = 10, rateLimitPerHour = null) {
  const n = Number(totalRecipients) || 0
  const etaSeconds = n * avgDelaySec
  if (rateLimitPerHour && rateLimitPerHour > 0) {
    const rateSeconds = (n / rateLimitPerHour) * 3600
    return Math.max(etaSeconds, rateSeconds)
  }
  return etaSeconds
}

export const DEFAULT_PRICE_PER_MESSAGE_IDR = {
  marketing: 627.33,
  utility: 366.65,
  authentication: 366.65,
  service: 356.65,
}

export function estimateCost(totalRecipients, category, priceMap = DEFAULT_PRICE_PER_MESSAGE_IDR) {
  const n = Number(totalRecipients) || 0
  const price = Number(priceMap?.[category] ?? 0)
  return n * price
}
