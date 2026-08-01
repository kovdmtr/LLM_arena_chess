/* Главная: герой с CTA, ключевые фичи и лента последних партий (живые данные). */
import GameCard from '../components/GameCard.jsx'
import Link from '../components/Link.jsx'
import { Empty, ErrorBanner, Skeletons } from '../components/States.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

const RECENT_LIMIT = 5

const FEATURES = [
  ['★', 'analysis'],
  ['♞', 'hints'],
  ['✎', 'plan'],
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
  const t = useT()
  const games = useAsync(() => api.games(), [])
  const models = useAsync(() => api.models(), [])
  const catalog = indexModels(models.data || [])
  const recent = (games.data || []).slice(0, RECENT_LIMIT)

  return (
    <div className="fade-in">
      <section className="wrap" style={{ paddingTop: 40, paddingBottom: 28 }}>
        <span className="eyebrow">{t('home.eyebrow')}</span>
        <h1 style={{ fontSize: 'clamp(30px, 3.4vw, 42px)', marginTop: 12 }}>{t('home.title')}</h1>
        <p style={{ fontSize: 16, color: 'var(--ink-2)', maxWidth: 520, marginTop: 12, lineHeight: 1.55 }}>
          {t('home.lead')}
        </p>
        <div className="row gap-3" style={{ marginTop: 22, flexWrap: 'wrap' }}>
          <Link href={hrefFor('new-game')} className="btn btn-primary btn-lg">
            {t('home.cta.play')}
          </Link>
          <Link href={hrefFor('archive')} className="btn btn-ghost btn-lg">
            {t('home.cta.archive')}
          </Link>
          <Link href={hrefFor('tournaments')} className="btn btn-ghost btn-lg">
            {t('home.cta.tournaments')}
          </Link>
        </div>
      </section>

      <section className="wrap" style={{ paddingBottom: 32 }}>
        <div className="row gap-4" style={{ alignItems: 'stretch', flexWrap: 'wrap' }}>
          {FEATURES.map(([icon, name]) => (
            <FeatureCard
              key={name}
              icon={icon}
              title={t(`home.feature.${name}.title`)}
              body={t(`home.feature.${name}.body`)}
            />
          ))}
        </div>
      </section>

      <section className="wrap" style={{ paddingBottom: 56 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <h2 style={{ fontSize: 24 }}>{t('home.recent.title')}</h2>
          <Link href={hrefFor('archive')} className="btn btn-quiet btn-sm">
            {t('home.recent.all')}
          </Link>
        </div>

        <ErrorBanner error={games.error} />
        {games.loading && <Skeletons count={3} />}
        {!games.loading && !games.error && recent.length === 0 && (
          <Empty title={t('home.recent.empty.title')}>{t('home.recent.empty.body')}</Empty>
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
