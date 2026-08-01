/* Лента ходов парами (номер · белые · чёрные) — как в дизайне и в отчёте.
 * Текущий ход подсвечен; клик по ходу опционален (в live перемотки нет). */
import { pairMoves } from '../lib/fen.js'
import { classOf, glyphOf } from '../lib/report.js'

function Cell({ move, current, onSelect }) {
  if (!move) return <span className="mv-cell" />
  // цвет по классу хода из ★-анализа; в live классов ещё нет — цвет обычный
  const className =
    'mv-cell' + (current ? ' cur' : '') + (move.classification ? ' ' + classOf(move.classification) : '')
  const content = (
    <>
      {move.san}
      {glyphOf(move.classification) && <span className="glyph">{glyphOf(move.classification)}</span>}
    </>
  )
  if (!onSelect) return <span className={className}>{content}</span>
  return (
    <button type="button" className={className} onClick={() => onSelect(move.ply)}>
      {content}
    </button>
  )
}

export default function MoveList({ moves, currentPly = null, onSelect = null }) {
  const pairs = pairMoves(moves)
  return (
    <div className="moves scroll">
      {pairs.map((pair) => (
        <div className="mv-row" key={pair.number}>
          <span className="mv-num tnum">{pair.number}.</span>
          <Cell move={pair.white} current={pair.white && pair.white.ply === currentPly} onSelect={onSelect} />
          <Cell move={pair.black} current={pair.black && pair.black.ply === currentPly} onSelect={onSelect} />
        </div>
      ))}
    </div>
  )
}
