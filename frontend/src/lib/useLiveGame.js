/* Подключение к WS живой партии: свёртка кадров в состояние экрана.
 *
 * Токен доступа кладём в query — на HTTPS это `wss` (docs/FRONTEND.md §4).
 * Сервер сам переигрывает накопленные кадры, поэтому перезагрузка страницы
 * восстанавливает партию целиком; `record` нужен лишь для мгновенной отрисовки.
 */
import { useEffect, useReducer, useRef } from 'react'

import { tokenFrom } from './api.js'
import { LIVE_ERROR, applyFrame, initialLiveState } from './live.js'

/** ws(s)://host/games/{id}/ws с токеном доступа, если он есть в адресе. */
export function liveSocketUrl(id, { protocol, host, search } = {}) {
  const scheme = (protocol || location.protocol) === 'https:' ? 'wss:' : 'ws:'
  const token = tokenFrom(search === undefined ? location.search : search)
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${scheme}//${host || location.host}/games/${encodeURIComponent(id)}/ws${query}`
}

function reducer(state, action) {
  if (action.type === 'frame') return applyFrame(state, action.frame)
  if (action.type === 'socket-error') {
    // Обрыв после финала — норма: сервер закрывает сокет сам.
    if (state.status === LIVE_ERROR || state.result) return state
    return { ...state, status: LIVE_ERROR, errorKey: 'live.disconnected' }
  }
  return state
}

export function useLiveGame(id, record) {
  const [state, dispatch] = useReducer(reducer, record, initialLiveState)
  const socketRef = useRef(null)

  useEffect(() => {
    if (!id) return undefined
    const socket = new WebSocket(liveSocketUrl(id))
    socketRef.current = socket

    socket.onmessage = (event) => {
      let frame = null
      try {
        frame = JSON.parse(event.data)
      } catch {
        return // мусор в сокете не должен ронять экран
      }
      dispatch({ type: 'frame', frame })
    }
    socket.onerror = () => dispatch({ type: 'socket-error' })

    return () => {
      socket.onmessage = null
      socket.onerror = null
      socket.close()
    }
  }, [id])

  return state
}
