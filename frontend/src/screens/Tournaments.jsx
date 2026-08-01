/* Список турниров: карточки с участниками, прогрессом и статусом. */
import Link from '../components/Link.jsx'
import { Empty, ErrorBanner, Skeletons } from '../components/States.jsx'
import TournamentCard from '../components/TournamentCard.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

export default function Tournaments() {
  const t = useT()
  const tournaments = useAsync(() => api.tournaments(), [])
  const models = useAsync(() => api.models(), [])
  const catalog = indexModels(models.data || [])
  const list = tournaments.data || []

  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <span className="eyebrow">{t('tournaments.eyebrow')}</span>
          <h1 style={{ fontSize: 36, margin: '12px 0 0' }}>{t('tournaments.title')}</h1>
          <p style={{ color: 'var(--muted)', margin: '10px 0 0', maxWidth: 520 }}>
            {t('tournaments.lead')}
          </p>
        </div>
        <div className="row gap-2">
          <button
            className="btn btn-ghost btn-sm"
            onClick={tournaments.reload}
            disabled={tournaments.loading}
          >
            {t('action.refresh')}
          </button>
          <Link href={hrefFor('new-tournament')} className="btn btn-primary btn-sm">
            {t('tournaments.create')}
          </Link>
        </div>
      </div>

      <div style={{ marginTop: 22 }}>
        <ErrorBanner error={tournaments.error} />
        {tournaments.loading && <Skeletons count={3} />}
        {!tournaments.loading && !tournaments.error && list.length === 0 && (
          <Empty title={t('tournaments.empty.title')}>{t('tournaments.empty.body')}</Empty>
        )}
        <div className="col gap-2">
          {list.map((tournament) => (
            <TournamentCard key={tournament.id} tournament={tournament} catalog={catalog} />
          ))}
        </div>
      </div>
    </div>
  )
}
