import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ThemeState {
  dark: boolean
  toggle: () => void
}

function applyTheme(dark: boolean) {
  document.documentElement.classList.toggle('dark', dark)
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      dark: false,
      toggle: () =>
        set((s) => {
          const next = !s.dark
          applyTheme(next)
          return { dark: next }
        }),
    }),
    { name: 'linkhq-theme' },
  ),
)

// Apply stored theme before first React paint to avoid flash.
if (typeof window !== 'undefined') {
  try {
    const raw = localStorage.getItem('linkhq-theme')
    const isDark = raw
      ? (JSON.parse(raw) as { state?: { dark?: boolean } }).state?.dark === true
      : false
    applyTheme(isDark)
  } catch {
    // ignore parse errors
  }
}
