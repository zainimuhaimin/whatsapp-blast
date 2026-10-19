<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../api/client'
import { useAuth } from '../stores/useAuth'
import { useToast } from '../stores/useToast'

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
  <div class="min-h-screen flex items-center justify-center bg-emerald-950 px-4">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-2xl p-8">
      <div class="text-center mb-8">
        <div class="text-5xl mb-3">💬</div>
        <h1 class="text-2xl font-bold">WA Blast</h1>
        <p class="text-sm text-slate-500 mt-1">Masuk untuk mengelola broadcast WhatsApp</p>
      </div>

      <form @submit.prevent="submit" class="space-y-4">
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

        <div v-if="error" class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold disabled:opacity-50 transition-colors"
        >
          {{ loading ? 'Memproses…' : 'Masuk' }}
        </button>
      </form>
    </div>
  </div>
</template>
