import { describe, expect, it } from 'vitest'

import { errorMessage, tokenFrom, withToken } from './api.js'

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

describe('errorMessage', () => {
  it('берёт detail строкой — так бэкенд отдаёт понятные ошибки формы', () => {
    expect(errorMessage({ detail: 'Ключ для модели не задан.' }, 400)).toBe(
      'Ключ для модели не задан.',
    )
  })

  it('склеивает detail списком (ошибки валидации FastAPI)', () => {
    expect(errorMessage({ detail: [{ msg: 'field required' }, { msg: 'too short' }] }, 422)).toBe(
      'field required; too short',
    )
  })

  it('без detail даёт текст по статусу', () => {
    expect(errorMessage(null, 404)).toBe('Не найдено.')
    expect(errorMessage({}, 403)).toContain('токеном')
    expect(errorMessage(null, 500)).toContain('500')
  })
})
