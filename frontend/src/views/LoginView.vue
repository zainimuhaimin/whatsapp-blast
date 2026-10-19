<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../api/client'
import { useAuth } from '../stores/useAuth'
import { useToast } from '../stores/useToast'
import AppMark from '../components/AppMark.vue'

const router = useRouter()
const { setUser } = useAuth()
const toast = useToast()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = 'Username dan password wajib diisi.'
    return
  }
  loading.value = true
  try {
    await authApi.login(username.value.trim(), password.value)
    const me = await authApi.me()
    setUser(me)
    toast.success(`Selamat datang, ${me?.username || username.value}!`)
    router.push('/')
  } catch (e) {
    const data = e?.response?.data
    error.value =
      (data && (data.detail || data.message)) ||
      'Login gagal. Periksa username dan password Anda.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <AppMark :size="44" />
        <h1 class="page-title mt-4">WA Blast</h1>
        <p class="page-sub">Masuk untuk mengelola broadcast WhatsApp</p>
      </div>

      <form @submit.prevent="submit" class="login-form">
        <div>
          <label class="field-label" for="username">Username</label>
          <input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            class="field-input"
            placeholder="Nama pengguna"
            :disabled="loading"
          />
        </div>
        <div>
          <label class="field-label" for="password">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="field-input"
            placeholder="••••••••"
            :disabled="loading"
          />
        </div>

        <div v-if="error" class="login-error" role="alert">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="btn btn-primary btn-block"
        >
          {{ loading ? 'Memproses…' : 'Masuk' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: var(--ground);
}
.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 32px;
}
.login-brand { text-align: center; margin-bottom: 28px; display: grid; justify-items: center; }
.login-form { display: grid; gap: 16px; }
.login-error {
  font-size: 13px;
  color: var(--pill-negative-ink);
  background: var(--pill-negative-bg);
  border-radius: var(--radius-control);
  padding: 10px 12px;
}
.btn-block { width: 100%; min-height: 40px; }
</style>
