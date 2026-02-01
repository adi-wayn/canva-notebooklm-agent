import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy API calls to the FastAPI server during local development
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
