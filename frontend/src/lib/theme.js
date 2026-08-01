/* Тема оформления: светлая/тёмная (DESIGN_BRIEF §2).
 *
 * По умолчанию — системная; явный выбор пользователя сохраняется и переживает
 * перезагрузку. Тема — атрибут `data-theme` на <html>, всё остальное делает CSS.
 */

export const THEME_KEY = 'arena-theme'
export const THEMES = ['light', 'dark']

/** Итоговая тема: сохранённый выбор важнее системной настройки. */
export function resolveTheme(stored, prefersDark) {
  if (THEMES.includes(stored)) return stored
  return prefersDark ? 'dark' : 'light'
}

/** Противоположная тема (для кнопки-переключателя). */
export function nextTheme(theme) {
  return theme === 'dark' ? 'light' : 'dark'
}

function safeStorage() {
  try {
    return window.localStorage
  } catch {
    return null // приватный режим/запрет хранилища — просто работаем без памяти
  }
}

export function readStoredTheme(storage = safeStorage()) {
  try {
    return storage ? storage.getItem(THEME_KEY) : null
  } catch {
    return null
  }
}

export function storeTheme(theme, storage = safeStorage()) {
  try {
    if (storage) storage.setItem(THEME_KEY, theme)
  } catch {
    /* не критично: тема просто не запомнится */
  }
}

/** Системное предпочтение тёмной темы. */
export function prefersDark() {
  return Boolean(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
}

/** Применить тему к документу. */
export function applyTheme(theme, doc = document) {
  doc.documentElement.setAttribute('data-theme', theme)
}

/** Тема при старте приложения (и сразу применённая к документу). */
export function initTheme() {
  const theme = resolveTheme(readStoredTheme(), prefersDark())
  applyTheme(theme)
  return theme
}
