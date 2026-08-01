import { describe, expect, it } from 'vitest'

import { START_FEN } from './fen.js'
import { createT } from './i18n.js'
import {
  CLASSIFICATION_GLYPHS,
  accuracyPercent,
  buildFrames,
  clampFrame,
  classOf,
  formatEval,
  glyphOf,
} from './report.js'

const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1'
const AFTER_E5 = 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2'

const RECORD = {
  moves: [
    { ply: 1, side: 'white', san: 'e4', uci: 'e2e4', fen_before: START_FEN, fen_after: AFTER_E4 },
    { ply: 2, side: 'black', san: 'e5', uci: 'e7e5', fen_before: AFTER_E4, fen_after: AFTER_E5 },
  ],
}

describe('buildFrames', () => {
  it('нулевой кадр — стартовая позиция, дальше по кадру на полуход', () => {
    const frames = buildFrames(RECORD)

    expect(frames).toHaveLength(3)
    expect(frames[0]).toEqual({ index: 0, fen: START_FEN, lastMove: null, move: null })
    expect(frames[1].fen).toBe(AFTER_E4)
    expect(frames[1].lastMove).toBe('e2e4')
    expect(frames[2].move.san).toBe('e5')
  })

  it('индекс кадра совпадает с полуходом — клик по ходу ведёт в нужную позицию', () => {
    const frames = buildFrames(RECORD)
    for (const move of RECORD.moves) {
      expect(frames[move.ply].move).toBe(move)
    }
  })

  it('партия без ходов — один кадр со стартовой позицией', () => {
    expect(buildFrames({ moves: [] })).toHaveLength(1)
    expect(buildFrames(null)[0].fen).toBe(START_FEN)
  })
})

describe('глифы и цвета классов', () => {
  it('совпадают с бэкендом (arena.analysis.classify)', () => {
    expect(CLASSIFICATION_GLYPHS).toMatchObject({
      brilliant: '!!',
      good: '!',
      interesting: '!?',
      inaccuracy: '?!',
      mistake: '?',
      blunder: '??',
    })
  })

  it('normal/book и неизвестное — без глифа', () => {
    expect(glyphOf('normal')).toBe('')
    expect(glyphOf('book')).toBe('')
    expect(glyphOf(null)).toBe('')
    expect(glyphOf('новый-класс')).toBe('')
  })

  it('класс без разметки не красит ход', () => {
    expect(classOf('blunder')).toBe('g-blunder')
    expect(classOf(null)).toBe('')
  })

  it('у каждого класса есть перевод в обоих языках', () => {
    for (const name of Object.keys(CLASSIFICATION_GLYPHS)) {
      expect(createT('ru').has(`class.${name}`)).toBe(true)
      expect(createT('en').has(`class.${name}`)).toBe(true)
    }
  })
})

describe('formatEval', () => {
  it('сантипешки → пешки со знаком', () => {
    expect(formatEval(120)).toBe('+1.20')
    expect(formatEval(-35)).toBe('−0.35')
    expect(formatEval(0)).toBe('0.00')
  })

  it('без оценки — ничего не показываем', () => {
    expect(formatEval(null)).toBeNull()
    expect(formatEval(undefined)).toBeNull()
  })
})

describe('accuracyPercent', () => {
  it('доля → проценты', () => {
    expect(accuracyPercent({ accuracy: 0.8214 })).toBe(82)
    expect(accuracyPercent({ accuracy: 1 })).toBe(100)
  })

  it('без анализа — null (в панели будет прочерк)', () => {
    expect(accuracyPercent({ accuracy: null })).toBeNull()
    expect(accuracyPercent(null)).toBeNull()
  })
})

describe('clampFrame', () => {
  it('держит индекс в границах — клавиши на краях безопасны', () => {
    expect(clampFrame(-3, 5)).toBe(0)
    expect(clampFrame(9, 5)).toBe(4)
    expect(clampFrame(2, 5)).toBe(2)
  })

  it('пустой список кадров и мусор не роняют плеер', () => {
    expect(clampFrame(1, 0)).toBe(0)
    expect(clampFrame(NaN, 5)).toBe(0)
  })
})
