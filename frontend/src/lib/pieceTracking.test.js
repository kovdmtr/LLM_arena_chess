import { describe, expect, it } from 'vitest'

import { START_FEN } from './fen.js'
import { occupiedSquares, squareOffset, trackPieces } from './pieceTracking.js'

const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1'
const AFTER_E4_E5 = 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2'

/** Счётчик id, как в компоненте доски. */
function minter(start = 100) {
  let next = start
  return () => {
    next += 1
    return next
  }
}

function track(prevIds, prevFen, nextFen, uci) {
  return trackPieces(prevIds, prevFen, nextFen, uci, minter(Object.keys(prevIds || {}).length + 100))
}

describe('occupiedSquares', () => {
  it('перечисляет занятые клетки начальной позиции', () => {
    const squares = occupiedSquares(START_FEN)

    expect(Object.keys(squares)).toHaveLength(32)
    expect(squares.e1).toEqual({ type: 'k', color: 'w' })
    expect(squares.d8).toEqual({ type: 'q', color: 'b' })
    expect(squares.e4).toBeUndefined()
  })
})

describe('trackPieces', () => {
  it('первая позиция: всем фигурам выдаются новые id', () => {
    const { ids, animated } = trackPieces(null, null, START_FEN, null, minter())

    expect(Object.keys(ids)).toHaveLength(32)
    expect(animated).toBe(false)
  })

  it('сыгравшая фигура сохраняет id — иначе браузер не сдвинет её, а перерисует', () => {
    const start = trackPieces(null, null, START_FEN, null, minter())
    const after = track(start.ids, START_FEN, AFTER_E4, 'e2e4')

    expect(after.ids.e4).toBe(start.ids.e2)
    expect(after.ids.e2).toBeUndefined()
    expect(after.animated).toBe(true)
    // остальные фигуры не «переехали»
    expect(after.ids.d1).toBe(start.ids.d1)
    expect(Object.keys(after.ids)).toHaveLength(32)
  })

  it('ход соперника не трогает id уже стоящих фигур', () => {
    const start = trackPieces(null, null, START_FEN, null, minter())
    const white = track(start.ids, START_FEN, AFTER_E4, 'e2e4')
    const black = track(white.ids, AFTER_E4, AFTER_E4_E5, 'e7e5')

    expect(black.ids.e5).toBe(start.ids.e7)
    expect(black.ids.e4).toBe(start.ids.e2)
  })

  it('взятие убирает id съеденной фигуры, а бьющая переезжает на её клетку', () => {
    const before = 'rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2'
    const after = 'rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2'
    const start = trackPieces(null, null, before, null, minter())

    const result = track(start.ids, before, after, 'e4d5')

    expect(result.ids.d5).toBe(start.ids.e4)
    expect(result.ids.d5).not.toBe(start.ids.d5) // съеденная пешка исчезла
    expect(Object.keys(result.ids)).toHaveLength(Object.keys(start.ids).length - 1)
  })

  it('рокировка двигает и короля, и ладью', () => {
    const before = 'rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4'
    const after = 'rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 5 4'
    const start = trackPieces(null, null, before, null, minter())

    const result = track(start.ids, before, after, 'e1g1')

    expect(result.ids.g1).toBe(start.ids.e1) // король
    expect(result.ids.f1).toBe(start.ids.h1) // ладья
    expect(result.ids.e1).toBeUndefined()
    expect(result.ids.h1).toBeUndefined()
  })

  it('взятие на проходе убирает пешку с клетки, которой нет в ходе', () => {
    const before = 'rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 4'
    const after = 'rnbqkbnr/ppp1p1pp/5P2/3p4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 4'
    const start = trackPieces(null, null, before, null, minter())

    const result = track(start.ids, before, after, 'e5f6')

    expect(result.ids.f6).toBe(start.ids.e5)
    expect(result.ids.f5).toBeUndefined() // снятая на проходе пешка
    expect(Object.keys(result.ids)).toHaveLength(Object.keys(start.ids).length - 1)
  })

  it('перемотка без хода раздаёт id заново — лучше без анимации, чем с ложной', () => {
    const start = trackPieces(null, null, START_FEN, null, minter())

    const jumped = track(start.ids, START_FEN, AFTER_E4_E5, null)

    expect(jumped.animated).toBe(false)
    expect(jumped.ids.e4).not.toBe(start.ids.e2)
  })
})

describe('squareOffset', () => {
  it('шаг равен 100% — фигура ровно в клетку', () => {
    expect(squareOffset('a8')).toEqual({ x: 0, y: 0 })
    expect(squareOffset('c1')).toEqual({ x: 200, y: 700 })
    expect(squareOffset('h1')).toEqual({ x: 700, y: 700 })
  })

  it('разворот доски зеркалит обе оси', () => {
    expect(squareOffset('a8', true)).toEqual({ x: 700, y: 700 })
    expect(squareOffset('h1', true)).toEqual({ x: 0, y: 0 })
  })

  it('мусорная клетка не роняет доску', () => {
    expect(squareOffset('z9')).toBeNull()
  })
})
