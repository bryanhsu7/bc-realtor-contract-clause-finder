import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            if (res.writableEnded || res.headersSent) return
            const code = err.code || ''
            const detail =
              code === 'ECONNREFUSED' || code === 'ECONNRESET'
                ? 'Nothing is accepting connections on port 8000. From the repo root run: `python -m backend.main` (venv activated, OPENAI_API_KEY set). Requests from this dev server proxy `/api` to **localhost:8000**.'
                : `Dev proxy failed (${code || err.message || 'unknown'}). Is the backend running on port 8000?`

            res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
            res.end(JSON.stringify({ detail }))
          })
        },
      },
    },
  },
})
