/* Архив: все партии (память + диск), идущие идут первыми — так их отдаёт API. */
import GameCard from '../components/GameCard.jsx'
import Link from '../components/Link.jsx'
import { Empty, ErrorBanner, Skeletons } from '../components/States.jsx'
import { api } from '../lib/api.js'
import { plural } from '../lib/format.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

export default function Archive() {
  const games = useAsync(() => api.games(), [])
  const models = useAsync(() => api.models(), [])
  const catalog = indexModels(models.data || [])
  const list = games.data || []
  const liveCount = list.filter((game) => game.live).length

  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <span className="eyebrow">Архив</span>
          <h1 style={{ fontSize: 36, margin: '12px 0 0' }}>Все партии</h1>
          <p style={{ color: 'var(--muted)', margin: '10px 0 0' }}>
            {games.loading
              ? 'Загружаем…'
              : `${list.length} ${plural(list.length, 'партия', 'партии', 'партий')}` +
                (liveCount ? ` · ${liveCount} в эфире` : '')}
          </p>
        </div>
        <div className="row gap-2">
          <button className="btn btn-ghost btn-sm" onClick={games.reload} disabled={games.loading}>
            ↻ Обновить
          </button>
          <Link href={hrefFor('new-game')} className="btn btn-primary btn-sm">
            ＋ Запустить
          </Link>
        </div>
      </div>

      <div style={{ marginTop: 22 }}>
        <ErrorBanner error={games.error} />
        {games.loading && <Skeletons count={5} />}
        {!games.loading && !games.error && list.length === 0 && (
          <Empty title="Партий пока нет">
            Запустите первую партию — она появится здесь сразу после старта.
          </Empty>
        )}
        <div className="col gap-2">
          {list.map((game) => (
            <GameCard key={game.id} game={game} catalog={catalog} />
          ))}
        </div>
      </div>
    </div>
  )
}
