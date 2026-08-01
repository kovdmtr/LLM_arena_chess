import { describe, expect, it } from 'vitest'

import { THEME_KEY, nextTheme, readStoredTheme, resolveTheme, storeTheme } from './theme.js'

/** Минимальный поддельный localStorage — тесту не нужен jsdom. */
function fakeStorage(initial = {}) {
  const data = { ...initial }
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = String(value)
    },
  }
}

describe('resolveTheme', () => {
  it('сохранённый выбор важнее системной настройки', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })

  it('без выбора берёт системную', () => {
    expect(resolveTheme(null, true)).toBe('dark')
    expect(resolveTheme(null, false)).toBe('light')
  })

  it('мусор в хранилище игнорируется', () => {
    expect(resolveTheme('пурпурная', false)).toBe('light')
    expect(resolveTheme('', true)).toBe('dark')
  })
})

describe('nextTheme', () => {
  it('переключает туда и обратно', () => {
    expect(nextTheme('light')).toBe('dark')
    expect(nextTheme('dark')).toBe('light')
    expect(nextTheme(nextTheme('light'))).toBe('light')
  })
})

describe('хранилище темы', () => {
  it('запоминает выбор под известным ключом', () => {
    const storage = fakeStorage()
    storeTheme('dark', storage)
    expect(storage.data[THEME_KEY]).toBe('dark')
    expect(readStoredTheme(storage)).toBe('dark')
  })

  it('переживает отсутствие хранилища (приватный режим)', () => {
    expect(readStoredTheme(null)).toBeNull()
    expect(() => storeTheme('dark', null)).not.toThrow()
  })

  it('сохранённая тема доживает до resolveTheme', () => {
    const storage = fakeStorage()
    storeTheme('light', storage)
    expect(resolveTheme(readStoredTheme(storage), true)).toBe('light')
  })
})
