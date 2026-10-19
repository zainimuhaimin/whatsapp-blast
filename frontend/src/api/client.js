import axios from 'axios'
import { useToast } from '../stores/useToast'

/**
 * API client untuk tool WA Blast.
 *
 * Kontrak (lihat design/architecture-draft.md section 3):
 * - Base path: /api (VITE_API_URL + '/api')
 * - Auth: JWT via httpOnly cookie → withCredentials: true
 * - 401 → redirect ke /login (kecuali saat sedang di halaman login)
 *
 * Penanganan error terpusat: setiap request gagal (kecuali 401 yang di-redirect
 * dan error yang di-skip via config.silent) menampilkan toast error dengan
 * pesan dari backend (response.data.detail / message) atau pesan generik.
 */

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`

export const http = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// Callback toast didaftarkan di sini untuk menghindari circular import
// (client.js dipakai stores, stores dipakai views — toast dipakai di mana-mana).
let toastError = null
export function setGlobalErrorHandler(fn) {
  toastError = fn
}

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const silent = error?.config?.silent === true

    if (status === 401) {
      // Session habis / belum login → paksa ke halaman login
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
      return Promise.reject(error)
    }

    if (!silent && toastError) {
      const data = error?.response?.data
      const msg =
        (data && (data.detail || data.message)) ||
        (error.code === 'ECONNABORTED'
          ? 'Waktu permintaan habis. Coba lagi.'
          : 'Terjadi kesalahan koneksi ke server.')
      toastError(Array.isArray(msg) ? msg.join('; ') : String(msg))
    }
    return Promise.reject(error)
  }
)

function params(obj = {}) {
  const q = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null && v !== '') q[k] = v
  }
  return { params: q }
}

/* ------------------------------ helpers ------------------------------ */

export function unwrapPage(res) {
  // Normalisasi response list: backend boleh mengembalikan array langsung
  // atau object {items, total, page, limit}
  const d = res.data
  if (Array.isArray(d)) return { items: d, total: d.length }
  return { items: d.items || d.data || [], total: d.total ?? d.count ?? 0 }
}

/* --------------------------------- auth -------------------------------- */

export const authApi = {
  login: (username, password) =>
    http.post('/auth/login', { username, password }).then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
  me: () => http.get('/auth/me', { silent: true }).then((r) => r.data),
}

/* -------------------------------- contacts ------------------------------ */

export const contactsApi = {
  list: (q = {}) => http.get('/contacts', params(q)).then(unwrapPage),
  get: (id) => http.get(`/contacts/${id}`).then((r) => r.data),
  create: (payload) => http.post('/contacts', payload).then((r) => r.data),
  update: (id, payload) => http.put(`/contacts/${id}`, payload).then((r) => r.data),
  remove: (id) => http.delete(`/contacts/${id}`).then((r) => r.data),
  toggleBlacklist: (id, is_blacklisted) =>
    http.patch(`/contacts/${id}/blacklist`, { is_blacklisted }).then((r) => r.data),
  findOrCreate: (payload) => http.post('/contacts/find-or-create', payload).then((r) => r.data),
}

/* -------------------------------- templates ----------------------------- */

export const templatesApi = {
  list: () => http.get('/templates').then(unwrapPage),
  get: (id) => http.get(`/templates/${id}`).then((r) => r.data),
  create: (payload) => http.post('/templates', payload).then((r) => r.data),
  update: (id, payload) => http.put(`/templates/${id}`, payload).then((r) => r.data),
  remove: (id) => http.delete(`/templates/${id}`).then((r) => r.data),
  versions: (id) => http.get(`/templates/${id}/versions`).then(unwrapPage),
  createVersion: (id, body) =>
    http.post(`/templates/${id}/versions`, { body }).then((r) => r.data),
  getVersion: (id, version) =>
    http.get(`/templates/${id}/versions/${version}`).then((r) => r.data),
}

/* -------------------------------- campaigns ----------------------------- */

export const campaignsApi = {
  list: (q = {}) => http.get('/campaigns', params(q)).then(unwrapPage),
  get: (id) => http.get(`/campaigns/${id}`).then((r) => r.data),
  create: (payload) => http.post('/campaigns', payload).then((r) => r.data),
  update: (id, payload) => http.put(`/campaigns/${id}`, payload).then((r) => r.data),
  remove: (id) => http.delete(`/campaigns/${id}`).then((r) => r.data),

  aiExtract: (id, input_text) =>
    http.post(`/campaigns/${id}/ai-extract`, { input_text }).then((r) => r.data),

  aiParseRecipients: (id, input_text) =>
    http.post(`/campaigns/${id}/ai-parse-recipients`, { input_text }).then((r) => r.data),
  aiApplyRecipients: (id, items) =>
    http.post(`/campaigns/${id}/ai-apply-recipients`, { items }).then((r) => r.data),
  applyFile: (id, payload) =>
    http.post(`/campaigns/${id}/apply-file`, payload).then((r) => r.data),

  recipientVariables: (id) =>
    http.get(`/campaigns/${id}/recipient-variables`).then((r) => r.data),
  saveRecipientVariables: (id, items) =>
    http.put(`/campaigns/${id}/recipient-variables`, { items }).then((r) => r.data),
  clearRecipientVariable: (id, variableName) =>
    http.delete(`/campaigns/${id}/recipient-variables/${encodeURIComponent(variableName)}`).then((r) => r.data),

  mappings: (id) => http.get(`/campaigns/${id}/mappings`).then((r) => r.data),
  saveMappings: (id, mappings) =>
    http.put(`/campaigns/${id}/mappings`, { mappings }).then((r) => r.data),

  buildRecipients: (id, contact_ids) =>
    http.post(`/campaigns/${id}/recipients`, { contact_ids }).then((r) => r.data),
  recipients: (id, q = {}) =>
    http.get(`/campaigns/${id}/recipients`, params(q)).then(unwrapPage),
  retryRecipient: (id, recipientId) =>
    http.post(`/campaigns/${id}/recipients/${recipientId}/retry`).then((r) => r.data),
  manualStatus: (id, recipientId, status) =>
    http.post(`/campaigns/${id}/recipients/${recipientId}/manual-status`, { status }).then((r) => r.data),
  updateMessageBody: (id, body) =>
    http.post(`/campaigns/${id}/message-body`, { body }).then((r) => r.data),

  review: (id) => http.get(`/campaigns/${id}/review`).then((r) => r.data),
  confirm: (id) => http.post(`/campaigns/${id}/confirm`).then((r) => r.data),

  pause: (id) => http.post(`/campaigns/${id}/pause`).then((r) => r.data),
  resume: (id) => http.post(`/campaigns/${id}/resume`).then((r) => r.data),
  cancel: (id) => http.post(`/campaigns/${id}/cancel`).then((r) => r.data),

  stats: (id) => http.get(`/campaigns/${id}/stats`).then((r) => r.data),
  messages: (id, q = {}) =>
    http.get(`/campaigns/${id}/messages`, params(q)).then(unwrapPage),
  chatLinks: (id, q = {}) =>
    http.get(`/campaigns/${id}/chat-links`, params(q)).then(unwrapPage),
}

/* ------------------------------ test numbers ---------------------------- */

export const testNumbersApi = {
  list: () => http.get('/test-numbers').then(unwrapPage),
  create: (payload) => http.post('/test-numbers', payload).then((r) => r.data),
  update: (id, payload) => http.put(`/test-numbers/${id}`, payload).then((r) => r.data),
  remove: (id) => http.delete(`/test-numbers/${id}`).then((r) => r.data),
}

/* -------------------------------- settings ------------------------------ */

export const settingsApi = {
  list: () => http.get('/settings').then((r) => r.data),
  update: (key, value) =>
    http.put(`/settings/${encodeURIComponent(key)}`, { value }).then((r) => r.data),
  testGemini: () => http.post('/settings/gemini/test').then((r) => r.data),
}

/* ------------------------------- audit logs ----------------------------- */

export const auditLogsApi = {
  list: (q = {}) => http.get('/audit-logs', params(q)).then(unwrapPage),
}

/* ------------------------------ file uploads ---------------------------- */

export const fileUploadsApi = {
  parse: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/file-uploads/parse', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  preview: (uploadId, payload) =>
    http.post(`/file-uploads/${uploadId}/preview`, payload).then((r) => r.data),
  createCampaign: (uploadId, payload) =>
    http.post(`/file-uploads/${uploadId}/create-campaign`, payload).then((r) => r.data),
}

export const metaApi = {
  // Versi backend — ditampilkan di footer sidebar agar mudah memastikan
  // backend yang berjalan sudah yang terbaru setelah git pull + rebuild.
  // Dibuat silent agar tidak memicu toast bila backend mati.
  version: () => http.get('/version', { silent: true }).then((r) => r.data).catch(() => null),
}

/* --------------------------- registrasi handler -------------------------- */

// Pasang handler toast error global sekali saat modul dipakai pertama kali.
setGlobalErrorHandler((msg) => useToast().error(msg))
