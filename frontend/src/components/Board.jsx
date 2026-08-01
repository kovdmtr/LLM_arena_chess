/* Доска: рисуется из FEN на клиенте (см. lib/fen.js).
 *
 * Фигуры — юникодные глифы, а не картинки: они наследуют цвет и тень от темы,
 * не требуют ассетов и одинаково работают в live и в отчёте. Заливка задаётся
 * цветом текста, контур — обводкой (CSS), поэтому белые видны на светлой клетке.
 */
import { movePair, parseFen, squareOf } from '../lib/fen.js'

const GLYPHS = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' }

export default function Board({ fen, lastMove, flip = false, coords = true }) {
  const { board } = parseFen(fen)
  const move = movePair(lastMove)
  const highlighted = [move && move.from, move && move.to]
    .filter(Boolean)
    .map(squareOf)
    .filter(Boolean)

  const ranks = flip ? [0, 1, 2, 3, 4, 5, 6, 7] : [7, 6, 5, 4, 3, 2, 1, 0]
  const files = flip ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7]
  const isHighlighted = (rank, file) =>
    highlighted.some((square) => square.rank === rank && square.file === file)

  return (
    <div className="board">
      <div className="board-grid">
        {ranks.map((rank) =>
          files.map((file) => {
            const piece = board[rank][file]
            const dark = (rank + file) % 2 === 0
            return (
              <div
                key={`${rank}-${file}`}
                className={
                  'sq ' + (dark ? 'dark' : 'light') + (isHighlighted(rank, file) ? ' hl' : '')
                }
              >
                {coords && file === files[0] && <span className="coord rank">{rank + 1}</span>}
                {coords && rank === ranks[7] && (
                  <span className="coord file">{String.fromCharCode(97 + file)}</span>
                )}
                {piece && (
                  <span className={'pc pc-' + piece.color} aria-hidden="true">
                    {GLYPHS[piece.type]}
                  </span>
                )}
              </div>
            )
          }),
        )}
      </div>
    </div>
  )
}
