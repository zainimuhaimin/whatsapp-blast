<script setup>
/**
 * AppLayout: shell Ruled T-frame — sidebar 232px + top bar 64px (desktop),
 * top bar 52px + menu sheet layar penuh (mobile).
 */
import { ref, computed, onMounted, watch } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { authApi, metaApi, settingsApi } from '../api/client'
import { useAuth } from '../stores/useAuth'
import { useToast } from '../stores/useToast'
import Icon from './Icon.vue'
import AppMark from './AppMark.vue'

const router = useRouter()
const route = useRoute()
const { user, clear } = useAuth()
const toast = useToast()
const menuOpen = ref(false)
const provider = ref('')
const backendVersion = ref('')

onMounted(async () => {
  // Tampilkan versi backend di footer — memudahkan memastikan backend
  // sudah di-rebuild setelah git pull (frontend update duluan via npm run dev).
  const v = await metaApi.version()
  if (v?.backend_version) backendVersion.value = v.backend_version
})

// Kunci scroll body saat menu sheet terbuka (mobile)
watch(menuOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})

// Tutup sheet bila rute berubah (mis. tombol back browser)
watch(() => route.fullPath, () => { menuOpen.value = false })

const nav = [
  { to: '/', label: 'Dashboard', icon: 'grid', end: true },
  { to: '/campaigns/new', label: 'Campaign Baru', icon: 'send' },
  { to: '/contacts', label: 'Kontak', icon: 'users' },
  { to: '/templates', label: 'Template', icon: 'chat' },
  { to: '/test-numbers', label: 'Nomor Test', icon: 'flask' },
  { to: '/sender', label: 'Koneksi WA', icon: 'wifi' },
  { to: '/settings', label: 'Pengaturan', icon: 'gear' },
  { to: '/audit-logs', label: 'Audit Log', icon: 'scroll' },
]

const crumb = computed(() => {
  const m = route.meta || {}
  const parent = m.parent
  const title = m.title || ''
  return parent ? { parent, title } : { parent: '', title }
})

function isActive(item) {
  if (item.end) return route.path === '/'
  return route.path.startsWith(item.to)
}

async function logout() {
  try {
    await authApi.logout()
    toast.success('Anda telah keluar.')
  } finally {
    clear()
    router.push('/login')
  }
}

onMounted(async () => {
  try {
    const list = await settingsApi.list()
    const row = (Array.isArray(list) ? list : []).find((s) => s.key === 'wa.provider')
    provider.value = row ? String(row.value?.value ?? row.value ?? '') : ''
  } catch {
    /* top bar tetap tampil tanpa pill provider */
  }
})
</script>

<template>
  <div class="shell">
    <!-- ============ Sidebar (desktop) ============ -->
    <aside class="sidebar">
      <RouterLink to="/" class="brand">
        <AppMark :size="30" />
        <span class="brand-text">
          <span class="brand-name">WA Blast</span>
          <span class="brand-sub">Broadcast WhatsApp</span>
        </span>
      </RouterLink>

      <nav class="nav">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <Icon :name="item.icon" class="nav-icon" />
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div class="user-chip">
          <span class="user-avatar">{{ (user?.username || 'P').slice(0, 1).toUpperCase() }}</span>
          <span class="user-name">{{ user?.username || 'Pengguna' }}</span>
          <button @click="logout" class="logout-btn" title="Keluar">
            <Icon name="logout" :size="14" />
            <span>Keluar</span>
          </button>
        </div>
        <div v-if="backendVersion" class="backend-ver" :title="'Versi backend yang sedang berjalan'">
          backend {{ backendVersion }}
        </div>
      </div>
    </aside>

    <!-- ============ Kolom kanan: top bar + konten ============ -->
    <div class="main-col">
      <header class="topbar">
        <button class="menu-btn" @click="menuOpen = true" aria-label="Buka menu">
          <Icon name="menu" :size="20" />
        </button>
        <div class="crumb">
          <span v-if="crumb.parent" class="crumb-parent">{{ crumb.parent }} <span class="crumb-sep">/</span> </span>
          <span class="crumb-current">{{ crumb.title }}</span>
        </div>
        <div class="topbar-right">
          <span v-if="provider" class="pill" :class="provider === 'official' ? 'pill-accent' : 'pill-warning'">
            {{ provider === 'official' ? 'Resmi' : 'Non-resmi' }}
          </span>
          <span class="topbar-user">{{ user?.username || '' }}</span>
          <button @click="logout" class="icon-btn" aria-label="Keluar" title="Keluar">
            <Icon name="logout" :size="16" />
          </button>
        </div>
      </header>

      <main class="canvas">
        <RouterView />
      </main>
    </div>

    <!-- ============ Menu sheet (mobile) ============ -->
    <Teleport to="body">
      <div v-if="menuOpen" class="menu-sheet">
        <div class="menu-head">
          <RouterLink to="/" class="brand" @click="menuOpen = false">
            <AppMark :size="30" />
            <span class="brand-text">
              <span class="brand-name">WA Blast</span>
              <span class="brand-sub">Broadcast WhatsApp</span>
            </span>
          </RouterLink>
          <button class="icon-btn" @click="menuOpen = false" aria-label="Tutup menu">
            <Icon name="x" :size="20" />
          </button>
        </div>
        <nav class="menu-nav">
          <RouterLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="nav-item menu-link"
            :class="{ active: isActive(item) }"
            @click="menuOpen = false"
          >
            <Icon :name="item.icon" class="nav-icon" />
            {{ item.label }}
          </RouterLink>
        </nav>
        <div class="menu-foot">
          <div class="user-row">
            <span class="user-avatar">{{ (user?.username || 'P').slice(0, 1).toUpperCase() }}</span>
            <span class="user-name">{{ user?.username || 'Pengguna' }}</span>
          </div>
          <button @click="logout" class="btn-secondary w-full">
            <Icon name="logout" :size="15" /> Keluar
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  background: var(--ground);
}

/* ---- Sidebar ---- */
.sidebar {
  width: var(--sidebar-width);
  flex: none;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--rule);
  position: sticky;
  top: 0;
  height: 100vh;
  height: 100dvh;
  background: var(--ground);
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px 14px;
  text-decoration: none;
  color: var(--text);
}
.brand-text { display: flex; flex-direction: column; line-height: 1.25; }
.brand-name { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
.brand-sub { font-size: 12px; color: var(--faint); }
.nav { flex: 1; overflow-y: auto; padding: 6px 0 12px; }
.nav .nav-item { min-height: 34px; margin-bottom: 2px; }
.sidebar-foot {
  border-top: 1px solid var(--rule);
  padding: 12px 12px 16px;
}
.user-row { display: flex; align-items: center; gap: 10px; padding: 4px 8px 10px; }
.user-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 8px;
  border-radius: var(--radius-control);
}
.user-chip:hover { background: var(--raised); }
.user-chip .user-name { flex: 1; min-width: 0; }
.logout-btn {
  display: inline-flex; align-items: center; gap: 6px; flex: none;
  background: transparent; border: 0; cursor: pointer;
  color: var(--muted); font-size: 13px; font-weight: 500;
  padding: 6px 8px; border-radius: var(--radius-control);
  white-space: nowrap;
}
.logout-btn:hover { color: var(--negative); background: var(--pill-negative-bg); }
.logout-btn svg { flex: none; display: block; }
.backend-ver {
  margin-top: 8px; padding: 0 8px;
  font-size: 11px; color: var(--faint);
}
.user-avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--accent-soft); color: var(--accent-ink);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600; flex: none;
}
.user-name { font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }


/* ---- Kolom kanan ---- */
.main-col { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.topbar {
  height: var(--topbar-height);
  flex: none;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 29px;
  border-bottom: 1px solid var(--rule);
  background: var(--ground);
  position: sticky;
  top: 0;
  z-index: 20;
}
.menu-btn { display: none; }
.crumb { font-size: 14px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.crumb-parent { color: var(--faint); }
.crumb-sep { margin: 0 6px; color: var(--control); }
.crumb-current { font-weight: 600; color: var(--text); }
.topbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  padding-left: 16px;
  border-left: 1px solid var(--rule);
  height: 100%;
}
.topbar-user { font-size: 13px; color: var(--muted); }
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: var(--radius-control);
  color: var(--muted); border: 1px solid transparent; background: transparent; cursor: pointer;
}
.icon-btn:hover { background: var(--raised); color: var(--text); }

.canvas {
  flex: 1;
  padding: 36px 29px 48px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
}

/* ---- Menu sheet (mobile) ---- */
.menu-sheet {
  position: fixed; inset: 0; z-index: 60;
  background: var(--ground);
  display: flex; flex-direction: column;
}
.menu-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--rule);
}
.menu-head .brand { padding: 0; }
.menu-nav { flex: 1; overflow-y: auto; padding: 12px 8px; }
.menu-nav .menu-link { min-height: 48px; font-size: 15px; }
.menu-foot { border-top: 1px solid var(--rule); padding: 16px; display: grid; gap: 8px; }

/* ---- Responsif ---- */
@media (min-width: 1024px) {
  /* Sheet mobile tidak boleh menutupi tampilan desktop (mis. setelah resize) */
  .menu-sheet { display: none; }
}
@media (max-width: 1023px) {
  .sidebar { display: none; }
  .topbar { height: 52px; padding: 0 16px; }
  .menu-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 44px; height: 44px; margin-left: -10px;
    color: var(--text); background: transparent; border: 0; cursor: pointer;
  }
  .topbar-right { border-left: 0; padding-left: 0; }
  .topbar-user { display: none; }
  .canvas { padding: 24px 16px 64px; }
}
</style>
