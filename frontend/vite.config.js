import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const api = 'https://ops-website.onrender.com'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8001', '/uploads': 'http://localhost:8001' } },
  preview: {
    allowedHosts: ['ops-ke-website.onrender.com'],
    proxy: {
      '/api': { target: api, changeOrigin: true },
      '/uploads': { target: api, changeOrigin: true },
    },
  },
})