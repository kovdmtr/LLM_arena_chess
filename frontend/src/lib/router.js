/* Разбор URL → экран. Чистый модуль: без DOM, поэтому легко тестируется.
 *
 * Пути намеренно совпадают с роутами бэкенда (`docs/FRONTEND.md` §2): SPA живёт
 * по тем же адресам, что и старый SSR-фронт, поэтому ссылки и закладки
 * (в т.ч. deep links вида /games/{id}) продолжают работать после переезда.
 */

/** Экран «не найдено» — единая точка, чтобы не плодить строки-литералы. */
export const NOT_FOUND = 'not-found'

/**
 * Разобрать путь в маршрут `{name, params}`.
 *
 * Хвостовой слэш игнорируется; неизвестный путь даёт `not-found`.
 */
export function parseRoute(pathname) {
  const parts = String(pathname || '/')
    .split('/')
    .filter(Boolean)

  if (parts.length === 0) return { name: 'home', params: {} }

  const [head, tail, extra] = parts
  if (extra !== undefined) return { name: NOT_FOUND, params: {} }

  if (head === 'games') {
    if (tail === undefined) return { name: 'archive', params: {} }
    if (tail === 'new') return { name: 'new-game', params: {} }
    return { name: 'game', params: { id: tail } }
  }

  if (head === 'tournaments') {
    if (tail === undefined) return { name: 'tournaments', params: {} }
    if (tail === 'new') return { name: 'new-tournament', params: {} }
    return { name: 'tournament', params: { id: tail } }
  }

  return { name: NOT_FOUND, params: {} }
}

/** Путь экрана: обратная операция к `parseRoute` (для ссылок и переходов). */
export function hrefFor(name, params = {}) {
  switch (name) {
    case 'home':
      return '/'
    case 'archive':
      return '/games'
    case 'new-game':
      return '/games/new'
    case 'game':
      return `/games/${encodeURIComponent(params.id)}`
    case 'tournaments':
      return '/tournaments'
    case 'new-tournament':
      return '/tournaments/new'
    case 'tournament':
      return `/tournaments/${encodeURIComponent(params.id)}`
    default:
      return '/'
  }
}

/**
 * Активен ли пункт навигации: раздел считается активным и на вложенных экранах
 * (страница партии подсвечивает «Партии», страница турнира — «Турниры»).
 */
export function isActiveNav(navName, route) {
  if (navName === route.name) return true
  if (navName === 'archive') return route.name === 'game'
  if (navName === 'tournaments') return route.name === 'tournament' || route.name === 'new-tournament'
  return false
}
