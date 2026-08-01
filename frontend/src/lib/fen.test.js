import { describe, expect, it } from 'vitest'

import { START_FEN, moveNumber, movePair, pairMoves, parseFen, squareName, squareOf } from './fen.js'

describe('parseFen', () => {
  it('раскладывает начальную позицию: board[rank][file], rank 0 — первая горизонталь', () => {
    const { board, turn, valid } = parseFen(START_FEN)

    expect(valid).toBe(true)
    expect(turn).toBe('w')
    expect(board[0][0]).toEqual({ type: 'r', color: 'w' }) // a1
    expect(board[0][4]).toEqual({ type: 'k', color: 'w' }) // e1
    expect(board[7][3]).toEqual({ type: 'q', color: 'b' }) // d8
    expect(board[1].every((cell) => cell.type === 'p' && cell.color === 'w')).toBe(true)
    expect(board[4].every((cell) => cell === null)).toBe(true)
  })

  it('считает пустые клетки и читает очередь хода', () => {
    const fen = 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 2'
    const { board, turn } = parseFen(fen)

    expect(turn).toBe('b')
    expect(board[3][4]).toEqual({ type: 'p', color: 'w' }) // e4
    expect(board[4][4]).toEqual({ type: 'p', color: 'b' }) // e5
    expect(board[2][4]).toBeNull()
  })

  it('битый FEN не роняет доску', () => {
    for (const bad of ['', 'мусор', 'rnbq/8/8 w', null]) {
      const { valid, board } = parseFen(bad)
      expect(valid).toBe(false)
      expect(board).toHaveLength(8)
      expect(board[0]).toHaveLength(8)
    }
  })
})

describe('координаты', () => {
  it('переводит имя клетки в индексы и обратно', () => {
    expect(squareOf('a1')).toEqual({ rank: 0, file: 0 })
    expect(squareOf('e4')).toEqual({ rank: 3, file: 4 })
    expect(squareOf('h8')).toEqual({ rank: 7, file: 7 })
    expect(squareName(3, 4)).toBe('e4')
    expect(squareName(0, 0)).toBe('a1')
  })

  it('мусор — null, а не исключение', () => {
    expect(squareOf('z9')).toBeNull()
    expect(squareOf('')).toBeNull()
    expect(squareOf(undefined)).toBeNull()
  })
})

describe('movePair', () => {
  it('разбирает UCI, включая превращение', () => {
    expect(movePair('e2e4')).toEqual({ from: 'e2', to: 'e4', promotion: null })
    expect(movePair('e7e8q')).toEqual({ from: 'e7', to: 'e8', promotion: 'q' })
    expect(movePair('E2E4')).toEqual({ from: 'e2', to: 'e4', promotion: null })
  })

  it('нелегальную запись отвергает — подсветка просто не рисуется', () => {
    expect(movePair('0000')).toBeNull()
    expect(movePair('e2')).toBeNull()
    expect(movePair(null)).toBeNull()
  })
})

describe('moveNumber', () => {
  it('пара полуходов — один ход', () => {
    expect(moveNumber(1)).toBe(1)
    expect(moveNumber(2)).toBe(1)
    expect(moveNumber(3)).toBe(2)
    expect(moveNumber(4)).toBe(2)
  })
})

describe('pairMoves', () => {
  const moves = [
    { ply: 1, side: 'white', san: 'e4' },
    { ply: 2, side: 'black', san: 'e5' },
    { ply: 3, side: 'white', san: 'Nf3' },
  ]

  it('складывает ходы в строки «номер · белые · чёрные»', () => {
    const pairs = pairMoves(moves)

    expect(pairs).toHaveLength(2)
    expect(pairs[0]).toEqual({ number: 1, white: moves[0], black: moves[1] })
    // незавершённая пара: чёрные ещё не сходили
    expect(pairs[1]).toEqual({ number: 2, white: moves[2], black: null })
  })

  it('пустой список — пустая лента', () => {
    expect(pairMoves([])).toEqual([])
    expect(pairMoves()).toEqual([])
  })
})
