import { describe, expect, it } from 'vitest'

import { EN, MESSAGES, RU } from '../i18n/messages.js'
import { DEFAULT_LANG, LANGS, createT, otherLang, resolveLang } from './i18n.js'

const CYRILLIC = /[А-Яа-яЁё]/

describe('resolveLang', () => {
  it('сохранённый выбор важнее языка браузера', () => {
    expect(resolveLang('en', ['ru-RU'])).toBe('en')
    expect(resolveLang('ru', ['en-US'])).toBe('ru')
  })

  it('без выбора берёт первый поддерживаемый язык браузера', () => {
    expect(resolveLang(null, ['en-GB', 'ru'])).toBe('en')
    expect(resolveLang(null, ['de-DE', 'en-US'])).toBe('en')
  })

  it('незнакомые языки → русский по умолчанию', () => {
    expect(resolveLang(null, ['de', 'fr'])).toBe(DEFAULT_LANG)
    expect(resolveLang('klingon', [])).toBe(DEFAULT_LANG)
    expect(resolveLang(null, [])).toBe(DEFAULT_LANG)
  })
})

describe('otherLang', () => {
  it('переключает между двумя языками', () => {
    expect(otherLang('ru')).toBe('en')
    expect(otherLang('en')).toBe('ru')
  })
})

describe('createT', () => {
  it('переводит ключ на выбранный язык', () => {
    expect(createT('ru')('nav.archive')).toBe('Партии')
    expect(createT('en')('nav.archive')).toBe('Games')
  })

  it('подставляет параметры', () => {
    expect(createT('ru')('time.minutesAgo', { count: 12 })).toBe('12 мин назад')
    expect(createT('en')('error.generic', { status: 500 })).toBe('Request failed (500).')
  })

  it('склоняет по правилам языка', () => {
    const ru = createT('ru')
    expect(ru('archive.count', { count: 1 })).toBe('1 партия')
    expect(ru('archive.count', { count: 3 })).toBe('3 партии')
    expect(ru('archive.count', { count: 11 })).toBe('11 партий')

    const en = createT('en')
    expect(en('archive.count', { count: 1 })).toBe('1 game')
    expect(en('archive.count', { count: 5 })).toBe('5 games')
  })

  it('неизвестный ключ возвращается как есть — экран не падает', () => {
    expect(createT('ru')('нет.такого.ключа')).toBe('нет.такого.ключа')
  })

  it('неизвестный язык откатывается на язык по умолчанию', () => {
    expect(createT('de')('nav.home')).toBe(RU['nav.home'])
  })
})

describe('словари', () => {
  it('покрывают одинаковый набор ключей', () => {
    expect(Object.keys(EN).sort()).toEqual(Object.keys(RU).sort())
  })

  it('строго одноязычны: в EN нет кириллицы', () => {
    const dirty = Object.entries(EN)
      .filter(([, value]) => CYRILLIC.test(JSON.stringify(value)))
      .map(([key]) => key)
    expect(dirty).toEqual([])
  })

  it('формы множественного числа заданы в обоих языках одинаково', () => {
    for (const key of Object.keys(RU)) {
      expect(typeof EN[key]).toBe(typeof RU[key])
    }
  })

  it('известны ровно поддерживаемые языки', () => {
    expect(Object.keys(MESSAGES).sort()).toEqual([...LANGS].sort())
  })
})
