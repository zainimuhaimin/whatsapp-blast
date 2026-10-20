import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/useAuth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true, title: 'Masuk' },
  },
  {
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: 'Dashboard' },
      },
      {
        path: 'contacts',
        name: 'contacts',
        component: () => import('../views/ContactsView.vue'),
        meta: { title: 'Kontak' },
      },
      {
        path: 'templates',
        name: 'templates',
        component: () => import('../views/TemplatesView.vue'),
        meta: { title: 'Template' },
      },
      {
        path: 'campaigns/new',
        name: 'campaign-new',
        component: () => import('../views/CampaignWizardView.vue'),
        meta: { title: 'Campaign Baru', parent: 'Campaign' },
      },
      {
        path: 'campaigns/:id',
        name: 'campaign-detail',
        component: () => import('../views/CampaignDetailView.vue'),
        meta: { title: 'Detail Campaign', parent: 'Campaign' },
      },
      {
        path: 'test-numbers',
        name: 'test-numbers',
        component: () => import('../views/TestNumbersView.vue'),
        meta: { title: 'Nomor Test' },
      },
      {
        path: 'sender',
        name: 'sender',
        component: () => import('../views/SenderView.vue'),
        meta: { title: 'Koneksi WA' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: 'Pengaturan' },
      },
      {
        path: 'audit-logs',
        name: 'audit-logs',
        component: () => import('../views/AuditLogsView.vue'),
        meta: { title: 'Audit Log' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Route guard: semua halaman kecuali /login butuh sesi aktif.
// Verifikasi lewat GET /api/auth/me (httpOnly cookie) agar tidak mengandalkan
// state lokal yang bisa basi.
router.beforeEach(async (to) => {
  document.title = to.meta.title
    ? `${to.meta.title} — WA Blast`
    : 'WA Blast — Tool Broadcast WhatsApp'

  const { fetchMe, fetchConfig } = useAuth()
  const disabled = await fetchConfig()
  if (disabled) {
    // Login dinonaktifkan: langsung ke dashboard; /login dialihkan ke beranda.
    if (to.name === 'login') return { name: 'dashboard' }
    await fetchMe() // tetap isi profil user untuk tampilan (avatar/nama)
    return true
  }

  if (to.meta.public) return true
  const user = await fetchMe()
  if (!user) return { name: 'login' }
  return true
})

export default router
