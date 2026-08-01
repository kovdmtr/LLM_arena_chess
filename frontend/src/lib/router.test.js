import { describe, expect, it } from 'vitest'

import { NOT_FOUND, hrefFor, isActiveNav, parseRoute } from './router.js'

describe('parseRoute', () => {
  it('разбирает экраны верхнего уровня', () => {
    expect(parseRoute('/')).toEqual({ name: 'home', params: {} })
    expect(parseRoute('/games')).toEqual({ name: 'archive', params: {} })
    expect(parseRoute('/tournaments')).toEqual({ name: 'tournaments', params: {} })
  })

  it('различает /games/new и партию по id — статический сегмент важнее', () => {
    expect(parseRoute('/games/new')).toEqual({ name: 'new-game', params: {} })
    expect(parseRoute('/games/abc-123')).toEqual({ name: 'game', params: { id: 'abc-123' } })
    expect(parseRoute('/tournaments/new')).toEqual({ name: 'new-tournament', params: {} })
    expect(parseRoute('/tournaments/t1')).toEqual({ name: 'tournament', params: { id: 't1' } })
  })

  it('терпит хвостовой слэш', () => {
    expect(parseRoute('/games/')).toEqual({ name: 'archive', params: {} })
    expect(parseRoute('/games/abc/')).toEqual({ name: 'game', params: { id: 'abc' } })
  })

  it('неизвестный и слишком глубокий путь → not-found', () => {
    expect(parseRoute('/nope').name).toBe(NOT_FOUND)
    expect(parseRoute('/games/abc/extra').name).toBe(NOT_FOUND)
  })
})

describe('hrefFor', () => {
  it('обратен parseRoute для всех экранов', () => {
    const cases = [
      ['home', {}],
      ['archive', {}],
      ['new-game', {}],
      ['game', { id: 'g1' }],
      ['tournaments', {}],
      ['new-tournament', {}],
      ['tournament', { id: 't1' }],
    ]
    for (const [name, params] of cases) {
      expect(parseRoute(hrefFor(name, params))).toEqual({ name, params })
    }
  })

  it('экранирует id в адресе', () => {
    expect(hrefFor('game', { id: 'a b/c' })).toBe('/games/a%20b%2Fc')
  })
})

describe('isActiveNav', () => {
  it('подсвечивает раздел на вложенных экранах', () => {
    expect(isActiveNav('archive', parseRoute('/games/abc'))).toBe(true)
    expect(isActiveNav('tournaments', parseRoute('/tournaments/t1'))).toBe(true)
    expect(isActiveNav('tournaments', parseRoute('/tournaments/new'))).toBe(true)
  })

  it('не подсвечивает чужие разделы', () => {
    expect(isActiveNav('archive', parseRoute('/tournaments'))).toBe(false)
    expect(isActiveNav('home', parseRoute('/games'))).toBe(false)
    // «Новая партия» — отдельный пункт, архив на нём не активен
    expect(isActiveNav('archive', parseRoute('/games/new'))).toBe(false)
  })
})
