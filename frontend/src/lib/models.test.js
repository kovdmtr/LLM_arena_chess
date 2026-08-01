import { describe, expect, it } from 'vitest'

import { groupByProvider, indexModels, initials, providerColor, providerLabel } from './models.js'

const CATALOG = [
  { id: 'gpt-4o', display_name: 'GPT-4o', provider: 'openai', has_key: true },
  { id: 'claude-opus-4-8', display_name: 'Claude Opus 4.8', provider: 'anthropic', has_key: true },
  { id: 'gemini-2.5-pro', display_name: 'Gemini 2.5 Pro', provider: 'gemini', has_key: false },
]

describe('провайдеры', () => {
  it('знают имена провайдеров бэкенда (в т.ч. gemini, а не google)', () => {
    expect(providerLabel('gemini')).toBe('Google Gemini')
    expect(providerLabel('openai')).toBe('OpenAI')
    expect(providerColor('anthropic')).toBe('var(--p-anthropic)')
  })

  it('незнакомый провайдер не ломает вёрстку', () => {
    expect(providerLabel('mistral')).toBe('mistral')
    expect(providerColor('mistral')).toBe('var(--muted)')
    expect(providerColor(undefined)).toBe('var(--muted)')
  })
})

describe('initials', () => {
  it('берёт буквы значимых слов', () => {
    expect(initials('Claude Opus 4.8')).toBe('CO')
    expect(initials('Gemini 2.5 Pro')).toBe('GE')
    expect(initials('GPT-4o')).toBe('GP')
  })

  it('не падает на пустом и странном имени', () => {
    expect(initials('')).toBe('??')
    expect(initials(undefined)).toBe('??')
    expect(initials('4')).toBe('4')
  })
})

describe('indexModels', () => {
  it('ищет модель по id и по отображаемому имени', () => {
    const catalog = indexModels(CATALOG)
    expect(catalog.find('gpt-4o').provider).toBe('openai')
    // список партий отдаёт только display_name — по нему и ищем провайдера
    expect(catalog.find('Claude Opus 4.8').provider).toBe('anthropic')
  })

  it('модель вне каталога — null, а не исключение', () => {
    expect(indexModels(CATALOG).find('нет такой')).toBeNull()
    expect(indexModels().find('gpt-4o')).toBeNull()
  })
})

describe('groupByProvider', () => {
  it('группирует, сохраняя порядок каталога', () => {
    const groups = groupByProvider(CATALOG)
    expect(groups.map((g) => g.provider)).toEqual(['openai', 'anthropic', 'gemini'])
    expect(groups[0].models).toHaveLength(1)
    expect(groups[2].label).toBe('Google Gemini')
  })

  it('несколько моделей одного провайдера — одна группа', () => {
    const groups = groupByProvider([
      ...CATALOG,
      { id: 'gpt-4o-mini', display_name: 'GPT-4o mini', provider: 'openai', has_key: true },
    ])
    expect(groups).toHaveLength(3)
    expect(groups[0].models.map((m) => m.id)).toEqual(['gpt-4o', 'gpt-4o-mini'])
  })
})
