/* Список турниров: карточки с участниками, прогрессом и статусом. */
import Link from '../components/Link.jsx'
import { Empty, ErrorBanner, Skeletons } from '../components/States.jsx'
import { useLang, useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { formatWhen, progressLabel } from '../lib/format.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

function TournamentCard({ tournament, catalog, t, lang }) {
  const when = formatWhen(tournament.created_at, new Date(), lang)
  const names = tournament.participants.map((id) => {
    const model = catalog.find(id)
    return model ? model.display_name : id
  })

  return (
    <Link href={hrefFor('tournament', { id: tournament.id })} className="rowcard">
      <div className="col" style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <span style={{ fontWeight: 700 }}>{names.join(' · ')}</span>
        <div className="row gap-2" style={{ minWidth: 0, flexWrap: 'wrap' }}>
          <span className={'badge' + (tournament.live ? ' badge-live' : ' badge-done')}>
            {tournament.live && <span className="dot" />}
            {tournament.live ? t('status.live') : t('status.finished')}
          </span>
          <span className="mono tnum" style={{ fontSize: 12, color: 'var(--muted)' }}>
            {progressLabel(tournament.played, tournament.total)}
          </span>
          {tournament.double && <span className="badge">{t('tournaments.double')}</span>}
          <span style={{ color: 'var(--faint)', fontSize: 12, marginLeft: 'auto' }}>
            {when ? t(when.key, when.params) : ''}
          </span>
        </div>
      </div>
    </Link>
  )
}

export default function Tournaments() {
  const t = useT()
  const { lang } = useLang()
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
            <TournamentCard
              key={tournament.id}
              tournament={tournament}
              catalog={catalog}
              t={t}
              lang={lang}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
