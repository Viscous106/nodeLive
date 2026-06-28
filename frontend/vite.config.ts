import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// COOP/COEP headers are MANDATORY for the Zoom Meeting SDK — its WASM media
// engine requires cross-origin isolation. Removing these silently breaks
// audio/video in some browsers. Ported from the nodeLive prototype.
const crossOriginIsolation = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    headers: crossOriginIsolation,
  },
  preview: {
    headers: crossOriginIsolation,
  },
})
