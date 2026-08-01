/* Состояние живой партии: свёртка кадров WebSocket (docs/FRONTEND.md §3).
 *
 * Чистый редьюсер — вся логика просмотра проверяется тестами без сокета и DOM.
 * Сервер при подключении переигрывает уже накопленные кадры, поэтому та же
 * свёртка одинаково работает и для «догона», и для новых событий.
 */
import { START_FEN } from './fen.js'

export const LIVE_CONNECTING = 'connecting'
export const LIVE_RUNNING = 'running'
export const LIVE_FINISHED = 'finished'
export const LIVE_ERROR = 'error'

/** Пустое состояние; `record` (из `GET /api/games/{id}`) даёт мгновенную отрисовку. */
export function initialLiveState(record = null) {
  const moves = (record && record.moves ? record.moves : []).map(fromRecord)
  const last = moves[moves.length - 1]
  return {
    status: LIVE_CONNECTING,
    fen: last ? last.fen : START_FEN,
    lastMove: last ? last.uci : null,
    moves,
    thinkingSide: null,
    illegal: null,
    hints: [],
    result: record ? record.result : null,
    termination: record ? record.termination : null,
    error: null,
  }
}

function fromRecord(move) {
  return {
    ply: move.ply,
    side: move.side,
    san: move.san,
    uci: move.uci,
    fen: move.fen_after,
    reasoning: move.reasoning || '',
  }
}

/** Кадр `{type, payload}` → новое состояние (исходное не мутируется). */
export function applyFrame(state, frame) {
  const type = frame && frame.type
  const payload = (frame && frame.payload) || {}

  switch (type) {
    case 'game_start':
      return { ...state, status: LIVE_RUNNING, fen: payload.fen || state.fen, lastMove: null }

    case 'turn_start':
      return {
        ...state,
        status: LIVE_RUNNING,
        fen: payload.fen || state.fen,
        thinkingSide: payload.side || null,
        illegal: null,
      }

    case 'move': {
      const move = {
        ply: payload.ply,
        side: payload.side,
        san: payload.san,
        uci: payload.uci,
        fen: payload.fen,
        reasoning: payload.reasoning || '',
      }
      // повтор того же полухода (переподключение) не должен задваивать ленту
      const moves = state.moves.filter((m) => m.ply !== move.ply).concat(move)
      moves.sort((a, b) => a.ply - b.ply)
      return {
        ...state,
        status: LIVE_RUNNING,
        moves,
        fen: payload.fen || state.fen,
        lastMove: payload.uci || null,
        thinkingSide: null,
        illegal: null,
      }
    }

    case 'illegal_attempt':
      return {
        ...state,
        illegal: {
          side: payload.side,
          ply: payload.ply,
          attempt: payload.attempt,
          reason: payload.reason || '',
          raw: payload.raw || '',
        },
      }

    case 'hint':
      return {
        ...state,
        hints: state.hints.concat({
          side: payload.side,
          ply: payload.ply,
          bestMove: payload.best_move,
          evalCp: payload.eval_cp ?? null,
          mateIn: payload.mate_in ?? null,
          remaining: payload.hints_remaining ?? null,
        }),
      }

    case 'game_over':
      return {
        ...state,
        status: LIVE_FINISHED,
        fen: payload.fen || state.fen,
        result: payload.result ?? state.result,
        termination: payload.termination ?? state.termination,
        thinkingSide: null,
        illegal: null,
      }

    case 'status':
      return {
        ...state,
        status: payload.status === LIVE_ERROR ? LIVE_ERROR : payload.status || state.status,
        result: payload.result ?? state.result,
        termination: payload.termination ?? state.termination,
        error: payload.error || state.error,
        thinkingSide: null,
      }

    case 'error':
      return { ...state, status: LIVE_ERROR, error: payload.message || '', thinkingSide: null }

    default:
      return state // незнакомый кадр (бэкенд новее фронта) просто игнорируем
  }
}

/** Последний ход стороны, которая только что сходила — для панели «мысли модели». */
export function lastMoveOf(state) {
  return state.moves.length ? state.moves[state.moves.length - 1] : null
}

/** Подсказки, выданные к этому полуходу (в ленте помечаем ход значком). */
export function hintForPly(state, ply) {
  return state.hints.find((hint) => hint.ply === ply) || null
}
