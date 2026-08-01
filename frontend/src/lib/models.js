/* Каталог моделей: цвета провайдеров, инициалы для аватара, индексы поиска.
 *
 * Список партий (`GET /api/games`) отдаёт только display_name сторон, без
 * провайдера, поэтому цвет аватара ищем по каталогу (`GET /api/models`);
 * если модель из каталога исчезла — аккуратно падаем на нейтральный цвет.
 */

export const PROVIDERS = {
  anthropic: { label: 'Anthropic', color: 'var(--p-anthropic)' },
  openai: { label: 'OpenAI', color: 'var(--p-openai)' },
  gemini: { label: 'Google Gemini', color: 'var(--p-google)' },
}

export function providerLabel(provider) {
  return (PROVIDERS[provider] && PROVIDERS[provider].label) || provider || 'Модель'
}

export function providerColor(provider) {
  return (PROVIDERS[provider] && PROVIDERS[provider].color) || 'var(--muted)'
}

/**
 * Короткая метка для аватара: буквы из значимых слов имени.
 *
 * «Claude Opus 4.8» → «CO», «GPT-4o» → «GP», «o4-mini» → «O4».
 */
export function initials(displayName) {
  const name = String(displayName || '').trim()
  if (!name) return '??'
  const words = name.split(/[\s\-_.]+/).filter(Boolean)
  if (words.length >= 2 && /^[a-zA-Zа-яА-Я]/.test(words[1])) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return name.replace(/[^a-zA-Zа-яА-Я0-9]/g, '').slice(0, 2).toUpperCase() || '??'
}

/** Индекс каталога: поиск модели по id и по отображаемому имени. */
export function indexModels(models = []) {
  const byId = new Map()
  const byName = new Map()
  for (const model of models) {
    byId.set(model.id, model)
    byName.set(model.display_name, model)
  }
  return {
    byId,
    byName,
    /** Модель по id или по display_name — что нашлось. */
    find(key) {
      return byId.get(key) || byName.get(key) || null
    },
  }
}

/** Модели по провайдерам, порядок каталога сохраняется. */
export function groupByProvider(models = []) {
  const groups = []
  for (const model of models) {
    let group = groups.find((g) => g.provider === model.provider)
    if (!group) {
      group = { provider: model.provider, label: providerLabel(model.provider), models: [] }
      groups.push(group)
    }
    group.models.push(model)
  }
  return groups
}
