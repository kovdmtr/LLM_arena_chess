/* Словари интерфейса. Строгое разделение языков: в EN-словаре нет русских строк,
 * в RU — английских (кроме имён собственных вроде Stockfish и PGN).
 *
 * Значение-объект — форма множественного числа (ключи Intl.PluralRules), см. lib/i18n.js.
 */

export const RU = {
  'lang.name': 'Русский',
  'lang.switch': 'Язык интерфейса',

  'nav.home': 'Арена',
  'nav.newGame': 'Новая партия',
  'nav.archive': 'Партии',
  'nav.tournaments': 'Турниры',
  'action.start': '＋ Запустить',
  'action.cancel': 'Отмена',
  'action.refresh': '↻ Обновить',
  'action.home': '← На главную',
  'theme.toDark': 'Тёмная тема',
  'theme.toLight': 'Светлая тема',

  'footer.stack': 'LLM Chess Arena · FastAPI · python-chess · Stockfish',
  'footer.disclaimer': 'Партии — реальные вызовы API моделей: запуск тратит деньги на ключах.',

  'home.eyebrow': 'Шахматная арена для языковых моделей',
  'home.title': 'Арена',
  'home.lead':
    'Запустите партию двух моделей или откройте сыгранную — с разбором качества ходов от Stockfish, мыслями моделей и планом на каждый ход.',
  'home.cta.play': 'Запустить партию',
  'home.cta.archive': 'Архив партий',
  'home.cta.tournaments': 'Турниры',
  'home.feature.analysis.title': 'Разбор качества ходов',
  'home.feature.analysis.body':
    'Stockfish размечает каждый ход: от блестящего до зевка — с оценкой в сантипешках.',
  'home.feature.hints.title': 'Подсказки движка',
  'home.feature.hints.body':
    'Каждой модели доступны три подсказки за партию — видно, когда она к ним прибегла.',
  'home.feature.plan.title': 'Мысли и план',
  'home.feature.plan.body':
    'Модель объясняет ход и ведёт приватный план игры — всё сохраняется в отчёте.',
  'home.recent.title': 'Последние партии',
  'home.recent.all': 'Все партии →',
  'home.recent.empty.title': 'Пока ни одной партии',
  'home.recent.empty.body': 'Запустите первую — она появится здесь и в архиве.',

  'archive.eyebrow': 'Архив',
  'archive.title': 'Все партии',
  'archive.loading': 'Загружаем…',
  'archive.count': { one: '{count} партия', few: '{count} партии', many: '{count} партий' },
  'archive.liveSuffix': ' · {count} в эфире',
  'archive.empty.title': 'Партий пока нет',
  'archive.empty.body': 'Запустите первую партию — она появится здесь сразу после старта.',

  'newGame.eyebrow': 'Настройка партии',
  'newGame.title': 'Новая партия',
  'newGame.lead':
    'Выберите модели для обеих сторон — можно поставить одну и ту же модель против себя самой. Партия идёт без контроля времени, легальность ходов судит python-chess.',
  'newGame.white': '♔ Белые',
  'newGame.black': '♚ Чёрные',
  'newGame.whiteShort': '♔ БЕЛЫЕ',
  'newGame.blackShort': '♚ ЧЁРНЫЕ',
  'newGame.cost':
    'Запуск партии — реальные вызовы API обеих моделей: это тратит деньги на ключах. Подсказки Stockfish (до 3 на сторону) и разбор качества ходов включаются автоматически, если движок доступен.',
  'newGame.language': 'Модели будут рассуждать и вести план по-русски — как язык интерфейса.',
  'newGame.start': '▶ Запустить партию',
  'newGame.starting': 'Запускаем…',
  'newGame.blocked.noModels': 'Нет доступных моделей: не задан ни один API-ключ (см. .env).',
  'newGame.blocked.notPicked': 'Выберите модель для обеих сторон.',
  'newGame.blocked.noKeyWhite': 'Для белых выбрана модель без ключа — она недоступна.',
  'newGame.blocked.noKeyBlack': 'Для чёрных выбрана модель без ключа — она недоступна.',
  'newGame.blocked.unknownWhite': 'Модель для белых не найдена в каталоге.',
  'newGame.blocked.unknownBlack': 'Модель для чёрных не найдена в каталоге.',

  'model.noKey': 'ключ не задан',
  'model.noKeyTitle': 'Ключ провайдера не задан',
  'model.none': '—',

  'status.live': 'В ЭФИРЕ',
  'status.finished': 'Завершена',
  'status.error': 'Ошибка',
  'status.aborted': 'Прервана',

  'time.justNow': 'только что',
  'time.minutesAgo': '{count} мин назад',
  'time.today': 'сегодня {time}',
  'time.date': '{date}',

  'state.loading': 'Загрузка',

  'error.network': 'Сервер недоступен — проверьте, что бэкенд запущен.',
  'error.notFound': 'Не найдено.',
  'error.forbidden': 'Нет доступа: откройте сайт по ссылке с токеном.',
  'error.generic': 'Ошибка запроса ({status}).',

  'wip.eyebrow': 'Экран в работе',
  'wip.game.title': 'Партия {id}',
  'wip.game.note': 'Живой просмотр и отчёт приедут отдельными задачами плана.',
  'wip.tournaments.title': 'Турниры',
  'wip.tournaments.note': 'Список турниров приедет отдельной задачей плана.',
  'wip.newTournament.title': 'Новый турнир',
  'wip.newTournament.note': 'Создание турнира приедет отдельной задачей плана.',
  'wip.tournament.title': 'Турнир {id}',
  'wip.tournament.note': 'Таблица и расписание приедут отдельной задачей плана.',
  'notFound.eyebrow': '404',
  'notFound.title': 'Страница не найдена',
  'notFound.note': 'Проверьте адрес — такого экрана нет.',
}

export const EN = {
  'lang.name': 'English',
  'lang.switch': 'Interface language',

  'nav.home': 'Arena',
  'nav.newGame': 'New game',
  'nav.archive': 'Games',
  'nav.tournaments': 'Tournaments',
  'action.start': '＋ Start',
  'action.cancel': 'Cancel',
  'action.refresh': '↻ Refresh',
  'action.home': '← Home',
  'theme.toDark': 'Dark theme',
  'theme.toLight': 'Light theme',

  'footer.stack': 'LLM Chess Arena · FastAPI · python-chess · Stockfish',
  'footer.disclaimer': 'Games are real model API calls: starting one spends money on your keys.',

  'home.eyebrow': 'A chess arena for language models',
  'home.title': 'Arena',
  'home.lead':
    'Start a game between two models or open a finished one — with Stockfish move-quality analysis, the models’ thoughts and the plan behind every move.',
  'home.cta.play': 'Start a game',
  'home.cta.archive': 'Game archive',
  'home.cta.tournaments': 'Tournaments',
  'home.feature.analysis.title': 'Move-quality analysis',
  'home.feature.analysis.body':
    'Stockfish grades every move from brilliant to blunder, with the evaluation in centipawns.',
  'home.feature.hints.title': 'Engine hints',
  'home.feature.hints.body':
    'Each model gets three hints per game — the report shows when it reached for one.',
  'home.feature.plan.title': 'Thoughts and plan',
  'home.feature.plan.body':
    'The model explains each move and keeps a private plan — all of it is stored in the report.',
  'home.recent.title': 'Recent games',
  'home.recent.all': 'All games →',
  'home.recent.empty.title': 'No games yet',
  'home.recent.empty.body': 'Start the first one — it will show up here and in the archive.',

  'archive.eyebrow': 'Archive',
  'archive.title': 'All games',
  'archive.loading': 'Loading…',
  'archive.count': { one: '{count} game', other: '{count} games' },
  'archive.liveSuffix': ' · {count} live',
  'archive.empty.title': 'No games yet',
  'archive.empty.body': 'Start the first game — it appears here as soon as it launches.',

  'newGame.eyebrow': 'Game setup',
  'newGame.title': 'New game',
  'newGame.lead':
    'Pick a model for each side — the same model may play itself. There is no time control; python-chess judges move legality.',
  'newGame.white': '♔ White',
  'newGame.black': '♚ Black',
  'newGame.whiteShort': '♔ WHITE',
  'newGame.blackShort': '♚ BLACK',
  'newGame.cost':
    'Starting a game makes real API calls for both models, spending money on your keys. Stockfish hints (up to 3 per side) and move-quality analysis switch on automatically when the engine is available.',
  'newGame.language': 'The models will reason and keep their plan in English — the interface language.',
  'newGame.start': '▶ Start game',
  'newGame.starting': 'Starting…',
  'newGame.blocked.noModels': 'No models available: no API key is configured (see .env).',
  'newGame.blocked.notPicked': 'Pick a model for both sides.',
  'newGame.blocked.noKeyWhite': 'The model picked for White has no key and is unavailable.',
  'newGame.blocked.noKeyBlack': 'The model picked for Black has no key and is unavailable.',
  'newGame.blocked.unknownWhite': 'The model picked for White is not in the catalog.',
  'newGame.blocked.unknownBlack': 'The model picked for Black is not in the catalog.',

  'model.noKey': 'no key',
  'model.noKeyTitle': 'Provider key is not configured',
  'model.none': '—',

  'status.live': 'LIVE',
  'status.finished': 'Finished',
  'status.error': 'Error',
  'status.aborted': 'Aborted',

  'time.justNow': 'just now',
  'time.minutesAgo': '{count} min ago',
  'time.today': 'today {time}',
  'time.date': '{date}',

  'state.loading': 'Loading',

  'error.network': 'Backend is unreachable — check that the server is running.',
  'error.notFound': 'Not found.',
  'error.forbidden': 'No access: open the site through the link with a token.',
  'error.generic': 'Request failed ({status}).',

  'wip.eyebrow': 'Screen in progress',
  'wip.game.title': 'Game {id}',
  'wip.game.note': 'Live view and report arrive in later tasks of the plan.',
  'wip.tournaments.title': 'Tournaments',
  'wip.tournaments.note': 'The tournament list arrives in a later task of the plan.',
  'wip.newTournament.title': 'New tournament',
  'wip.newTournament.note': 'Tournament creation arrives in a later task of the plan.',
  'wip.tournament.title': 'Tournament {id}',
  'wip.tournament.note': 'Standings and schedule arrive in a later task of the plan.',
  'notFound.eyebrow': '404',
  'notFound.title': 'Page not found',
  'notFound.note': 'Check the address — there is no such screen.',
}

export const MESSAGES = { ru: RU, en: EN }
