/* Комплект SVG фигур с бэкенда (`GET /api/pieces`).
 *
 * Тот же комплект, что в самодостаточном отчёте (python-chess), — доска на
 * сайте и в скачанном файле выглядит одинаково. Набор неизменен, поэтому
 * запрашивается один раз на вкладку и разделяется всеми досками.
 */
import { useEffect, useState } from 'react'

import { api } from './api.js'

let cache = null
let pending = null

function load() {
  if (cache) return Promise.resolve(cache)
  if (!pending) {
    pending = api
      .pieces()
      .then((data) => {
        cache = data
        return data
      })
      .catch(() => {
        pending = null // дадим следующему экрану попробовать снова
        return null
      })
  }
  return pending
}

export function usePieces() {
  const [pieces, setPieces] = useState(cache)

  useEffect(() => {
    if (cache) return undefined
    let alive = true
    load().then((data) => {
      if (alive && data) setPieces(data)
    })
    return () => {
      alive = false
    }
  }, [])

  return pieces
}
