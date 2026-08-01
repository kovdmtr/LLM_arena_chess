/* Доска: клетки из FEN + слой фигур поверх них.
 *
 * Два слоя вместо «фигура внутри клетки» дают сразу две вещи:
 *   — подсветка последнего хода красит только поле, фигура остаётся чистой;
 *   — фигура — отдельный элемент со стабильным id (см. lib/pieceTracking.js),
 *     поэтому смена позиции анимируется CSS-переходом, а не скачком.
 *
 * Сами фигуры — SVG с бэкенда (`GET /api/pieces`, python-chess): тот же
 * комплект, что в скачиваемом отчёте. Пока комплект не приехал, доска рисуется
 * без фигур — клетки и подсветка уже на месте.
 */
import { useRef } from 'react'

import { movePair, squareName } from '../lib/fen.js'
import { occupiedSquares, squareOffset, trackPieces } from '../lib/pieceTracking.js'
import { usePieces } from '../lib/usePieces.js'

const SYMBOLS = {
  w: { k: 'K', q: 'Q', r: 'R', b: 'B', n: 'N', p: 'P' },
  b: { k: 'k', q: 'q', r: 'r', b: 'b', n: 'n', p: 'p' },
}

export default function Board({ fen, lastMove, flip = false, coords = true }) {
  const pieces = usePieces()
  const tracker = useRef({ fen: null, ids: {}, next: 1 })

  const squares = occupiedSquares(fen)
  const previous = tracker.current
  if (previous.fen !== fen) {
    const mint = () => {
      previous.next += 1
      return previous.next
    }
    const { ids } = trackPieces(previous.ids, previous.fen, fen, lastMove, mint)
    tracker.current = { fen, ids, next: previous.next }
  }
  const ids = tracker.current.ids

  const move = movePair(lastMove)
  const highlighted = [move && move.from, move && move.to].filter(Boolean)

  const ranks = flip ? [0, 1, 2, 3, 4, 5, 6, 7] : [7, 6, 5, 4, 3, 2, 1, 0]
  const files = flip ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7]

  return (
    <div className="board">
      <div className="board-grid">
        {ranks.map((rank) =>
          files.map((file) => {
            const name = squareName(rank, file)
            const dark = (rank + file) % 2 === 0
            return (
              <div
                key={name}
                className={'sq ' + (dark ? 'dark' : 'light') + (highlighted.includes(name) ? ' hl' : '')}
              >
                {coords && file === files[0] && <span className="coord rank">{rank + 1}</span>}
                {coords && rank === ranks[7] && (
                  <span className="coord file">{String.fromCharCode(97 + file)}</span>
                )}
              </div>
            )
          }),
        )}
      </div>

      <div className="board-pieces">
        {Object.entries(squares).map(([square, piece]) => {
          const offset = squareOffset(square, flip)
          const symbol = SYMBOLS[piece.color][piece.type]
          const svg = pieces && pieces[symbol]
          if (!offset || !svg) return null
          return (
            <div
              key={ids[square]}
              className="pc"
              style={{ transform: `translate(${offset.x}%, ${offset.y}%)` }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          )
        })}
      </div>
    </div>
  )
}
