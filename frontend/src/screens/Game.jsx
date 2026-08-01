/* Экран партии по deep link `/games/{id}`.
 *
 * Идущая партия → живой просмотр по WebSocket; завершённая → разбор с плеером.
 * Такое же разветвление, как у SSR-роута `GET /games/{id}` — адреса и
 * поведение совпадают.
 */
import { ErrorBanner, Skeletons } from '../components/States.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { useAsync } from '../lib/useAsync.js'
import LiveGame from './LiveGame.jsx'
import Report from './Report.jsx'

export default function Game({ id }) {
  const t = useT()
  const game = useAsync(() => api.game(id), [id])

  if (game.loading) {
    return (
      <div className="wrap" style={{ paddingTop: 40, paddingBottom: 64 }}>
        <Skeletons count={2} height={180} />
      </div>
    )
  }

  if (game.error) {
    return (
      <div className="wrap" style={{ paddingTop: 40, paddingBottom: 64 }}>
        <ErrorBanner error={game.error} />
        <button className="btn btn-ghost" style={{ marginTop: 16 }} onClick={game.reload}>
          {t('action.refresh')}
        </button>
      </div>
    )
  }

  if (game.data.live) {
    // по завершении партии перечитываем запись — она уже с анализом
    return <LiveGame id={id} record={game.data.record} onFinished={game.reload} />
  }

  return <Report record={game.data.record} />
}
