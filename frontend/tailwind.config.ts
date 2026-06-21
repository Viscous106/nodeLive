import type { Config } from 'tailwindcss'

// Design tokens — see docs/design-tokens.md. Scaler-inspired palette,
// Inter, 8px card radius. Loaded by globals.css via `@config`.
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'selector',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: { DEFAULT: '#2563EB', light: '#3B82F6', dark: '#1D4ED8' },
        danger: { DEFAULT: '#DC2626' },
        gold: { DEFAULT: '#F59E0B', border: '#D97706' },

        page: 'var(--color-page)',
        card: 'var(--color-card)',
        'dark-banner': '#1E3A8A',

        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        'text-link': 'var(--color-text-link)',

        border: {
          DEFAULT: 'var(--color-border)',
          muted: 'var(--color-border-muted)',
          focus: '#3B82F6',
        },

        success: { DEFAULT: '#16A34A', light: '#22C55E' },
        warning: { DEFAULT: '#D97706', light: '#F59E0B' },

        'topic-blue': '#3B82F6',
        'topic-green': '#22C55E',
        'topic-pink': '#F43F5E',
        'topic-teal': '#14B8A6',

        'badge-mandatory-bg': '#FEF9C3',
        'badge-mandatory-text': '#854D0E',
        'badge-new-bg': '#DCFCE7',
        'badge-new-text': '#166534',
        'badge-unsolved-bg': '#F3F4F6',
        'badge-unsolved-text': '#374151',
      },
      borderRadius: {
        card: '8px',
        btn: '6px',
        pill: '24px',
        badge: '4px',
        hero: '12px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
        elevated:
          '0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -1px rgba(0,0,0,0.06)',
        drawer: '0 20px 60px rgba(0,0,0,0.15)',
      },
      spacing: {
        'page-x': '32px',
        'page-y': '24px',
      },
    },
  },
}

export default config
