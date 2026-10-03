import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Built with RELATIVE asset URLs (base './'). The backend injects <base href="${BASE_PATH}/">
// into index.html, so the same build works at /inventory (or any other prefix) with no rebuild.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: { outDir: 'dist', assetsDir: '_app', chunkSizeWarningLimit: 900 },
  server: {
    // dev: open http://localhost:5173/ ; API proxied to the backend running with BASE_PATH=/inventory
    proxy: { '/api': { target: 'http://localhost:8000', rewrite: (p) => '/inventory' + p } },
  },
})
