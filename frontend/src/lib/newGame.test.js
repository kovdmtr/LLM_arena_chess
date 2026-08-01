import { describe, expect, it } from 'vitest'

import { RU } from '../i18n/messages.js'
import { defaultPick, playable, startBlockedReason } from './newGame.js'

const OPENAI = { id: 'gpt-4o', display_name: 'GPT-4o', provider: 'openai', has_key: true }
const CLAUDE = { id: 'claude-opus-4-8', display_name: 'Claude Opus 4.8', provider: 'anthropic', has_key: true }
const NO_KEY = { id: 'gemini-2.5-pro', display_name: 'Gemini 2.5 Pro', provider: 'gemini', has_key: false }

describe('playable', () => {
  it('оставляет только модели с ключом', () => {
    expect(playable([OPENAI, NO_KEY, CLAUDE]).map((m) => m.id)).toEqual([OPENAI.id, CLAUDE.id])
  })
})

describe('defaultPick', () => {
  it('ставит две первые доступные модели', () => {
    expect(defaultPick([NO_KEY, OPENAI, CLAUDE])).toEqual({ white: OPENAI.id, black: CLAUDE.id })
  })

  it('одна доступная — играет сама с собой', () => {
    expect(defaultPick([OPENAI, NO_KEY])).toEqual({ white: OPENAI.id, black: OPENAI.id })
  })

  it('ни одной доступной — пустой выбор', () => {
    expect(defaultPick([NO_KEY])).toEqual({ white: '', black: '' })
    expect(defaultPick([])).toEqual({ white: '', black: '' })
  })
})

describe('startBlockedReason', () => {
  const catalog = [OPENAI, CLAUDE, NO_KEY]

  it('корректный выбор ничем не блокируется', () => {
    expect(startBlockedReason(OPENAI.id, CLAUDE.id, catalog)).toBeNull()
  })

  it('одна модель обеими сторонами разрешена', () => {
    expect(startBlockedReason(OPENAI.id, OPENAI.id, catalog)).toBeNull()
  })

  it('модель без ключа блокирует старт (как и бэкенд), ключ — по сторонам', () => {
    expect(startBlockedReason(NO_KEY.id, CLAUDE.id, catalog)).toBe('newGame.blocked.noKeyWhite')
    expect(startBlockedReason(OPENAI.id, NO_KEY.id, catalog)).toBe('newGame.blocked.noKeyBlack')
  })

  it('пустой выбор и модель вне каталога', () => {
    expect(startBlockedReason('', CLAUDE.id, catalog)).toBe('newGame.blocked.notPicked')
    expect(startBlockedReason('нет-такой', CLAUDE.id, catalog)).toBe('newGame.blocked.unknownWhite')
  })

  it('каталог без ключей объясняет, что чинить', () => {
    expect(startBlockedReason('', '', [NO_KEY])).toBe('newGame.blocked.noModels')
  })

  it('все причины блокировки есть в словарях', () => {
    const keys = [
      startBlockedReason('', '', [NO_KEY]),
      startBlockedReason('', CLAUDE.id, catalog),
      startBlockedReason(NO_KEY.id, CLAUDE.id, catalog),
      startBlockedReason(OPENAI.id, NO_KEY.id, catalog),
      startBlockedReason('нет-такой', CLAUDE.id, catalog),
      startBlockedReason(OPENAI.id, 'нет-такой', catalog),
    ]
    for (const key of keys) expect(RU[key]).toBeTruthy()
  })
})
