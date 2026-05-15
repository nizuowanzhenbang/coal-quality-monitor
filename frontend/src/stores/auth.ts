import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  username: string | null
  role: string | null
  isLoggedIn: boolean
  login: (token: string, username: string, role: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      role: null,
      isLoggedIn: false,
      login: (token, username, role) =>
        set({ token, username, role, isLoggedIn: true }),
      logout: () =>
        set({ token: null, username: null, role: null, isLoggedIn: false }),
    }),
    {
      name: 'coal-quality-auth',
    },
  ),
)
