import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { VitePWA } from 'vite-plugin-pwa'

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
    }),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '数据中枢',
        short_name: '数据中枢',
        theme_color: '#0B63F6',
        background_color: '#0F172A',
        display: 'standalone',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      },
      workbox: {
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 3600
              }
            }
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif)$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'image-cache'
            }
          },
          {
            urlPattern: /\.(?:js|css|html)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-resources'
            }
          }
        ]
      }
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
            if (normalizedId.includes('/three/')) {
              return 'vendor-three'
            }
            if (normalizedId.includes('/echarts/') || normalizedId.includes('/zrender/')) {
              return 'vendor-echarts'
            }
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
        changeOrigin: true,
        secure: false
      },
      '/uploads': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false
      },
      '/healthz': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false
      },
      '/readyz': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false
      }
    }
  }
})
