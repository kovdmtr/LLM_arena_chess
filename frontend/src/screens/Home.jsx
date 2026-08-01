/* Главная: герой с CTA, ключевые фичи и лента последних партий (живые данные). */
import GameCard from '../components/GameCard.jsx'
import Link from '../components/Link.jsx'
import { Empty, ErrorBanner, Skeletons } from '../components/States.jsx'
import { api } from '../lib/api.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

const RECENT_LIMIT = 5

const FEATURES = [
  ['★', 'Разбор качества ходов', 'Stockfish размечает каждый ход: от блестящего до зевка — с оценкой в сантипешках.'],
  ['♞', 'Подсказки движка', 'Каждой модели доступны три подсказки за партию — видно, когда она к ним прибегла.'],
  ['✎', 'Мысли и план', 'Модель объясняет ход и ведёт приватный план игры — всё сохраняется в отчёте.'],
]

function FeatureCard({ icon, title, body }) {
  return (
    <div className="card" style={{ padding: '22px 22px 24px', flex: '1 1 260px' }}>
      <div className="mono" style={{ fontSize: 22, marginBottom: 12 }}>
        {icon}
      </div>
      <h3 style={{ fontSize: 19, marginBottom: 7 }}>{title}</h3>
      <p style={{ margin: 0, color: 'var(--muted)', fontSize: 14.5, lineHeight: 1.55 }}>{body}</p>
    </div>
  )
}

export default function Home() {
  const games = useAsync(() => api.games(), [])
  const models = useAsync(() => api.models(), [])
  const catalog = indexModels(models.data || [])
  const recent = (games.data || []).slice(0, RECENT_LIMIT)

  return (
    <div className="fade-in">
      <section className="wrap" style={{ paddingTop: 40, paddingBottom: 28 }}>
        <span className="eyebrow">Шахматная арена для языковых моделей</span>
        <h1 style={{ fontSize: 'clamp(30px, 3.4vw, 42px)', marginTop: 12 }}>Арена</h1>
        <p style={{ fontSize: 16, color: 'var(--ink-2)', maxWidth: 520, marginTop: 12, lineHeight: 1.55 }}>
          Запустите партию двух моделей или откройте сыгранную — с разбором качества ходов от
          Stockfish, мыслями моделей и планом на каждый ход.
        </p>
        <div className="row gap-3" style={{ marginTop: 22, flexWrap: 'wrap' }}>
          <Link href={hrefFor('new-game')} className="btn btn-primary btn-lg">
            Запустить партию
          </Link>
          <Link href={hrefFor('archive')} className="btn btn-ghost btn-lg">
            Архив партий
          </Link>
          <Link href={hrefFor('tournaments')} className="btn btn-ghost btn-lg">
            Турниры
          </Link>
        </div>
      </section>

      <section className="wrap" style={{ paddingBottom: 32 }}>
        <div className="row gap-4" style={{ alignItems: 'stretch', flexWrap: 'wrap' }}>
          {FEATURES.map(([icon, title, body]) => (
            <FeatureCard key={title} icon={icon} title={title} body={body} />
          ))}
        </div>
      </section>

      <section className="wrap" style={{ paddingBottom: 56 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <h2 style={{ fontSize: 24 }}>Последние партии</h2>
          <Link href={hrefFor('archive')} className="btn btn-quiet btn-sm">
            Все партии →
          </Link>
        </div>

        <ErrorBanner error={games.error} />
        {games.loading && <Skeletons count={3} />}
        {!games.loading && !games.error && recent.length === 0 && (
          <Empty title="Пока ни одной партии">
            Запустите первую — она появится здесь и в архиве.
          </Empty>
        )}
        <div className="col gap-2">
          {recent.map((game) => (
            <GameCard key={game.id} game={game} catalog={catalog} />
          ))}
        </div>
      </section>
    </div>
  )
}
