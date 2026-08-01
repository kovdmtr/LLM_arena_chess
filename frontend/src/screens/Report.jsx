/* Разбор завершённой партии: плеер + ★-анализ + скачивание PGN.
 *
 * Паритет с прежним self-contained отчётом (docs/FRONTEND.md §6): перемотка
 * ◀/▶ + слайдер + клик по ходу + клавиши ←/→, лента ходов парами с цветом по
 * классу, панель «Мысли модели»/«План», точность и счётчики ошибок по сторонам.
 */
import { useEffect, useMemo, useState } from 'react'

import Board from '../components/Board.jsx'
import Link from '../components/Link.jsx'
import ModelChip from '../components/ModelChip.jsx'
import MoveList from '../components/MoveList.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { moveNumber } from '../lib/fen.js'
import { resultLabel } from '../lib/format.js'
import {
  accuracyPercent,
  buildFrames,
  clampFrame,
  classOf,
  formatEval,
  glyphOf,
} from '../lib/report.js'
import { hrefFor } from '../lib/router.js'

function SideSummary({ label, player, stats, t }) {
  const accuracy = accuracyPercent(stats)
  return (
    <div className="card col gap-2" style={{ padding: 16, flex: '1 1 220px' }}>
      <span className="eyebrow">{label}</span>
      <ModelChip name={player.display_name} provider={player.provider} size={26} sub />
      <div className="row gap-4" style={{ marginTop: 6, flexWrap: 'wrap' }}>
        <div className="col">
          <span className="serif" style={{ fontSize: 26, fontWeight: 700 }}>
            {accuracy === null ? '—' : `${accuracy}%`}
          </span>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>{t('report.accuracy')}</span>
        </div>
        {stats && (
          <div className="col gap-2" style={{ fontSize: 13, color: 'var(--ink-2)' }}>
            <span className="g-blunder">
              {t('report.blunders', { count: stats.blunders || 0 })}
            </span>
            <span className="g-mistake">
              {t('report.mistakes', { count: stats.mistakes || 0 })}
            </span>
            <span className="g-inaccuracy">
              {t('report.inaccuracies', { count: stats.inaccuracies || 0 })}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Report({ record }) {
  const t = useT()
  const frames = useMemo(() => buildFrames(record), [record])
  const [index, setIndex] = useState(frames.length - 1)
  const frame = frames[clampFrame(index, frames.length)]
  const move = frame.move
  const analysis = record.analysis
  const players = record.players

  const go = (next) => setIndex((current) => clampFrame(next, frames.length) || 0)

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'ArrowLeft') go(index - 1)
      else if (event.key === 'ArrowRight') go(index + 1)
      else return
      event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [index, frames.length]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="wrap fade-in" style={{ paddingTop: 28, paddingBottom: 56 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <span className="eyebrow">{t('report.eyebrow')}</span>
          <h1 style={{ fontSize: 30, margin: '10px 0 0' }}>
            {players.white.display_name} — {players.black.display_name}
          </h1>
          <p style={{ margin: '10px 0 0', color: 'var(--muted)' }}>
            {t('report.result', { result: resultLabel(record.result) })}
            {record.termination ? ` · ${record.termination}` : ''}
          </p>
        </div>
        <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
          <a className="btn btn-ghost btn-sm" href={api.pgnUrl(record.id)}>
            {t('report.downloadPgn')}
          </a>
          <Link href={hrefFor('archive')} className="btn btn-quiet btn-sm">
            {t('report.toArchive')}
          </Link>
        </div>
      </div>

      <div className="row gap-6" style={{ alignItems: 'flex-start', marginTop: 20, flexWrap: 'wrap' }}>
        <div className="col gap-3" style={{ flex: '1 1 420px', minWidth: 300, maxWidth: 560 }}>
          <Board fen={frame.fen} lastMove={frame.lastMove} />

          <div className="row gap-3" style={{ alignItems: 'center' }}>
            <button
              className="icon-btn"
              style={{ borderRadius: 999 }}
              onClick={() => go(index - 1)}
              disabled={index <= 0}
              aria-label={t('report.prev')}
              title={t('report.prev')}
            >
              ◀
            </button>
            <input
              className="slider"
              type="range"
              min={0}
              max={frames.length - 1}
              value={frame.index}
              onChange={(event) => go(Number(event.target.value))}
              aria-label={t('report.slider')}
            />
            <button
              className="icon-btn"
              style={{ borderRadius: 999 }}
              onClick={() => go(index + 1)}
              disabled={index >= frames.length - 1}
              aria-label={t('report.next')}
              title={t('report.next')}
            >
              ▶
            </button>
            <span className="mono tnum" style={{ fontSize: 12.5, color: 'var(--muted)', flex: 'none' }}>
              {frame.index} / {frames.length - 1}
            </span>
          </div>
        </div>

        <div className="col gap-4" style={{ flex: '1 1 320px', minWidth: 280 }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
              {t('report.moves')}
            </div>
            <div style={{ maxHeight: 240, overflow: 'auto' }}>
              <MoveList
                moves={record.moves}
                currentPly={move ? move.ply : null}
                onSelect={(ply) => go(ply)}
              />
            </div>
          </div>

          <div className="card col gap-3" style={{ padding: 16 }}>
            {move ? (
              <>
                <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
                  <span className="mono" style={{ fontWeight: 700 }}>
                    {moveNumber(move.ply)}. {move.san}
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--muted)' }}>
                    {players[move.side].display_name}
                  </span>
                  {move.classification && (
                    <span className={'badge ' + classOf(move.classification)}>
                      {t(`class.${move.classification}`)} {glyphOf(move.classification)}
                    </span>
                  )}
                  {formatEval(move.engine_eval_cp) && (
                    <span className="mono tnum" style={{ fontSize: 12.5, color: 'var(--muted)' }}>
                      {formatEval(move.engine_eval_cp)}
                    </span>
                  )}
                </div>

                <div className="block">
                  <span className="block-label">{t('report.thoughts')}</span>
                  <p style={{ margin: 0 }}>{move.reasoning || t('live.noReasoning')}</p>
                </div>

                {move.strategy && (
                  <div className="block block-plan">
                    <span className="block-label">{t('report.plan')}</span>
                    <p style={{ margin: 0 }}>{move.strategy}</p>
                  </div>
                )}

                {move.hint && (
                  <p className="hint" style={{ margin: 0 }}>
                    {t('report.hint', { move: move.hint.best_move })}
                  </p>
                )}
              </>
            ) : (
              <p style={{ margin: 0, color: 'var(--muted)', fontSize: 14 }}>{t('report.startPosition')}</p>
            )}
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: 22, margin: '32px 0 14px' }}>{t('report.analysis')}</h2>
      {analysis ? (
        <div className="row gap-4" style={{ alignItems: 'stretch', flexWrap: 'wrap' }}>
          <SideSummary label={t('newGame.whiteShort')} player={players.white} stats={analysis.white} t={t} />
          <SideSummary label={t('newGame.blackShort')} player={players.black} stats={analysis.black} t={t} />
        </div>
      ) : (
        <p style={{ color: 'var(--muted)', marginTop: 0 }}>{t('report.noAnalysis')}</p>
      )}
    </div>
  )
}
