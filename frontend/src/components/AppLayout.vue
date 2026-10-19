<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { authApi } from '../api/client'
import { useAuth } from '../stores/useAuth'
import { useToast } from '../stores/useToast'

const router = useRouter()
const { user, clear } = useAuth()
const toast = useToast()
const sidebarOpen = ref(false)

const nav = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/campaigns/new', label: 'Campaign Baru', icon: '🚀' },
  { to: '/contacts', label: 'Kontak', icon: '👥' },
  { to: '/templates', label: 'Template', icon: '📝' },
  { to: '/test-numbers', label: 'Nomor Test', icon: '🧪' },
  { to: '/settings', label: 'Pengaturan', icon: '⚙️' },
  { to: '/audit-logs', label: 'Audit Log', icon: '🧾' },
]

async function logout() {
  try {
    await authApi.logout()
    toast.success('Anda telah keluar.')
  } finally {
    clear()
    router.push('/login')
  }
}
</script>

<template>
  <div class="min-h-screen flex">
    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-40 w-60 bg-emerald-950 text-emerald-50 flex flex-col
             transform transition-transform lg:translate-x-0 lg:static"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="px-5 py-5 border-b border-emerald-900">
        <div class="text-xl font-bold">💬 WA Blast</div>
        <div class="text-xs text-emerald-300 mt-0.5">Tool broadcast WhatsApp</div>
      </div>

      <nav class="flex-1 overflow-y-auto p-3 space-y-1">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                 hover:bg-emerald-900/60 transition-colors"
          active-class="bg-emerald-800 text-white"
          @click="sidebarOpen = false"
        >
          <span class="text-lg">{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="p-4 border-t border-emerald-900">
        <div class="text-sm font-medium truncate">{{ user?.username || 'Pengguna' }}</div>
        <button
          @click="logout"
          class="mt-2 w-full text-sm px-3 py-2 rounded-lg bg-emerald-900 hover:bg-emerald-800 transition-colors"
        >
          Keluar
        </button>
      </div>
    </aside>

    <!-- Overlay mobile -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-30 bg-black/40 lg:hidden"
      @click="sidebarOpen = false"
    ></div>

    <!-- Konten -->
    <div class="flex-1 min-w-0 flex flex-col">
      <header class="lg:hidden bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-20">
        <button @click="sidebarOpen = true" class="text-2xl" aria-label="Buka menu">☰</button>
        <span class="font-semibold">WA Blast</span>
      </header>
      <main class="flex-1 p-4 lg:p-8 max-w-7xl w-full mx-auto">
        <RouterView />
      </main>
    </div>
  </div>
</template>
