import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/tracks': 'http://localhost:5000',
      '/status': 'http://localhost:5000',
      '/scores': 'http://localhost:5000',
      '/refresh': 'http://localhost:5000',
      '/eval': 'http://localhost:5000',
    }
  }
})
