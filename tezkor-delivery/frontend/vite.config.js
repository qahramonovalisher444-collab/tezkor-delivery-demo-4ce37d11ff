import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    watch: { ignored: ['**/dist/**', '**/test-results/**', '**/playwright-report/**'] },
    proxy: { '/api': process.env.TEZKOR_API_PROXY || 'http://127.0.0.1:8000', '/admin': process.env.TEZKOR_API_PROXY || 'http://127.0.0.1:8000' },
  },
})
