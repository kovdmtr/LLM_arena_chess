import { describe, expect, it } from 'vitest'

import { createT } from './i18n.js'
import { formatWhen, progressLabel, resultLabel, statusBadge, winnerOf } from './format.js'

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
  it('отдаёт ключ словаря, а не готовую фразу', () => {
    const badge = statusBadge({ live: true, status: 'running', result: '*' })
    expect(badge.key).toBe('status.live')
    expect(badge.className).toContain('badge-live')
    expect(badge.dot).toBe(true)
    expect(createT('en')(badge.key)).toBe('LIVE')
  })

  it('завершённая — по результату, а не по статусу сессии', () => {
    expect(statusBadge({ live: false, status: 'finished', result: '1-0' }).key).toBe('status.finished')
  })

  it('сбой провайдера виден отдельно от обычного финала', () => {
    expect(statusBadge({ live: false, status: 'error', result: '*' }).key).toBe('status.error')
  })

  it('партия без результата и без эфира — прервана', () => {
    expect(statusBadge({ live: false, status: 'finished', result: '*' }).key).toBe('status.aborted')
  })
})

describe('formatWhen', () => {
  const now = new Date('2026-08-01T15:00:00')

  it('свежее время — относительное, с параметром для склонения', () => {
    expect(formatWhen('2026-08-01T14:59:30', now)).toEqual({ key: 'time.justNow' })
    expect(formatWhen('2026-08-01T14:48:00', now)).toEqual({
      key: 'time.minutesAgo',
      params: { count: 12 },
    })
  })

  it('сегодня — время в 24-часовом виде', () => {
    expect(formatWhen('2026-08-01T09:05:00', now)).toEqual({
      key: 'time.today',
      params: { time: '09:05' },
    })
  })

  it('дата раскладывается по правилам языка', () => {
    expect(formatWhen('2026-07-30T09:05:00', now, 'ru').params.date).toBe('30.07.2026')
    expect(formatWhen('2026-07-30T09:05:00', now, 'en').params.date).toBe('07/30/2026')
  })

  it('вчерашний вечер не выдаётся за «сегодня»', () => {
    expect(formatWhen('2026-07-31T23:30:00', now).key).toBe('time.date')
  })

  it('мусорная дата не роняет карточку', () => {
    expect(formatWhen('не дата', now)).toBeNull()
  })

  it('результат переводится обоими словарями', () => {
    const when = formatWhen('2026-08-01T14:48:00', now)
    expect(createT('ru')(when.key, when.params)).toBe('12 мин назад')
    expect(createT('en')(when.key, when.params)).toBe('12 min ago')
  })
})

describe('progressLabel', () => {
  it('показывает сыграно из всего', () => {
    expect(progressLabel(3, 6)).toBe('3 / 6')
  })
})
