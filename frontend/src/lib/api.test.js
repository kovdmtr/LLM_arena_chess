import { describe, expect, it } from 'vitest'

import { errorInfo, tokenFrom, withToken } from './api.js'
import { createT } from './i18n.js'

describe('токен доступа', () => {
  it('достаётся из query-строки', () => {
    expect(tokenFrom('?token=s3cret')).toBe('s3cret')
    expect(tokenFrom('?a=1&token=s3cret&b=2')).toBe('s3cret')
  })

  it('его отсутствие — не ошибка', () => {
    expect(tokenFrom('')).toBeNull()
    expect(tokenFrom('?a=1')).toBeNull()
    expect(tokenFrom(undefined)).toBeNull()
  })

  it('подставляется в путь, не ломая уже имеющиеся параметры', () => {
    expect(withToken('/api/games', '?token=t')).toBe('/api/games?token=t')
    expect(withToken('/api/games?live=1', '?token=t')).toBe('/api/games?live=1&token=t')
  })

  it('без токена путь остаётся прежним', () => {
    expect(withToken('/api/games', '')).toBe('/api/games')
  })

  it('экранируется — токен может содержать спецсимволы', () => {
    expect(withToken('/api/games', '?token=' + encodeURIComponent('a b&c'))).toBe(
      '/api/games?token=a%20b%26c',
    )
  })
})

describe('errorInfo', () => {
  it('берёт detail строкой — так бэкенд отдаёт понятные ошибки формы', () => {
    expect(errorInfo({ detail: 'Ключ для модели не задан.' }, 400)).toEqual({
      text: 'Ключ для модели не задан.',
    })
  })

  it('склеивает detail списком (ошибки валидации FastAPI)', () => {
    expect(errorInfo({ detail: [{ msg: 'field required' }, { msg: 'too short' }] }, 422)).toEqual({
      text: 'field required; too short',
    })
  })

  it('без detail отдаёт ключ словаря — он переводится на язык интерфейса', () => {
    expect(errorInfo(null, 404)).toEqual({ key: 'error.notFound' })
    expect(errorInfo({}, 403)).toEqual({ key: 'error.forbidden' })
    expect(errorInfo(null, 500)).toEqual({ key: 'error.generic', params: { status: 500 } })

    const info = errorInfo(null, 500)
    expect(createT('en')(info.key, info.params)).toBe('Request failed (500).')
    expect(createT('ru')(info.key, info.params)).toBe('Ошибка запроса (500).')
  })
})

describe('errorInfo: коды бэкенда', () => {
  it('код из detail становится ключом словаря, params — подстановкой', () => {
    const info = errorInfo({ detail: { code: 'error.modelNoKey', params: { id: 'gpt-4o' } } }, 400)

    expect(info.key).toBe('error.modelNoKey')
    expect(info.params).toEqual({ id: 'gpt-4o' })
    expect(createT('en')(info.key, info.params)).toBe(
      'No API key is configured for model “gpt-4o”.',
    )
    expect(createT('ru')(info.key, info.params)).toContain('gpt-4o')
  })

  it('техническое message остаётся про запас — на случай незнакомого кода', () => {
    const info = errorInfo(
      { detail: { code: 'error.brandNew', message: 'подробности с бэкенда' } },
      400,
    )

    expect(info.key).toBe('error.brandNew')
    expect(createT('en').has('error.brandNew')).toBe(false)
    expect(info.text).toBe('подробности с бэкенда')
  })

  it('все коды ошибок API есть в обоих словарях', () => {
    // Список зеркалит api_error(...) в src/arena/web/api.py.
    const CODES = [
      'error.modelUnknown',
      'error.modelNoKey',
      'error.modelUnavailable',
      'error.startFailed',
      'error.tournamentTooFewModels',
      'error.gameNotFound',
      'error.tournamentNotFound',
    ]
    for (const code of CODES) {
      expect(createT('ru').has(code)).toBe(true)
      expect(createT('en').has(code)).toBe(true)
    }
  })
})
