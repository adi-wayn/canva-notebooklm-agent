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
        // Critical for SSE: disable buffering and enable streaming
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            // Disable buffering for SSE endpoints
            if (req.url.includes('/stream')) {
              proxyReq.setHeader('X-Accel-Buffering', 'no');
            }
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // Ensure SSE responses are not buffered
            if (req.url.includes('/stream')) {
              proxyRes.headers['x-accel-buffering'] = 'no';
            }
          });
        },
      },
    },
  },
});
