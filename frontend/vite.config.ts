import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      includeAssets: ['pwa-icon.svg'],
      manifest: {
        name: 'Hilti RouteIQ',
        short_name: 'RouteIQ',
        description: 'AI sales visit copilot for Hilti field salespeople.',
        theme_color: '#d2051e',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/pwa-icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
        ],
      },
      registerType: 'autoUpdate',
      workbox: {
        navigateFallback: '/',
        runtimeCaching: [
          {
            urlPattern: /^http:\/\/localhost:8000\/salespeople\/.*\/day-plan/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'day-plan-cache',
              expiration: {
                maxEntries: 8,
                maxAgeSeconds: 60 * 60 * 12,
              },
            },
          },
        ],
      },
    }),
  ],
})
