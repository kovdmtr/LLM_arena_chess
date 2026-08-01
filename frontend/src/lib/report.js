/* Разбор партии: кадры плеера и оформление ★-анализа. Чистый модуль, под тестами.
 *
 * Классы и глифы совпадают с бэкендом (`arena.analysis.classify`), иначе разбор
 * на сайте и в offline-отчёте разошёлся бы.
 */
import { START_FEN } from './fen.js'

/** Глиф класса хода; `normal`/`book`/неизвестное — без глифа (как на бэкенде). */
export const CLASSIFICATION_GLYPHS = {
  brilliant: '!!',
  good: '!',
  interesting: '!?',
  inaccuracy: '?!',
  mistake: '?',
  blunder: '??',
  normal: '',
  book: '',
}

export function glyphOf(classification) {
  return CLASSIFICATION_GLYPHS[classification] || ''
}

/** CSS-класс цвета для ленты ходов и бейджа. */
export function classOf(classification) {
  return classification ? `g-${classification}` : ''
}

/**
 * Кадры плеера: кадр 0 — стартовая позиция, дальше по одному на полуход.
 *
 * FEN берём из записи (`fen_before`/`fen_after`) — своей шахматной логики на
 * фронте нет, доска только отображает то, что посчитал бэкенд.
 */
export function buildFrames(record) {
  const moves = (record && record.moves) || []
  const start = moves.length ? moves[0].fen_before || START_FEN : START_FEN
  const frames = [{ index: 0, fen: start, lastMove: null, move: null }]
  moves.forEach((move, i) => {
    frames.push({
      index: i + 1,
      fen: move.fen_after,
      lastMove: move.uci,
      move,
    })
  })
  return frames
}

/** Оценка в сантипешках → «+1.20» / «−0.35» (POV белых, как в записи). */
export function formatEval(cp) {
  if (cp === null || cp === undefined) return null
  const pawns = cp / 100
  const sign = cp > 0 ? '+' : cp < 0 ? '−' : ''
  return `${sign}${Math.abs(pawns).toFixed(2)}`
}

/** Точность стороны в процентах или `null`, если анализа не было. */
export function accuracyPercent(playerAnalysis) {
  if (!playerAnalysis || playerAnalysis.accuracy === null || playerAnalysis.accuracy === undefined) {
    return null
  }
  return Math.round(playerAnalysis.accuracy * 100)
}

/** Индекс кадра по полуходу (для клика по ходу в ленте). */
export function frameOfPly(ply) {
  return ply
}

/** Ограничить индекс кадра диапазоном — защита от клавиш на краях. */
export function clampFrame(index, total) {
  if (!Number.isFinite(index)) return 0
  return Math.max(0, Math.min(index, Math.max(0, total - 1)))
}
