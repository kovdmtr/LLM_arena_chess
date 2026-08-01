/* Загрузка данных API: состояние `{data, error, loading}` + повтор запроса.
 *
 * Отдельного стора не заводим — экранам хватает одного запроса на монтирование.
 */
import { useCallback, useEffect, useState } from 'react'

export function useAsync(load, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [nonce, setNonce] = useState(0)

  // load приходит из тела компонента (новая функция на каждый рендер) — держим
  // зависимость на явном списке deps, иначе запрос уйдёт в цикл.
  const run = useCallback(load, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let alive = true
    setState((prev) => ({ ...prev, loading: true }))
    run()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState({ data: null, error, loading: false }))
    return () => {
      alive = false
    }
  }, [run, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { ...state, reload }
}
