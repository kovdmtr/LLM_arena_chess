/* Форматирование данных API для интерфейса. Чистые функции — под тестами. */

/** Итог партии человеку: половинки дробью, незавершённая — прочерк. */
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
 * Статус партии бейджем: `{ text, className }`.
 *
 * Идущая партия важнее статуса из записи — её и подсвечиваем «в эфире».
 */
export function statusBadge(game) {
  if (game.live) return { text: 'В ЭФИРЕ', className: 'badge badge-live', dot: true }
  if (game.status === 'error') return { text: 'Ошибка', className: 'badge badge-live' }
  if (game.result && game.result !== '*') {
    return { text: 'Завершена', className: 'badge badge-done' }
  }
  return { text: 'Прервана', className: 'badge' }
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

function pad(value) {
  return String(value).padStart(2, '0')
}

/**
 * Когда была партия: «только что», «12 мин назад», «сегодня 14:03», дата.
 *
 * `now` инжектится, чтобы тест не зависел от текущего времени.
 */
export function formatWhen(iso, now = new Date()) {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return ''
  const diff = now.getTime() - then.getTime()

  if (diff < MINUTE) return 'только что'
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)} мин назад`
  if (diff < DAY && then.getDate() === now.getDate()) {
    return `сегодня ${pad(then.getHours())}:${pad(then.getMinutes())}`
  }
  return `${pad(then.getDate())}.${pad(then.getMonth() + 1)}.${then.getFullYear()}`
}

/** Русское склонение по числу: 1 партия, 2 партии, 5 партий. */
export function plural(n, one, few, many) {
  const mod100 = Math.abs(n) % 100
  const mod10 = Math.abs(n) % 10
  if (mod100 >= 11 && mod100 <= 14) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

/** Прогресс турнира строкой: «3 / 6». */
export function progressLabel(played, total) {
  return `${played} / ${total}`
}
