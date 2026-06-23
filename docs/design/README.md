# docs/design — импортированный дизайн «LLM Chess Arena (standalone)»

Справочные материалы дизайна для будущего редизайна фронтенда. **Это только
референс — рабочий фронтенд (`src/arena/web/`) не затронут.**

Источник: Claude Design, проект `576bdb4c-2903-4267-84b8-d86505e53e56`,
файл `LLM Chess Arena (standalone).html` (self-contained React-SPA: React UMD +
in-browser Babel, «тёплый деревянный» стиль). Bundle был запакован (gzip+base64);
здесь — распакованные исходники.

## Файлы

| Файл | Что внутри |
|------|-----------|
| `standalone-template.html` | Каркас страницы + **весь CSS** дизайн-системы (токены `:root`, доска, бейджи, кнопки, таблицы, move-list) + корневой `App` с роутингом по экранам (`home/new/live/report/archive/tournaments/leaderboard/auth/profile`). |
| `assets/51e2d313-*.js` | `window.ARENA` — данные-моки: каталог моделей (с семейством/режимом think-flash), пример партии (ходы `{san,from,to,cls,eval,r}`), архив, рейтинг (Elo), турнир, `CLS_META` (7 классов оценок). |
| `assets/d1522cd4-*.js` | `Board` (рендер доски на клиенте из `board[rank][file]`), `applyMove`/`buildPositions`, `EvalBar`. |
| `assets/793a14fd-*.js` | Общие компоненты: `Avatar`, `ModelChip`, `Glyph`, `Header` (навигация + меню пользователя), `ResultBadge`, `GameRow`. |
| `assets/81df6aaa-*.js` | Экраны `Home` (+ live-тизер, фичи) и `NewGame` (выбор семейства/версии модели, режим think/flash, тоглы подсказок/рассуждений). |
| `assets/4485d8aa-*.js` | Экраны `Live`, `Report` (плеер + точность/классы), `Archive`, `Tournaments` (таблица + расписание), `Leaderboard`. |
| `assets/3aff7dd1-*.js` | Экраны `Auth` (вход/регистрация) и `Profile` (настройки: язык, свои API-ключи; «Мои партии»). |

> Имена `assets/*.js` — исходные UUID ассетов bundle (на них ссылается
> `standalone-template.html`). React/ReactDOM/Babel-standalone из бандла **не
> сохранены** (это обычные CDN-библиотеки, не дизайн).

## Связанные документы

- `docs/DESIGN_BRIEF.md` — продуктовый бриф того же дизайна (экраны, палитра тем,
  компоненты, новые фичи).
- `docs/FRONTEND.md` — карта текущего фронта и контракт бэкенда; раздел «Вариант B»
  описывает, как этот SPA подключить к `/api/*` без переписывания бэкенда.
