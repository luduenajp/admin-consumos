import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendPort = process.env.BACKEND_PORT ?? '8000'
const backendTarget = `http://localhost:${backendPort}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev: proxy a puerto 8000 (o BACKEND_PORT si está definido)
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true, // escuchar en 0.0.0.0 para aceptar conexiones externas
    // Producción local: proxy al backend en el puerto configurado
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
    // Permitir acceso desde www.consumofamiliar.com
    allowedHosts: ['www.consumofamiliar.com', 'localhost', '127.0.0.1'],
  },
})
