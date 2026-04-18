import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

const proxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [
    vue(),
    Components({
      dts: false,
      resolvers: [
        ElementPlusResolver({
          importStyle: 'css'
        })
      ]
    })
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/')

          if (normalizedId.includes('/node_modules/')) {
            if (normalizedId.includes('/element-plus/') || normalizedId.includes('/@element-plus/')) {
              return 'vendor-ui'
            }
            if (normalizedId.includes('/vue-router/') || normalizedId.includes('/vue/') || normalizedId.includes('/pinia/')) {
              return 'vendor-vue'
            }
            if (normalizedId.includes('/axios/')) {
              return 'vendor-axios'
            }
            if (normalizedId.includes('/dayjs/')) {
              return 'vendor-dayjs'
            }
            if (normalizedId.includes('/async-validator/')) {
              return 'vendor-form'
            }
            return 'vendor'
          }

          return undefined
        }
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true
      },
      '/uploads': {
        target: proxyTarget,
        changeOrigin: true
      },
      '/healthz': {
        target: proxyTarget,
        changeOrigin: true
      },
      '/readyz': {
        target: proxyTarget,
        changeOrigin: true
      }
    }
  }
})
