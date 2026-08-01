/* Тесты конфигурации сборки: инварианты, от которых зависит раздача SPA. */
import { describe, expect, it } from 'vitest'

import config from './vite.config.js'

const WS_RULE = '^/games/[^/]+/ws$'

describe('vite build', () => {
  it('кладёт сборку внутрь питон-пакета — FastAPI ищет её относительно __file__', () => {
    expect(config.build.outDir).toBe('../src/arena/web/spa')
  })

  it('чистит каталог сборки, чтобы не копились старые хешированные ассеты', () => {
    expect(config.build.emptyOutDir).toBe(true)
  })
})

describe('dev-прокси', () => {
  it('отдаёт бэкенду данные, а не маршруты SPA', () => {
    // на бэкенде остались только /api и WS — серверной вёрстки и статики нет
    expect(Object.keys(config.server.proxy)).toContain('/api')
  })

  it('проксирует только WebSocket партии — страница /games/{id} остаётся за SPA', () => {
    const ws = new RegExp(WS_RULE)

    expect(ws.test('/games/abc123/ws')).toBe(true)
    expect(ws.test('/games/abc123')).toBe(false)
    expect(ws.test('/games')).toBe(false)
    expect(config.server.proxy[WS_RULE].ws).toBe(true)
  })
})
