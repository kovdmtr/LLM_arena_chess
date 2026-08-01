import { describe, expect, it } from 'vitest'

import { START_FEN } from './fen.js'
import {
  LIVE_CONNECTING,
  LIVE_ERROR,
  LIVE_FINISHED,
  LIVE_RUNNING,
  applyFrame,
  hintForPly,
  initialLiveState,
  lastMoveOf,
} from './live.js'
import { liveSocketUrl } from './useLiveGame.js'

const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1'

function frame(type, payload = {}) {
  return { type, payload }
}

function moveFrame(ply, side, san, uci, fen, reasoning = '') {
  return frame('move', { ply, side, san, uci, fen, reasoning })
}

describe('initialLiveState', () => {
  it('без записи — начальная позиция и статус «подключаемся»', () => {
    const state = initialLiveState()

    expect(state.status).toBe(LIVE_CONNECTING)
    expect(state.fen).toBe(START_FEN)
    expect(state.moves).toEqual([])
    expect(state.lastMove).toBeNull()
  })

  it('запись партии даёт мгновенную отрисовку последней позиции', () => {
    const state = initialLiveState({
      result: '*',
      moves: [
        { ply: 1, side: 'white', san: 'e4', uci: 'e2e4', fen_after: AFTER_E4, reasoning: 'центр' },
      ],
    })

    expect(state.fen).toBe(AFTER_E4)
    expect(state.lastMove).toBe('e2e4')
    expect(state.moves[0].reasoning).toBe('центр')
  })
})

describe('applyFrame', () => {
  it('ход пополняет ленту, двигает доску и снимает «думает»', () => {
    let state = applyFrame(initialLiveState(), frame('game_start', { fen: START_FEN }))
    state = applyFrame(state, frame('turn_start', { side: 'white', ply: 1, fen: START_FEN }))
    expect(state.thinkingSide).toBe('white')

    state = applyFrame(state, moveFrame(1, 'white', 'e4', 'e2e4', AFTER_E4, 'захват центра'))

    expect(state.status).toBe(LIVE_RUNNING)
    expect(state.fen).toBe(AFTER_E4)
    expect(state.lastMove).toBe('e2e4')
    expect(state.thinkingSide).toBeNull()
    expect(lastMoveOf(state).reasoning).toBe('захват центра')
  })

  it('повтор кадра при переподключении не задваивает ход', () => {
    let state = applyFrame(initialLiveState(), moveFrame(1, 'white', 'e4', 'e2e4', AFTER_E4))
    state = applyFrame(state, moveFrame(1, 'white', 'e4', 'e2e4', AFTER_E4))

    expect(state.moves).toHaveLength(1)
  })

  it('ходы держатся по возрастанию полухода даже при перепутанном порядке', () => {
    let state = applyFrame(initialLiveState(), moveFrame(2, 'black', 'e5', 'e7e5', AFTER_E4))
    state = applyFrame(state, moveFrame(1, 'white', 'e4', 'e2e4', AFTER_E4))

    expect(state.moves.map((m) => m.ply)).toEqual([1, 2])
  })

  it('нелегальная попытка показывается и снимается следующим ходом', () => {
    let state = applyFrame(
      initialLiveState(),
      frame('illegal_attempt', { side: 'white', ply: 1, attempt: 2, reason: 'нет такого хода' }),
    )
    expect(state.illegal.attempt).toBe(2)

    state = applyFrame(state, moveFrame(1, 'white', 'e4', 'e2e4', AFTER_E4))
    expect(state.illegal).toBeNull()
  })

  it('подсказка запоминается и находится по полуходу', () => {
    const state = applyFrame(
      initialLiveState(),
      frame('hint', { side: 'white', ply: 3, best_move: 'g1f3', eval_cp: 25, hints_remaining: 2 }),
    )

    expect(hintForPly(state, 3)).toMatchObject({ bestMove: 'g1f3', evalCp: 25, remaining: 2 })
    expect(hintForPly(state, 1)).toBeNull()
  })

  it('game_over фиксирует итог, status закрывает партию', () => {
    let state = applyFrame(
      initialLiveState(),
      frame('game_over', { result: '0-1', termination: 'checkmate', fen: AFTER_E4 }),
    )
    expect(state.status).toBe(LIVE_FINISHED)
    expect(state.result).toBe('0-1')

    state = applyFrame(state, frame('status', { status: 'finished', result: '0-1' }))
    expect(state.status).toBe(LIVE_FINISHED)
    expect(state.thinkingSide).toBeNull()
  })

  it('сбой партии виден отдельно от нормального финала', () => {
    const state = applyFrame(
      initialLiveState(),
      frame('status', { status: 'error', error: 'провайдер отказал' }),
    )

    expect(state.status).toBe(LIVE_ERROR)
    expect(state.error).toBe('провайдер отказал')
  })

  it('кадр error (неизвестная партия) переводит экран в ошибку', () => {
    const state = applyFrame(initialLiveState(), frame('error', { message: 'партия не найдена' }))

    expect(state.status).toBe(LIVE_ERROR)
    expect(state.error).toBe('партия не найдена')
  })

  it('незнакомый кадр не меняет состояние — бэкенд может быть новее фронта', () => {
    const state = initialLiveState()
    expect(applyFrame(state, frame('pause', { by: 'user' }))).toBe(state)
    expect(applyFrame(state, null)).toBe(state)
  })
})

describe('liveSocketUrl', () => {
  it('http → ws, https → wss', () => {
    expect(liveSocketUrl('g1', { protocol: 'http:', host: 'localhost:5173', search: '' })).toBe(
      'ws://localhost:5173/games/g1/ws',
    )
    expect(liveSocketUrl('g1', { protocol: 'https:', host: 'arena.example', search: '' })).toBe(
      'wss://arena.example/games/g1/ws',
    )
  })

  it('несёт токен доступа — WebSocket тоже под «воротами»', () => {
    const url = liveSocketUrl('g1', { protocol: 'http:', host: 'h', search: '?token=a b' })
    expect(url).toBe('ws://h/games/g1/ws?token=a%20b')
  })

  it('экранирует id партии', () => {
    const url = liveSocketUrl('a/b', { protocol: 'http:', host: 'h', search: '' })
    expect(url).toBe('ws://h/games/a%2Fb/ws')
  })
})
