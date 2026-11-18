import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

// The frontend calls /api/... and Vite forwards it to the backend,
// so the browser never talks to port 8080 directly (no CORS setup needed).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    build: {
      chunkSizeWarningLimit: 1200, // MapLibre alone is ~1 MB; it is in its own cached file
      rolldownOptions: {
        output: {
          // Big libraries in their own files: they change rarely, so browsers keep them
          // cached across deploys and only the small app file is downloaded again.
          advancedChunks: {
            groups: [
              { name: 'maplibre', test: /node_modules[\\/]maplibre-gl/ },
              { name: 'react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
              { name: 'ui', test: /node_modules[\\/](motion|motion-dom|motion-utils|framer-motion|@base-ui|@floating-ui|@number-flow|number-flow|sonner|cmdk)/ },
            ],
          },
        },
      },
    },
    server: {
      // the metrics catalogue is read from ../spec/metricas_modis_viirs.csv (outside frontend/)
      fs: { allow: ['..'] },
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://127.0.0.1:8080',
          changeOrigin: true,
        },
      },
    },
  }
})
