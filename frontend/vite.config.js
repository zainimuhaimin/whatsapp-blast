import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/*.png'],
      manifest: {
        name: 'WA Blast — Tool Broadcast WhatsApp',
        short_name: 'WA Blast',
        description:
          'Kelola kontak, template, dan campaign broadcast WhatsApp dengan throttling anti-ban.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#f7faf8',
        theme_color: '#0d5c2e',
        lang: 'id',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Jangan pernah cache panggilan API — selalu ke jaringan.
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkOnly',
          },
        ],
      },
      devOptions: {
        // Matikan SW saat dev agar tidak mengganggu hot-reload.
        enabled: false,
      },
    }),
  ],
  server: {
    port: 5173,
    host: true,
    // Dev proxy: panggilan /api diteruskan ke backend lokal (tanpa CORS issue).
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
