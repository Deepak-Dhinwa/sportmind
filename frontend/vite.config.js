import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // The page is opened on localhost, which resolves to IPv6 first.
    // The API listens on IPv4. Proxying keeps every call on the page's own origin.
    proxy: {
      "/stats": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/graph": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/predict": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/knowledge": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/system": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/chat": { target: "http://127.0.0.1:8000", ws: true, changeOrigin: true },
    },
  },
})
