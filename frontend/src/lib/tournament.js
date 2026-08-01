/* Турниры: выбор участников и оформление таблицы/расписания. Чистый модуль.
 *
 * Правила выбора совпадают с `POST /api/tournaments` (см. api.py): минимум две
 * различные модели, каждая — с ключом. Причины возвращаются ключами словаря.
 */

/** Переключить модель в выборе, сохраняя порядок нажатий. */
export function toggleSelection(selected, id) {
  return selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]
}

/** Почему нельзя стартовать турнир: ключ словаря; `null` — можно. */
export function tournamentBlockedReason(selected, models = []) {
  const playable = models.filter((model) => model.has_key)
  if (playable.length < 2) return 'newTournament.blocked.notEnoughModels'

  const unique = [...new Set(selected)]
  if (unique.length < 2) return 'error.tournamentTooFewModels'

  const index = new Map(models.map((model) => [model.id, model]))
  for (const id of unique) {
    const model = index.get(id)
    if (!model) return 'newTournament.blocked.unknownModel'
    if (!model.has_key) return 'newTournament.blocked.noKey'
  }
  return null
}

/** Сколько партий в round-robin: пары × круги. */
export function gameCount(participants, double = false) {
  const n = Math.max(0, participants)
  if (n < 2) return 0 // иначе формула даёт -0 и путает вывод
  const pairs = (n * (n - 1)) / 2
  return double ? pairs * 2 : pairs
}

/** Расписание по турам: `[{ round, games }]`, порядок туров возрастающий. */
export function groupByRound(schedule = []) {
  const rounds = new Map()
  for (const game of schedule) {
    const key = game.round
    if (!rounds.has(key)) rounds.set(key, [])
    rounds.get(key).push(game)
  }
  return [...rounds.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([round, games]) => ({ round, games }))
}

/** Очки: 1, 1.5, 0.5 — половинки не прячем, целые не раздуваем. */
export function formatPoints(points) {
  const value = Number(points) || 0
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** Доля очков (0..100 с бэкенда) → «75%». */
export function formatScorePct(pct) {
  if (pct === null || pct === undefined) return '—'
  return `${Math.round(pct)}%`
}

/** Средняя точность (0..1) → «82%»; без анализа — прочерк. */
export function formatAccuracy(accuracy) {
  if (accuracy === null || accuracy === undefined) return '—'
  return `${Math.round(accuracy * 100)}%`
}
