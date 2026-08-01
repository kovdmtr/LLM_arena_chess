/* Живая партия: доска слева, ходы и мысли модели справа (DESIGN_BRIEF §7.3).
 *
 * Данные идут по WebSocket; перезагрузка страницы не «убивает» просмотр —
 * сервер переигрывает накопленные кадры с начала партии.
 */
import Board from '../components/Board.jsx'
import MoveList from '../components/MoveList.jsx'
import ModelChip from '../components/ModelChip.jsx'
import { useT } from '../lib/LangContext.jsx'
import { moveNumber } from '../lib/fen.js'
import { LIVE_ERROR, LIVE_FINISHED, hintForPly, lastMoveOf } from '../lib/live.js'
import { resultLabel } from '../lib/format.js'
import { useLiveGame } from '../lib/useLiveGame.js'

function Side({ player, label, thinking }) {
  return (
    <div className="row gap-2" style={{ justifyContent: 'space-between', minWidth: 0 }}>
      <ModelChip name={player.display_name} provider={player.provider} size={24} />
      <span className="mono" style={{ fontSize: 11, color: 'var(--muted)', flex: 'none' }}>
        {thinking ? <span className="badge badge-live"><span className="dot" />{label}</span> : label}
      </span>
    </div>
  )
}

export default function LiveGame({ id, record, onFinished }) {
  const t = useT()
  const state = useLiveGame(id, record)
  const last = lastMoveOf(state)
  const hint = last ? hintForPly(state, last.ply) : null
  const players = record.players

  return (
    <div className="wrap fade-in" style={{ paddingTop: 28, paddingBottom: 56 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <span className="eyebrow">{t('live.eyebrow')}</span>
          <h1 style={{ fontSize: 30, margin: '10px 0 0' }}>
            {players.white.display_name} — {players.black.display_name}
          </h1>
        </div>
        <span className="mono" style={{ fontSize: 12, color: 'var(--faint)' }}>{id}</span>
      </div>

      {state.status === LIVE_ERROR && (
        <div className="banner banner-error" role="alert" style={{ marginTop: 18 }}>
          <span>⚠</span>
          <span>{state.errorKey ? t(state.errorKey) : state.error || t('live.failed')}</span>
        </div>
      )}

      {state.status === LIVE_FINISHED && (
        <div className="banner" style={{ marginTop: 18, justifyContent: 'space-between' }}>
          <span>
            {t('live.finished', { result: resultLabel(state.result) })}
            {state.termination ? ` · ${state.termination}` : ''}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onFinished}>
            {t('live.openReport')}
          </button>
        </div>
      )}

      <div className="row gap-6" style={{ alignItems: 'flex-start', marginTop: 20, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 420px', minWidth: 300, maxWidth: 560 }}>
          <Board fen={state.fen} lastMove={state.lastMove} />
        </div>

        <div className="col gap-4" style={{ flex: '1 1 320px', minWidth: 280 }}>
          <div className="card col gap-2" style={{ padding: 14 }}>
            <Side
              player={players.white}
              label={t('side.white')}
              thinking={state.thinkingSide === 'white'}
            />
            <Side
              player={players.black}
              label={t('side.black')}
              thinking={state.thinkingSide === 'black'}
            />
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
              {t('live.moves')}
            </div>
            <div style={{ maxHeight: 260, overflow: 'auto' }}>
              {state.moves.length ? (
                <MoveList moves={state.moves} currentPly={last ? last.ply : null} />
              ) : (
                <p style={{ padding: '14px 16px', margin: 0, color: 'var(--muted)', fontSize: 14 }}>
                  {t('live.waitingFirstMove')}
                </p>
              )}
            </div>
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
              {t('live.thoughts')}
            </div>
            <div style={{ padding: '12px 16px' }}>
              {last ? (
                <>
                  <div className="row gap-2" style={{ marginBottom: 8, flexWrap: 'wrap' }}>
                    <span className="mono" style={{ fontWeight: 700 }}>
                      {moveNumber(last.ply)}. {last.san}
                    </span>
                    <span style={{ fontSize: 13, color: 'var(--muted)' }}>
                      {players[last.side].display_name}
                    </span>
                    {hint && <span className="badge badge-green">{t('live.hintUsed')}</span>}
                  </div>
                  <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.55, color: 'var(--ink-2)' }}>
                    {last.reasoning || t('live.noReasoning')}
                  </p>
                </>
              ) : (
                <p style={{ margin: 0, color: 'var(--muted)', fontSize: 14 }}>{t('live.waitingThoughts')}</p>
              )}
            </div>
          </div>

          {state.illegal && (
            <div className="banner" role="status">
              <span>↺</span>
              <span>{t('live.illegalAttempt', { attempt: state.illegal.attempt })}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
