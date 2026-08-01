/* Форматирование данных API. Чистые функции — под тестами.
 *
 * Текстов здесь нет: функции возвращают ключ словаря и параметры, а фразу
 * подставляет `t` в компоненте. Так интерфейс остаётся строго одноязычным.
 */

/** Итог партии человеку: половинки дробью, незавершённая — прочерк. Язык не нужен. */
export function resultLabel(result) {
  switch (result) {
    case '1-0':
      return '1–0'
    case '0-1':
      return '0–1'
    case '1/2-1/2':
      return '½–½'
    default:
      return '—'
  }
}

/** Кто выиграл: 'white' | 'black' | 'draw' | null (партия не окончена). */
export function winnerOf(result) {
  if (result === '1-0') return 'white'
  if (result === '0-1') return 'black'
  if (result === '1/2-1/2') return 'draw'
  return null
}

/**
 * Статус партии бейджем: `{ key, className, dot }`.
 *
 * Идущая партия важнее статуса из записи — её и подсвечиваем «в эфире».
 */
export function statusBadge(game) {
  if (game.live) return { key: 'status.live', className: 'badge badge-live', dot: true }
  if (game.status === 'error') return { key: 'status.error', className: 'badge badge-live' }
  if (game.result && game.result !== '*') {
    return { key: 'status.finished', className: 'badge badge-done' }
  }
  return { key: 'status.aborted', className: 'badge' }
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

function pad(value) {
  return String(value).padStart(2, '0')
}

/**
 * Когда была партия: `{ key, params }` — «только что», «N мин назад»,
 * «сегодня HH:MM» или дата в формате языка.
 *
 * `now` инжектится, чтобы тест не зависел от текущего времени; `lang` нужен
 * только для порядка чисел в дате (01.08.2026 против 08/01/2026).
 */
export function formatWhen(iso, now = new Date(), lang = 'ru') {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return null
  const diff = now.getTime() - then.getTime()

  if (diff < MINUTE) return { key: 'time.justNow' }
  if (diff < HOUR) return { key: 'time.minutesAgo', params: { count: Math.floor(diff / MINUTE) } }
  if (diff < DAY && then.getDate() === now.getDate()) {
    return { key: 'time.today', params: { time: `${pad(then.getHours())}:${pad(then.getMinutes())}` } }
  }
  const date = new Intl.DateTimeFormat(lang, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(then)
  return { key: 'time.date', params: { date } }
}

/** Прогресс турнира строкой: «3 / 6». */
export function progressLabel(played, total) {
  return `${played} / ${total}`
}
