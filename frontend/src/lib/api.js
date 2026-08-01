/* Клиент JSON-API бэкенда (`/api/*`, см. src/arena/web/api.py).
 *
 * Токен доступа: сайт может быть закрыт «секретной ссылкой» (docs/FRONTEND.md §4).
 * Обычно хватает cookie `arena_access`, которую ставит бэкенд при первом заходе
 * по `…/?token=…`. Но в dev-режиме index.html отдаёт Vite (гейт его не видит),
 * поэтому токен из адресной строки на всякий случай прокидываем в каждый запрос.
 */

/** Ошибка API: несёт HTTP-статус и человекочитаемый текст для баннера. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
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

/** Текст ошибки из ответа FastAPI: `detail` строкой, списком или ничем. */
export function errorMessage(body, status) {
  const detail = body && body.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    const parts = detail.map((item) => (item && item.msg) || String(item))
    return parts.join('; ')
  }
  if (status === 404) return 'Не найдено.'
  if (status === 403) return 'Нет доступа: откройте сайт по ссылке с токеном.'
  return `Ошибка запроса (${status}).`
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
    throw new ApiError('Сервер недоступен — проверьте, что бэкенд запущен.', 0)
  }
  if (response.status === 204) return null

  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) throw new ApiError(errorMessage(body, response.status), response.status)
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
  games: () => getJson('/api/games'),
  game: (id) => getJson(`/api/games/${encodeURIComponent(id)}`),
  startGame: (white, black) => postJson('/api/games', { white, black }),
  pgnUrl: (id) => withToken(`/api/games/${encodeURIComponent(id)}/pgn`, currentSearch()),
  tournaments: () => getJson('/api/tournaments'),
  tournament: (id) => getJson(`/api/tournaments/${encodeURIComponent(id)}`),
  startTournament: (models, double) => postJson('/api/tournaments', { models, double }),
}
