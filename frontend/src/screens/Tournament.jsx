/* Турнир: таблица результатов + расписание со ссылками на партии.
 *
 * Пока турнир идёт, данные перечитываются по таймеру — таблица частичная
 * (по сыгранным партиям), как и в прежнем SSR-экране.
 */
import { useEffect } from 'react'

import Link from '../components/Link.jsx'
import ModelChip from '../components/ModelChip.jsx'
import { ErrorBanner, Skeletons } from '../components/States.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { progressLabel, resultLabel } from '../lib/format.js'
import { indexModels } from '../lib/models.js'
import { hrefFor } from '../lib/router.js'
import { formatAccuracy, formatPoints, formatScorePct, groupByRound } from '../lib/tournament.js'
import { useAsync } from '../lib/useAsync.js'

const POLL_MS = 4000

function Standings({ standings, catalog, t }) {
  const rows = (standings && standings.models) || []
  if (!rows.length) {
    return (
      <p style={{ padding: '14px 16px', margin: 0, color: 'var(--muted)', fontSize: 14 }}>
        {t('tournament.noGamesYet')}
      </p>
    )
  }
  return (
    <div className="scroll">
      <table className="tbl">
        <thead>
          <tr>
            <th>#</th>
            <th>{t('tournament.model')}</th>
            <th className="num">{t('tournament.games')}</th>
            <th className="num">{t('tournament.wins')}</th>
            <th className="num">{t('tournament.draws')}</th>
            <th className="num">{t('tournament.losses')}</th>
            <th className="num">{t('tournament.points')}</th>
            <th className="num">{t('tournament.score')}</th>
            <th className="num">{t('tournament.accuracy')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const model = catalog.find(row.model_id)
            return (
              <tr key={row.model_id} className={i === 0 ? 'me' : ''}>
                <td style={{ color: 'var(--faint)', fontWeight: 700 }}>{i + 1}</td>
                <td>
                  <ModelChip name={row.display_name} provider={model && model.provider} size={24} />
                </td>
                <td className="num mono">{row.games}</td>
                <td className="num mono">{row.wins}</td>
                <td className="num mono">{row.draws}</td>
                <td className="num mono">{row.losses}</td>
                <td className="num mono" style={{ fontWeight: 700 }}>{formatPoints(row.points)}</td>
                <td className="num mono">{formatScorePct(row.score_pct)}</td>
                <td className="num mono">{formatAccuracy(row.avg_accuracy)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Schedule({ schedule, t }) {
  const rounds = groupByRound(schedule)
  return (
    <div className="col">
      {rounds.map(({ round, games }) => (
        <div key={round}>
          <div className="eyebrow" style={{ padding: '10px 16px', background: 'var(--paper-2)' }}>
            {t('tournament.round', { round })}
          </div>
          {games.map((game, i) => {
            const label = `${game.white_name} — ${game.black_name}`
            const result = game.result ? resultLabel(game.result) : '·'
            const body = (
              <>
                <span style={{ flex: 1, minWidth: 0 }}>{label}</span>
                <span className="mono tnum" style={{ flex: 'none', color: 'var(--muted)' }}>{result}</span>
              </>
            )
            const style = {
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '11px 16px',
              borderBottom: '1px solid var(--line)',
              fontSize: 14,
            }
            return game.game_id ? (
              <Link
                key={`${round}-${i}`}
                href={hrefFor('game', { id: game.game_id })}
                style={{ ...style, textDecoration: 'none' }}
              >
                {body}
              </Link>
            ) : (
              <div key={`${round}-${i}`} style={{ ...style, color: 'var(--muted)' }}>
                {body}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

export default function Tournament({ id }) {
  const t = useT()
  const tournament = useAsync(() => api.tournament(id), [id])
  const models = useAsync(() => api.models(), [])
  const catalog = indexModels(models.data || [])
  const data = tournament.data
  const live = Boolean(data && data.live)
  const reload = tournament.reload

  // идущий турнир обновляем по таймеру: прогресс и таблица растут по мере партий
  useEffect(() => {
    if (!live) return undefined
    const timer = setInterval(reload, POLL_MS)
    return () => clearInterval(timer)
  }, [live, reload])

  if (tournament.loading && !data) {
    return (
      <div className="wrap" style={{ paddingTop: 40, paddingBottom: 64 }}>
        <Skeletons count={2} height={160} />
      </div>
    )
  }

  if (tournament.error) {
    return (
      <div className="wrap" style={{ paddingTop: 40, paddingBottom: 64 }}>
        <ErrorBanner error={tournament.error} />
        <Link href={hrefFor('tournaments')} className="btn btn-ghost" style={{ marginTop: 16 }}>
          {t('tournament.toList')}
        </Link>
      </div>
    )
  }

  return (
    <div className="wrap fade-in" style={{ paddingTop: 28, paddingBottom: 56 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <span className="eyebrow">{t('tournaments.eyebrow')}</span>
          <h1 style={{ fontSize: 30, margin: '10px 0 0' }}>
            {data.participants.map((p) => p.display_name).join(' · ')}
          </h1>
          <div className="row gap-2" style={{ marginTop: 10, flexWrap: 'wrap' }}>
            <span className={'badge' + (live ? ' badge-live' : ' badge-done')}>
              {live && <span className="dot" />}
              {live ? t('status.live') : t('status.finished')}
            </span>
            <span className="mono tnum" style={{ fontSize: 12.5, color: 'var(--muted)' }}>
              {progressLabel(data.played, data.total)}
            </span>
            {data.double && <span className="badge">{t('tournaments.double')}</span>}
          </div>
        </div>
        <span className="mono" style={{ fontSize: 12, color: 'var(--faint)' }}>{data.id}</span>
      </div>

      {data.status === 'error' && (
        <div className="banner banner-error" role="alert" style={{ marginTop: 18 }}>
          <span>⚠</span>
          <span>{data.error || t('tournament.failed')}</span>
        </div>
      )}

      <div className="row gap-6" style={{ alignItems: 'flex-start', marginTop: 20, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: '1 1 460px', minWidth: 320, overflow: 'hidden' }}>
          <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            {t('tournament.standings')}
          </div>
          <Standings standings={data.standings} catalog={catalog} t={t} />
        </div>

        <div className="card" style={{ flex: '1 1 320px', minWidth: 280, overflow: 'hidden' }}>
          <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            {t('tournament.schedule')}
          </div>
          <Schedule schedule={data.schedule} t={t} />
        </div>
      </div>
    </div>
  )
}
