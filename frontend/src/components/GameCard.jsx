/* Строка-карточка партии для главной и архива: стороны, статус, итог, время. */
import { useLang, useT } from '../lib/LangContext.jsx'
import { formatWhen, resultLabel, statusBadge } from '../lib/format.js'
import { hrefFor } from '../lib/router.js'
import Link from './Link.jsx'
import ModelChip from './ModelChip.jsx'

function ResultBadge({ result }) {
  return (
    <span
      className="mono tnum"
      style={{
        fontWeight: 600,
        padding: '3px 10px',
        borderRadius: 6,
        background: 'var(--paper-2)',
        border: '1px solid var(--line)',
        fontSize: 13,
        flex: 'none',
      }}
    >
      {resultLabel(result)}
    </span>
  )
}

export default function GameCard({ game, catalog }) {
  const t = useT()
  const { lang } = useLang()
  const badge = statusBadge(game)
  const when = formatWhen(game.created_at, new Date(), lang)
  const white = catalog && catalog.find(game.white)
  const black = catalog && catalog.find(game.black)

  return (
    <Link href={hrefFor('game', { id: game.id })} className="rowcard">
      <div className="col" style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <div className="row gap-2" style={{ minWidth: 0 }}>
          <ModelChip name={game.white} provider={white && white.provider} size={22} />
          <span className="mono" style={{ color: 'var(--faint)', fontSize: 11 }}>
            vs
          </span>
          <ModelChip name={game.black} provider={black && black.provider} size={22} />
        </div>
        <div className="row gap-2" style={{ minWidth: 0 }}>
          <span className={badge.className} style={{ flex: 'none' }}>
            {badge.dot && <span className="dot" />}
            {t(badge.key)}
          </span>
          <span className="mono" style={{ color: 'var(--faint)', fontSize: 11.5 }}>
            {game.id}
          </span>
          <span style={{ color: 'var(--faint)', fontSize: 12, marginLeft: 'auto', flex: 'none' }}>
            {when ? t(when.key, when.params) : ''}
          </span>
        </div>
      </div>
      <ResultBadge result={game.result} />
    </Link>
  )
}
