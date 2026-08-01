/* Клиент JSON-API бэкенда (`/api/*`, см. src/arena/web/api.py).
 *
 * Токен доступа: сайт может быть закрыт «секретной ссылкой» (docs/FRONTEND.md §4).
 * Обычно хватает cookie `arena_access`, которую ставит бэкенд при первом заходе
 * по `…/?token=…`. Но в dev-режиме index.html отдаёт Vite (гейт его не видит),
 * поэтому токен из адресной строки на всякий случай прокидываем в каждый запрос.
 */

/**
 * Ошибка API для баннера.
 *
 * Текст берётся из двух источников: `key`/`params` — наш словарь (переводится
 * на язык интерфейса), `text` — сообщение самого бэкенда (`detail`), которое
 * показываем как есть: оно объясняет отказ конкретнее любого общего перевода.
 */
export class ApiError extends Error {
  constructor({ key, params, text, status }) {
    super(text || key || 'error.generic')
    this.name = 'ApiError'
    this.key = key || null
    this.params = params || null
    this.text = text || null
    this.status = status
  }
}

/** Достать токен доступа из query-строки (`?token=…`), если он там есть. */
export function tokenFrom(search) {
  const value = new URLSearchParams(search || '').get('token')
  return value || null
}

/** Добавить к пути токен доступа, не затирая уже имеющиеся query-параметры. */
export function withToken(path, search) {
  const token = tokenFrom(search)
  if (!token) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}token=${encodeURIComponent(token)}`
}

/**
 * Что показать по ответу FastAPI: ключ словаря либо готовый текст.
 *
 * Наш `/api/*` отдаёт `detail = {code, params, message}` — код переводим на
 * язык интерфейса, `message` (техническая подробность нижних слоёв) держим
 * про запас на случай незнакомого кода. Строка/список в `detail` — чужой
 * формат (валидация FastAPI, прокси): показываем как есть.
 */
export function errorInfo(body, status) {
  const detail = body && body.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.code) {
    return { key: detail.code, params: detail.params || null, text: detail.message || null }
  }
  if (typeof detail === 'string' && detail) return { text: detail }
  if (Array.isArray(detail) && detail.length) {
    return { text: detail.map((item) => (item && item.msg) || String(item)).join('; ') }
  }
  if (status === 404) return { key: 'error.notFound' }
  if (status === 403) return { key: 'error.forbidden' }
  return { key: 'error.generic', params: { status } }
}

function currentSearch() {
  return typeof location === 'undefined' ? '' : location.search
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(withToken(path, currentSearch()), {
      headers: { Accept: 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch (cause) {
    throw new ApiError({ key: 'error.network', status: 0 })
  }
  if (response.status === 204) return null

  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) throw new ApiError({ ...errorInfo(body, response.status), status: response.status })
  return body
}

/** GET JSON. */
export function getJson(path) {
  return request(path)
}

/** POST JSON. */
export function postJson(path, payload) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/* --- эндпоинты (тонкие обёртки, чтобы пути жили в одном месте) --- */

export const api = {
  models: () => getJson('/api/models'),
  pieces: () => getJson('/api/pieces'),
  games: () => getJson('/api/games'),
  game: (id) => getJson(`/api/games/${encodeURIComponent(id)}`),
  // language — язык интерфейса: на нём модели пишут рассуждения и план
  startGame: (white, black, language) => postJson('/api/games', { white, black, language }),
  pgnUrl: (id) => withToken(`/api/games/${encodeURIComponent(id)}/pgn`, currentSearch()),
  // самодостаточный HTML-отчёт файлом: открывается без сервера и без сети
  reportUrl: (id) => withToken(`/api/games/${encodeURIComponent(id)}/report`, currentSearch()),
  tournaments: () => getJson('/api/tournaments'),
  tournament: (id) => getJson(`/api/tournaments/${encodeURIComponent(id)}`),
  startTournament: (models, double, language) =>
    postJson('/api/tournaments', { models, double, language }),
}
