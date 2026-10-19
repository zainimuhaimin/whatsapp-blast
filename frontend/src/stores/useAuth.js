import { ref } from 'vue'

/**
 * Auth store sederhana: menyimpan profil user yang sedang login.
 * Login pertama kali selalu diverifikasi lewat GET /api/auth/me
 * agar httpOnly cookie benar-benar valid (bukan sekadar tebakan lokal).
 */
import { authApi } from '../api/client'

const user = ref(null)
const checked = ref(false)

export function useAuth() {
  async function fetchMe() {
    if (checked.value) return user.value
    try {
      user.value = await authApi.me()
    } catch {
      user.value = null
    }
    checked.value = true
    return user.value
  }

  function setUser(u) {
    user.value = u
    checked.value = true
  }

  function clear() {
    user.value = null
    checked.value = true
  }

  function reset() {
    checked.value = false
  }

  return { user, checked, fetchMe, setUser, clear, reset }
}
