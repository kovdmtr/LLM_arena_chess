import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Сборка кладётся внутрь питон-пакета (src/arena/web/spa) — тогда FastAPI находит
// её относительно __file__ и она едет вместе с пакетом (в т.ч. в Docker-образ).
// Каталог сборки в .gitignore: в репозитории живут исходники, не артефакты.
//
// dev-сервер (npm run dev) проксирует на локальный uvicorn только данные:
//   /api/*            — JSON-API
//   /games/{id}/ws    — WebSocket живой партии (только он, остальные /games/* —
//                       это маршруты самого SPA и должны отдаваться Vite)
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../src/arena/web/spa',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '^/games/[^/]+/ws$': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.js', '*.test.js'],
  },
})
