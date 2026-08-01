/* Главная: заголовок с кнопками и живые данные — партии и турниры.
 *
 * Рекламных блоков (маркетинговый подзаголовок, карточки «фич») здесь нет
 * намеренно: главная — это точка входа к партиям, а не витрина. */
import GameCard from '../components/GameCard.jsx'
import Link from '../components/Link.jsx'
import { Empty, ErrorBanner, Skeletons } from '../components/States.jsx'
import TournamentCard from '../components/TournamentCard.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

const RECENT_LIMIT = 5
const TOURNAMENT_LIMIT = 3

export default function Home() {
  const t = useT()
  const games = useAsync(() => api.games(), [])
  const models = useAsync(() => api.models(), [])
  const tournaments = useAsync(() => api.tournaments(), [])
  const catalog = indexModels(models.data || [])
  const recent = (games.data || []).slice(0, RECENT_LIMIT)
  // идущие турниры API отдаёт первыми — на главной показываем верхушку списка
  const recentTournaments = (tournaments.data || []).slice(0, TOURNAMENT_LIMIT)

  return (
    <div className="fade-in">
      <section className="wrap" style={{ paddingTop: 40, paddingBottom: 28 }}>
        <h1 style={{ fontSize: 'clamp(28px, 3.2vw, 38px)' }}>{t('home.title')}</h1>
        <div className="row gap-3" style={{ marginTop: 20, flexWrap: 'wrap' }}>
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

      <section className="wrap" style={{ paddingBottom: 64 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <h2 style={{ fontSize: 24 }}>{t('tournaments.title')}</h2>
          <Link href={hrefFor('tournaments')} className="btn btn-quiet btn-sm">
            {t('home.tournaments.all')}
          </Link>
        </div>

        <ErrorBanner error={tournaments.error} />
        {tournaments.loading && <Skeletons count={2} />}
        {!tournaments.loading && !tournaments.error && recentTournaments.length === 0 && (
          <Empty title={t('tournaments.empty.title')}>
            <Link href={hrefFor('new-tournament')} className="btn btn-ghost btn-sm">
              {t('tournaments.create')}
            </Link>
          </Empty>
        )}
        <div className="col gap-2">
          {recentTournaments.map((tournament) => (
            <TournamentCard key={tournament.id} tournament={tournament} catalog={catalog} />
          ))}
        </div>
      </section>
    </div>
  )
}
