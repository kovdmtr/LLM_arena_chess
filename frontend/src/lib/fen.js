/* Разбор FEN и координат — всё, что нужно доске. Чистый модуль, под тестами.
 *
 * Доска рисуется на клиенте: бэкенд шлёт FEN в каждом кадре WS и хранит его в
 * `MoveRecord`, а готовый серверный SVG (`svg` в кадре) мы не используем — он
 * не знает про тему и палитру нового дизайна.
 *
 * Представление: board[rank][file], rank 0 — первая горизонталь (белые),
 * file 0 — вертикаль «a». Фигура — { type: 'k'|'q'|'r'|'b'|'n'|'p', color: 'w'|'b' }.
 */

export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

const PIECE_TYPES = new Set(['k', 'q', 'r', 'b', 'n', 'p'])

function emptyBoard() {
  return Array.from({ length: 8 }, () => Array(8).fill(null))
}

/**
 * FEN → `{ board, turn, valid }`.
 *
 * Битый FEN не роняет экран: возвращается пустая доска с `valid: false`,
 * а вызывающий сам решает, что показать.
 */
export function parseFen(fen) {
  const board = emptyBoard()
  const [placement, turn = 'w'] = String(fen || '').trim().split(/\s+/)
  if (!placement) return { board, turn: 'w', valid: false }

  const rows = placement.split('/')
  if (rows.length !== 8) return { board, turn: 'w', valid: false }

  rows.forEach((row, index) => {
    const rank = 7 - index // FEN идёт с 8-й горизонтали вниз
    let file = 0
    for (const char of row) {
      if (/\d/.test(char)) {
        file += Number(char)
        continue
      }
      const type = char.toLowerCase()
      if (!PIECE_TYPES.has(type) || file > 7) return
      board[rank][file] = { type, color: char === type ? 'b' : 'w' }
      file += 1
    }
  })

  return { board, turn: turn === 'b' ? 'b' : 'w', valid: true }
}

/** 'e4' → `{ rank: 3, file: 4 }`; мусор → null. */
export function squareOf(name) {
  const text = String(name || '')
  if (!/^[a-h][1-8]$/.test(text)) return null
  return { file: text.charCodeAt(0) - 97, rank: text.charCodeAt(1) - 49 }
}

/** `{rank, file}` → 'e4'. */
export function squareName(rank, file) {
  return String.fromCharCode(97 + file) + (rank + 1)
}

/** UCI-ход ('e2e4', 'e7e8q') → `{ from, to, promotion }`; мусор → null. */
export function movePair(uci) {
  const text = String(uci || '').toLowerCase()
  if (!/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(text)) return null
  return {
    from: text.slice(0, 2),
    to: text.slice(2, 4),
    promotion: text.slice(4) || null,
  }
}

/** Номер хода по полуходу: 1-й и 2-й полуходы — это ход №1. */
export function moveNumber(ply) {
  return Math.floor((ply + 1) / 2)
}

/** Ходы парами `{ number, white, black }` — как в дизайне списка ходов. */
export function pairMoves(moves = []) {
  const pairs = []
  for (const move of moves) {
    const number = moveNumber(move.ply)
    let pair = pairs[pairs.length - 1]
    if (!pair || pair.number !== number) {
      pair = { number, white: null, black: null }
      pairs.push(pair)
    }
    pair[move.side === 'black' ? 'black' : 'white'] = move
  }
  return pairs
}
