/* Интернационализация: словари → функция `t(key, params)`.
 *
 * Правило проекта: интерфейс целиком на одном языке, без смешения. Поэтому
 * фразы не «зашиты» в данные — модули данных (`format`, `newGame`, `api`)
 * возвращают ключи и параметры, а текст подставляет `t` уже в компоненте.
 */
import { MESSAGES } from '../i18n/messages.js'

export const LANGS = ['ru', 'en']
export const DEFAULT_LANG = 'ru'
export const LANG_KEY = 'arena-lang'

/** Язык интерфейса: сохранённый выбор → язык браузера → русский. */
export function resolveLang(stored, browserLangs = []) {
  if (LANGS.includes(stored)) return stored
  for (const tag of browserLangs) {
    const code = String(tag || '').slice(0, 2).toLowerCase()
    if (LANGS.includes(code)) return code
  }
  return DEFAULT_LANG
}

/** Другой язык (переключатель в шапке — на два языка). */
export function otherLang(lang) {
  return lang === 'ru' ? 'en' : 'ru'
}

function interpolate(text, params) {
  if (!params) return text
  return String(text).replace(/\{(\w+)\}/g, (match, name) =>
    name in params ? String(params[name]) : match,
  )
}

function pluralForm(value, count, lang) {
  const rules = new Intl.PluralRules(lang)
  const category = rules.select(count)
  return value[category] ?? value.other ?? value.many ?? value.one
}

/**
 * Собрать переводчик для языка.
 *
 * Неизвестный ключ возвращается как есть — пропажа перевода видна, но экран
 * не падает. Значение-объект трактуется как формы множественного числа и
 * выбирается по `params.count` через `Intl.PluralRules`.
 */
export function createT(lang) {
  const dict = MESSAGES[lang] || MESSAGES[DEFAULT_LANG]
  function t(key, params) {
    const value = dict[key]
    if (value === undefined) return key
    if (typeof value === 'object') {
      const count = params && params.count
      return interpolate(pluralForm(value, Number(count) || 0, lang), params)
    }
    return interpolate(value, params)
  }

  /** Есть ли перевод: бэкенд может прислать код ошибки, которого мы не знаем. */
  t.has = (key) => Object.prototype.hasOwnProperty.call(dict, key)
  return t
}

function safeStorage() {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function readStoredLang(storage = safeStorage()) {
  try {
    return storage ? storage.getItem(LANG_KEY) : null
  } catch {
    return null
  }
}

export function storeLang(lang, storage = safeStorage()) {
  try {
    if (storage) storage.setItem(LANG_KEY, lang)
  } catch {
    /* не критично: язык просто не запомнится */
  }
}

/** Язык при старте приложения (и проставленный в <html lang>). */
export function initLang() {
  const lang = resolveLang(readStoredLang(), navigator.languages || [navigator.language])
  document.documentElement.setAttribute('lang', lang)
  return lang
}
