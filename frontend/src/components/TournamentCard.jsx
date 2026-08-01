/* Строка-карточка турнира: участники, статус, прогресс, когда запущен.
 * Общая для списка турниров и блока на главной. */
import { useLang, useT } from '../lib/LangContext.jsx'
import { formatWhen, progressLabel } from '../lib/format.js'
import { hrefFor } from '../lib/router.js'
import Link from './Link.jsx'

export default function TournamentCard({ tournament, catalog }) {
  const t = useT()
  const { lang } = useLang()
  const when = formatWhen(tournament.created_at, new Date(), lang)
  const names = tournament.participants.map((id) => {
    const model = catalog && catalog.find(id)
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
