import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:10000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
