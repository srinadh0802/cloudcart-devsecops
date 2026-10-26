import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local development API proxy. Nginx/API gateway will be created in the DevOps stages.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(Object.entries({
      auth: 8001, stores: 8002, catalog: 8003,
      inventory: 8004, orders: 8005, delivery: 8006
    }).map(([service, port]) => [
      `/api/${service}`,
      { target: `http://127.0.0.1:${port}`, changeOrigin: true,
        rewrite: path => path.replace(new RegExp(`^/api/${service}`), '') }
    ]))
  }
})
