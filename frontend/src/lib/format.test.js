import { describe, expect, it } from 'vitest'

import { formatWhen, plural, progressLabel, resultLabel, statusBadge, winnerOf } from './format.js'

describe('resultLabel', () => {
  it('переводит результат бэкенда в шахматную запись', () => {
    expect(resultLabel('1-0')).toBe('1–0')
    expect(resultLabel('0-1')).toBe('0–1')
    expect(resultLabel('1/2-1/2')).toBe('½–½')
  })

  it('незавершённая партия — прочерк', () => {
    expect(resultLabel('*')).toBe('—')
    expect(resultLabel(undefined)).toBe('—')
  })
})

describe('winnerOf', () => {
  it('определяет сторону-победителя и ничью', () => {
    expect(winnerOf('1-0')).toBe('white')
    expect(winnerOf('0-1')).toBe('black')
    expect(winnerOf('1/2-1/2')).toBe('draw')
    expect(winnerOf('*')).toBeNull()
  })
})

describe('statusBadge', () => {
  it('идущая партия помечается «в эфире» с точкой', () => {
    const badge = statusBadge({ live: true, status: 'running', result: '*' })
    expect(badge.text).toBe('В ЭФИРЕ')
    expect(badge.className).toContain('badge-live')
    expect(badge.dot).toBe(true)
  })

  it('завершённая — по результату, а не по статусу сессии', () => {
    expect(statusBadge({ live: false, status: 'finished', result: '1-0' }).text).toBe('Завершена')
  })

  it('сбой провайдера виден отдельно от обычного финала', () => {
    expect(statusBadge({ live: false, status: 'error', result: '*' }).text).toBe('Ошибка')
  })

  it('партия без результата и без эфира — прервана', () => {
    expect(statusBadge({ live: false, status: 'finished', result: '*' }).text).toBe('Прервана')
  })
})

describe('formatWhen', () => {
  const now = new Date('2026-08-01T15:00:00')

  it('свежее время — относительное', () => {
    expect(formatWhen('2026-08-01T14:59:30', now)).toBe('только что')
    expect(formatWhen('2026-08-01T14:48:00', now)).toBe('12 мин назад')
  })

  it('сегодня — время, раньше — дата', () => {
    expect(formatWhen('2026-08-01T09:05:00', now)).toBe('сегодня 09:05')
    expect(formatWhen('2026-07-30T09:05:00', now)).toBe('30.07.2026')
  })

  it('вчерашний вечер не выдаётся за «сегодня»', () => {
    expect(formatWhen('2026-07-31T23:30:00', now)).toBe('31.07.2026')
  })

  it('мусорная дата не роняет карточку', () => {
    expect(formatWhen('не дата', now)).toBe('')
  })
})

describe('plural', () => {
  it('склоняет по русским правилам', () => {
    const форма = (n) => plural(n, 'партия', 'партии', 'партий')
    expect(форма(1)).toBe('партия')
    expect(форма(3)).toBe('партии')
    expect(форма(5)).toBe('партий')
    expect(форма(11)).toBe('партий')
    expect(форма(21)).toBe('партия')
    expect(форма(112)).toBe('партий')
    expect(форма(0)).toBe('партий')
  })
})

describe('progressLabel', () => {
  it('показывает сыграно из всего', () => {
    expect(progressLabel(3, 6)).toBe('3 / 6')
  })
})
