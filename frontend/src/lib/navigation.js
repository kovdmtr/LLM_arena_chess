/* Навигация SPA поверх History API: переходы без перезагрузки + хук маршрута. */
import { useEffect, useState } from 'react'

import { tokenFrom } from './api.js'
import { parseRoute } from './router.js'

const NAV_EVENT = 'arena:navigate'

/** Сохранить `?token=…` при переходе: по нему живёт доступ «по секретной ссылке». */
function keepToken(href) {
  const token = tokenFrom(location.search)
  if (!token || href.includes('token=')) return href
  const sep = href.includes('?') ? '&' : '?'
  return `${href}${sep}token=${encodeURIComponent(token)}`
}

/** Перейти на внутренний адрес (без перезагрузки страницы). */
export function navigate(href, { replace = false } = {}) {
  const url = keepToken(href)
  if (replace) history.replaceState(null, '', url)
  else history.pushState(null, '', url)
  window.dispatchEvent(new Event(NAV_EVENT))
  window.scrollTo(0, 0)
}

/** Текущий маршрут; обновляется при переходах и кнопке «назад». */
export function useRoute() {
  const [route, setRoute] = useState(() => parseRoute(location.pathname))

  useEffect(() => {
    const sync = () => setRoute(parseRoute(location.pathname))
    window.addEventListener('popstate', sync)
    window.addEventListener(NAV_EVENT, sync)
    return () => {
      window.removeEventListener('popstate', sync)
      window.removeEventListener(NAV_EVENT, sync)
    }
  }, [])

  return route
}
