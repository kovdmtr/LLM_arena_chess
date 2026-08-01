import { describe, expect, it } from 'vitest'

import { createT } from './i18n.js'
import {
  formatAccuracy,
  formatPoints,
  formatScorePct,
  gameCount,
  groupByRound,
  toggleSelection,
  tournamentBlockedReason,
} from './tournament.js'

const A = { id: 'a', display_name: 'A', provider: 'openai', has_key: true }
const B = { id: 'b', display_name: 'B', provider: 'anthropic', has_key: true }
const NO_KEY = { id: 'x', display_name: 'X', provider: 'gemini', has_key: false }

describe('toggleSelection', () => {
  it('добавляет и убирает модель, сохраняя порядок', () => {
    expect(toggleSelection([], 'a')).toEqual(['a'])
    expect(toggleSelection(['a'], 'b')).toEqual(['a', 'b'])
    expect(toggleSelection(['a', 'b'], 'a')).toEqual(['b'])
  })
})

describe('tournamentBlockedReason', () => {
  const catalog = [A, B, NO_KEY]

  it('две модели с ключами — можно стартовать', () => {
    expect(tournamentBlockedReason(['a', 'b'], catalog)).toBeNull()
  })

  it('одна модель (или дубли) — мало, как и на бэкенде', () => {
    expect(tournamentBlockedReason(['a'], catalog)).toBe('error.tournamentTooFewModels')
    expect(tournamentBlockedReason(['a', 'a'], catalog)).toBe('error.tournamentTooFewModels')
  })

  it('модель без ключа блокирует старт', () => {
    expect(tournamentBlockedReason(['a', 'x'], catalog)).toBe('newTournament.blocked.noKey')
  })

  it('модель вне каталога блокирует старт', () => {
    expect(tournamentBlockedReason(['a', 'нет'], catalog)).toBe('newTournament.blocked.unknownModel')
  })

  it('каталог без пары доступных моделей объясняет причину', () => {
    expect(tournamentBlockedReason([], [A, NO_KEY])).toBe('newTournament.blocked.notEnoughModels')
  })

  it('все причины переводятся на оба языка', () => {
    const keys = [
      tournamentBlockedReason([], [A, NO_KEY]),
      tournamentBlockedReason(['a'], catalog),
      tournamentBlockedReason(['a', 'x'], catalog),
      tournamentBlockedReason(['a', 'нет'], catalog),
    ]
    for (const key of keys) {
      expect(createT('ru').has(key)).toBe(true)
      expect(createT('en').has(key)).toBe(true)
    }
  })
})

describe('gameCount', () => {
  it('круговой турнир: пары, два круга — вдвое больше', () => {
    expect(gameCount(2)).toBe(1)
    expect(gameCount(3)).toBe(3)
    expect(gameCount(4)).toBe(6)
    expect(gameCount(3, true)).toBe(6)
  })

  it('меньше двух участников — партий нет', () => {
    expect(gameCount(1)).toBe(0)
    expect(gameCount(0)).toBe(0)
  })
})

describe('groupByRound', () => {
  it('раскладывает расписание по турам в порядке возрастания', () => {
    const schedule = [
      { round: 2, white: 'a', black: 'b' },
      { round: 1, white: 'b', black: 'a' },
      { round: 2, white: 'c', black: 'a' },
    ]

    const rounds = groupByRound(schedule)

    expect(rounds.map((r) => r.round)).toEqual([1, 2])
    expect(rounds[1].games).toHaveLength(2)
  })

  it('пустое расписание — пустой список', () => {
    expect(groupByRound([])).toEqual([])
    expect(groupByRound()).toEqual([])
  })
})

describe('форматирование таблицы', () => {
  it('очки: половинки видны, целые не раздуты', () => {
    expect(formatPoints(1)).toBe('1')
    expect(formatPoints(1.5)).toBe('1.5')
    expect(formatPoints(0)).toBe('0')
  })

  it('доля очков и точность округляются, отсутствие — прочерк', () => {
    expect(formatScorePct(66.666)).toBe('67%')
    expect(formatScorePct(null)).toBe('—')
    expect(formatAccuracy(0.8214)).toBe('82%')
    expect(formatAccuracy(null)).toBe('—')
  })
})
