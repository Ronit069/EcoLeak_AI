import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Phase 1 swap: point /api at P2 live backend once available.
      // Mock mode (default) serves /mocks/*.json from public/.
      '/api': {
        target: process.env.ECOLEAK_API_URL ?? 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
