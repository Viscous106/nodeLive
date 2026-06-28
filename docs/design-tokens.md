# Design Tokens — nodeLive LMS

Extracted from Scaler Academy LMS screenshots + user-supplied colors.zip.
**Font:** Source Sans Pro (both headings and body — confirmed from Scaler typography screenshot)
**Icon library:** Lucide React (closest match to Scaler's SVG icon style)
**Component system:** shadcn/ui + Tailwind CSS 4.x + Radix UI primitives

---

## Tailwind CSS Configuration

```ts
// tailwind.config.ts
import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Source Sans Pro"', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Brand
        primary:  { DEFAULT: '#2563EB', light: '#3B82F6', dark: '#1D4ED8' },
        danger:   { DEFAULT: '#DC2626' },
        gold:     { DEFAULT: '#F59E0B', border: '#D97706' },

        // Backgrounds
        page:     '#EFF6FF',   // main page bg (light blue-gray)
        card:     '#FFFFFF',
        'dark-banner': '#1E3A8A',

        // Text
        'text-primary':   '#111827',
        'text-secondary': '#374151',
        'text-muted':     '#6B7280',
        'text-link':      '#2563EB',

        // Borders
        border:   { DEFAULT: '#E2E8F0', muted: '#F1F5F9', focus: '#3B82F6' },

        // Semantic
        success:  { DEFAULT: '#16A34A', light: '#22C55E' },
        warning:  { DEFAULT: '#D97706', light: '#F59E0B' },

        // Video card thumbnail colors (topic-coded)
        'topic-blue':  '#3B82F6',
        'topic-green': '#22C55E',
        'topic-pink':  '#F43F5E',
        'topic-teal':  '#14B8A6',

        // Badge tokens
        'badge-mandatory-bg':   '#FEF9C3',
        'badge-mandatory-text': '#854D0E',
        'badge-new-bg':         '#DCFCE7',
        'badge-new-text':       '#166534',
        'badge-unsolved-bg':    '#F3F4F6',
        'badge-unsolved-text':  '#374151',
      },
      borderRadius: {
        card:   '8px',
        btn:    '6px',
        pill:   '24px',
        badge:  '4px',
        hero:   '12px',
      },
      boxShadow: {
        card:     '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
        elevated: '0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -1px rgba(0,0,0,0.06)',
        drawer:   '0 20px 60px rgba(0,0,0,0.15)',
      },
      spacing: {
        'page-x': '32px',
        'page-y': '24px',
      },
    },
  },
}
export default config
```

---

## CSS Variables (globals.css)

```css
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;500;600;700&display=swap');

:root {
  --font-sans: 'Source Sans Pro', system-ui, sans-serif;

  /* Brand */
  --color-primary:       #2563EB;
  --color-primary-light: #3B82F6;
  --color-primary-dark:  #1D4ED8;
  --color-danger:        #DC2626;
  --color-gold:          #F59E0B;

  /* Backgrounds */
  --bg-page:             #EFF6FF;
  --bg-card:             #FFFFFF;
  --bg-dark-banner:      #1E3A8A;
  --bg-code-editor:      #1E1E1E;

  /* Text */
  --text-primary:        #111827;
  --text-secondary:      #374151;
  --text-muted:          #6B7280;
  --text-link:           #2563EB;

  /* Borders */
  --border-default:      #E2E8F0;
  --border-muted:        #F1F5F9;
  --border-focus:        #3B82F6;

  /* Active tab indicator */
  --tab-active-border:   2px solid #2563EB;
  --tab-active-color:    #2563EB;
  --tab-inactive-color:  #6B7280;

  /* Semantic */
  --success:             #16A34A;
  --success-light:       #22C55E;
  --warning:             #D97706;
  --danger-text:         #DC2626;
}
```

---

## Typography Scale

| Role | Size | Weight | Color | Line Height |
|------|------|--------|-------|-------------|
| Page Title | `24px / 1.5rem` | `700` | `#111827` | `1.2` |
| Section Title | `20px / 1.25rem` | `600` | `#111827` | `1.3` |
| Card Title | `16px / 1rem` | `600` | `#111827` | `1.4` |
| Body | `14px / 0.875rem` | `400` | `#374151` | `1.5` |
| Label / Meta | `12px / 0.75rem` | `500` | `#6B7280` | `1.4` |
| Badge | `11–12px` | `600` | varies | `1` |
| Table Header | `12px` | `600` | `#6B7280` (uppercase) | `1` |

Tailwind classes:
```
text-2xl font-bold    → Page Title
text-xl font-semibold → Section Title
text-base font-semibold → Card Title
text-sm               → Body
text-xs font-medium text-muted → Label/Meta
```

---

## Spacing System (base 4px)

| Token | Value | Usage |
|-------|-------|-------|
| `page-x` | `32px` | Horizontal page padding |
| `page-y` | `24px` | Vertical page padding |
| `section-gap` | `32px` | Between page sections |
| `card-padding` | `16–20px` | Inside cards |
| `card-gap` | `16px` | Between cards in a row |
| `sidebar-width` | `280px` | Right sidebar (fixed) |
| `drawer-width` | `290px` | Left nav drawer |
| `topnav-height` | `64px` | Top navigation bar |
| `tab-height` | `48px` | Tab bar height |

---

## shadcn/ui Component Overrides

Theme tokens that need to be set in `components.json` and `globals.css`:

```json
{
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "baseColor": "blue",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "hooks": "@/hooks"
  }
}
```

Override the default shadcn blue to `#2563EB` (already matches Tailwind's blue-600).

---

## Video Card Topic Color Mapping

```ts
export const TOPIC_COLORS: Record<string, string> = {
  os: '#3B82F6',
  systems: '#3B82F6',
  infrastructure: '#3B82F6',
  process: '#22C55E',
  data: '#22C55E',
  sql: '#F43F5E',
  database: '#F43F5E',
  queries: '#F43F5E',
  default: '#14B8A6',
}

export function getTopicColor(title: string): string {
  const lower = title.toLowerCase()
  for (const [key, color] of Object.entries(TOPIC_COLORS)) {
    if (lower.includes(key)) return color
  }
  return TOPIC_COLORS.default
}
```

---

## Animation Tokens

```css
/* Side drawer slide-in */
.drawer-enter { transform: translateX(-100%); }
.drawer-enter-active { transform: translateX(0); transition: transform 200ms ease-in-out; }

/* Backdrop fade */
.backdrop-enter { opacity: 0; }
.backdrop-enter-active { opacity: 1; transition: opacity 200ms ease-in-out; }

/* Card hover */
.card-hover { transition: box-shadow 150ms ease; }
.card-hover:hover { box-shadow: 0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -1px rgba(0,0,0,0.06); }
```
