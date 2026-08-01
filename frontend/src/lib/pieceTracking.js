/* Сопоставление фигур между двумя позициями — основа плавного хода.
 *
 * Доска перерисовывается по FEN, но браузер должен понимать, что фигура на новой
 * клетке — та же самая, что была на старой: только тогда CSS-переход сдвинет её,
 * а не «перерисует» скачком. Поэтому каждой фигуре присваивается стабильный id,
 * который переезжает с клетки на клетку по сыгранному ходу.
 *
 * Чистый модуль: никакой шахматной логики, только перенос идентификаторов по
 * уже сыгранному ходу (сами позиции считает бэкенд).
 */
import { movePair, parseFen, squareName, squareOf } from './fen.js'

/** Все занятые клетки позиции: `{ [square]: {type, color} }`. */
export function occupiedSquares(fen) {
  const { board } = parseFen(fen)
  const squares = {}
  for (let rank = 0; rank < 8; rank += 1) {
    for (let file = 0; file < 8; file += 1) {
      const piece = board[rank][file]
      if (piece) squares[squareName(rank, file)] = piece
    }
  }
  return squares
}

/** Ладейный «довесок» рокировки: король пошёл через две вертикали. */
function castlingRookMove(from, to, piece) {
  if (!piece || piece.type !== 'k') return null
  const start = squareOf(from)
  const end = squareOf(to)
  if (!start || !end || Math.abs(end.file - start.file) !== 2) return null
  const rank = start.rank
  return end.file === 6
    ? { from: squareName(rank, 7), to: squareName(rank, 5) } // короткая
    : { from: squareName(rank, 0), to: squareName(rank, 3) } // длинная
}

/**
 * Перенести id фигур на новую позицию.
 *
 * `previous` — карта `{square: id}` для прошлой позиции, `uci` — сыгранный ход.
 * Возвращает `{ ids, moved }`: карту для новой позиции и признак того, что
 * сопоставление удалось (при перемотке или рассинхроне id раздаются заново —
 * тогда анимации не будет, что честнее «телепортации» чужих фигур).
 */
export function trackPieces(previousIds, previousFen, nextFen, uci, mint) {
  const next = occupiedSquares(nextFen)
  const move = movePair(uci)
  const ids = {}
  let carried = {}

  if (move && previousIds && previousFen) {
    const before = occupiedSquares(previousFen)
    const mover = before[move.from]
    carried = { ...previousIds }
    delete carried[move.to] // взятие: фигура соперника уходит с доски
    if (carried[move.from] !== undefined) {
      carried[move.to] = carried[move.from]
      delete carried[move.from]
    }
    const rook = castlingRookMove(move.from, move.to, mover)
    if (rook && carried[rook.from] !== undefined) {
      carried[rook.to] = carried[rook.from]
      delete carried[rook.from]
    }
    // взятие на проходе: пешка исчезает с клетки, которой нет в ходе
    for (const square of Object.keys(carried)) {
      if (!next[square]) delete carried[square]
    }
  }

  let matched = 0
  for (const square of Object.keys(next)) {
    if (carried[square] !== undefined) {
      ids[square] = carried[square]
      matched += 1
    } else {
      ids[square] = mint()
    }
  }

  return { ids, animated: matched > 0 }
}

/**
 * Смещение клетки для `transform: translate(x%, y%)` фигуры.
 *
 * Проценты в `translate` считаются от размера самого элемента, а фигура — ровно
 * одна клетка, поэтому шаг равен 100%: клетка `c1` → `translate(200%, 700%)`.
 */
export function squareOffset(square, flip = false) {
  const position = squareOf(square)
  if (!position) return null
  const file = flip ? 7 - position.file : position.file
  const rank = flip ? position.rank : 7 - position.rank
  return { x: file * 100, y: rank * 100 }
}
