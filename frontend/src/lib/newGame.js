/* Логика выбора моделей для новой партии. Чистая — под тестами.
 *
 * Правило доступности одно и то же на фронте и на бэкенде: без ключа модель
 * выбрать нельзя (`has_key`), иначе `POST /api/games` вернёт 400 (см. api.py).
 */

/** Доступные для выбора модели каталога. */
export function playable(models = []) {
  return models.filter((model) => model.has_key)
}

/**
 * Кого подставить в форму по умолчанию: две первые доступные модели.
 *
 * Доступна одна — ставим её обеими сторонами (модель против себя самой —
 * легальный сценарий). Нет ни одной — пустой выбор, старт будет заблокирован.
 */
export function defaultPick(models = []) {
  const ready = playable(models)
  if (ready.length === 0) return { white: '', black: '' }
  if (ready.length === 1) return { white: ready[0].id, black: ready[0].id }
  return { white: ready[0].id, black: ready[1].id }
}

/**
 * Почему нельзя стартовать: ключ словаря; `null` — можно.
 *
 * Проверяем ровно то, что проверит бэкенд, чтобы не ловить 400 в форме.
 * Ключи по сторонам разные (а не подстановка слова «белых»/«чёрных») — так
 * перевод остаётся грамматичным в обоих языках.
 */
export function startBlockedReason(white, black, models = []) {
  if (playable(models).length === 0) return 'newGame.blocked.noModels'
  if (!white || !black) return 'newGame.blocked.notPicked'

  const index = new Map(models.map((model) => [model.id, model]))
  for (const [side, id] of [
    ['White', white],
    ['Black', black],
  ]) {
    const model = index.get(id)
    if (!model) return `newGame.blocked.unknown${side}`
    if (!model.has_key) return `newGame.blocked.noKey${side}`
  }
  return null
}
