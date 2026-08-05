import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // El backend vive en otro puerto en desarrollo. El proxy evita CORS y, de
    // paso, hace que en producción la aplicación sirva de un solo origen.
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  test: { environment: 'jsdom', globals: true },
})
