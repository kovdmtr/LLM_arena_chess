/* LLM Chess Arena — sample data (plain JS, no JSX) */
(function () {
  const PROVIDERS = {
    anthropic: { label: 'Anthropic', color: 'var(--p-anthropic)', short: 'A' },
    openai:    { label: 'OpenAI',    color: 'var(--p-openai)',    short: 'O' },
    google:    { label: 'Google',    color: 'var(--p-google)',    short: 'G' },
  };

  const MODELS = [
    { id: 'claude-opus-4-5',   provider: 'anthropic', name: 'Claude Opus 4.5',   tag: 'OP',  think: true,  family: 'Claude Opus',  version: '4.5' },
    { id: 'claude-opus-4-1',   provider: 'anthropic', name: 'Claude Opus 4.1',   tag: 'O41', think: true,  family: 'Claude Opus',  version: '4.1' },
    { id: 'claude-sonnet-4-5', provider: 'anthropic', name: 'Claude Sonnet 4.5', tag: 'SO',  think: true,  family: 'Claude Sonnet', version: '4.5' },
    { id: 'claude-3-7-sonnet', provider: 'anthropic', name: 'Claude 3.7 Sonnet', tag: '37',  think: true,  family: 'Claude Sonnet', version: '3.7' },
    { id: 'claude-haiku-4-5',  provider: 'anthropic', name: 'Claude Haiku 4.5',  tag: 'HA',  think: false, family: 'Claude Haiku',  version: '4.5' },
    { id: 'gpt-5.1',           provider: 'openai',    name: 'GPT-5.1',           tag: '5.1', think: true,  family: 'GPT-5',        version: '5.1' },
    { id: 'gpt-5',             provider: 'openai',    name: 'GPT-5',             tag: '5',   think: true,  family: 'GPT-5',        version: '5.0' },
    { id: 'gpt-5-mini',        provider: 'openai',    name: 'GPT-5 mini',        tag: 'mi',  think: false, family: 'GPT-5',        version: 'mini' },
    { id: 'gpt-4.1',           provider: 'openai',    name: 'GPT-4.1',           tag: '4.1', think: false, family: 'GPT-4',        version: '4.1' },
    { id: 'o4-mini',           provider: 'openai',    name: 'o4-mini',           tag: 'o4',  think: true,  family: 'o4',           version: 'mini' },
    { id: 'gemini-3-pro',      provider: 'google',    name: 'Gemini 3 Pro',      tag: '3P',  think: true,  family: 'Gemini 3',     version: 'Pro' },
    { id: 'gemini-3-flash',    provider: 'google',    name: 'Gemini 3 Flash',    tag: '3F',  think: false, family: 'Gemini 3',     version: 'Flash' },
    { id: 'gemini-2.5-pro',    provider: 'google',    name: 'Gemini 2.5 Pro',    tag: '25P', think: true,  family: 'Gemini 2.5',   version: 'Pro' },
    { id: 'gemini-2.5-flash',  provider: 'google',    name: 'Gemini 2.5 Flash',  tag: 'Fl',  think: false, family: 'Gemini 2.5',   version: 'Flash' },
  ];
  const byId = {}; MODELS.forEach(m => byId[m.id] = m);

  // families: ordered list of { family, provider, versions: [model,...] }
  const FAMILIES = [];
  MODELS.forEach(m => {
    let f = FAMILIES.find(x => x.family === m.family);
    if (!f) { f = { family: m.family, provider: m.provider, versions: [] }; FAMILIES.push(f); }
    f.versions.push(m);
  });

  // --- sample game: Giuoco Piano line, White = Opus 4.5, Black = GPT-5.1 ---
  // each move: san, from, to (algebraic squares), side, class, reasoning, eval (cp, white POV after move)
  const GAME_MOVES = [
    { san: 'e4',   from: 'e2', to: 'e4', side: 'w', cls: 'book', eval: 25,
      r: 'Открываю центр. e4 — самый принципиальный первый ход: захват центра и линии для слона и ферзя.' },
    { san: 'e5',   from: 'e7', to: 'e5', side: 'b', cls: 'book', eval: 20,
      r: 'Симметричный ответ. Борюсь за центр на равных и сохраняю гибкость развития.' },
    { san: 'Nf3',  from: 'g1', to: 'f3', side: 'w', cls: 'book', eval: 28,
      r: 'Развиваю коня с нападением на пешку e5. Естественное и сильное продолжение.' },
    { san: 'Nc6',  from: 'b8', to: 'c6', side: 'b', cls: 'book', eval: 22,
      r: 'Защищаю e5 и развиваю фигуру. Классическая итальянская расстановка.' },
    { san: 'Bc4',  from: 'f1', to: 'c4', side: 'w', cls: 'book', eval: 30,
      r: 'Итальянская партия. Слон нацелен на слабый пункт f7.' },
    { san: 'Bc5',  from: 'f8', to: 'c5', side: 'b', cls: 'book', eval: 24,
      r: 'Giuoco Piano. Зеркально развиваю слона, держу симметрию и давление на f2.' },
    { san: 'c3',   from: 'c2', to: 'c3', side: 'w', cls: 'good', eval: 36,
      r: 'Готовлю d4 и центр из двух пешек. Чуть ослабляю поле d3, но план перевешивает.' },
    { san: 'Nf6',  from: 'g8', to: 'f6', side: 'b', cls: 'good', eval: 28,
      r: 'Развиваю коня и нападаю на e4. Создаю встречную игру до того, как соперник построит центр.' },
    { san: 'd4',   from: 'd2', to: 'd4', side: 'w', cls: 'good', eval: 40,
      r: 'Бью в центр. Открываю позицию, пока мой развит лучше.' },
    { san: 'exd4', from: 'e5', to: 'd4', side: 'b', cls: 'normal', eval: 35,
      r: 'Беру пешку — иначе d4-d5 зажмёт мои фигуры. Принимаю вызов в центре.' },
    { san: 'cxd4', from: 'c3', to: 'd4', side: 'w', cls: 'good', eval: 42,
      r: 'Перекрытие. Получаю мощный пешечный центр e4+d4 и линию c для ладьи.' },
    { san: 'Bb4+', from: 'c5', to: 'b4', side: 'b', cls: 'interesting', eval: 30,
      r: 'Шах с темпом. Заставляю определиться с прикрытием короля прежде, чем центр станет грозным.' },
    { san: 'Nc3',  from: 'b1', to: 'c3', side: 'w', cls: 'good', eval: 38,
      r: 'Перекрываю шах развивающим ходом. Жертвую пешку e4 ради опережения в развитии — гамбит Мёллера.' },
    { san: 'Nxe4', from: 'f6', to: 'e4', side: 'b', cls: 'interesting', eval: 30,
      r: 'Принимаю гамбит. Лишняя пешка реальна; теперь точная защита — и перевес мой.' },
    { san: 'O-O',  from: 'e1', to: 'g1', side: 'w', cls: 'brilliant', eval: 55,
      r: 'Рокировка с жертвой! Король в безопасности, ладья выходит на e1 с разящей связкой по линии e. Компенсация с лихвой.' },
    { san: 'Bxc3', from: 'b4', to: 'c3', side: 'b', cls: 'mistake', eval: 110,
      r: 'Беру коня, чтобы упростить... но это раскрывает мою позицию и теряет темп. Недооценил связку по линии e.' },
    { san: 'd5',   from: 'd4', to: 'd5', side: 'w', cls: 'good', eval: 130,
      r: 'Пешка идёт вперёд с нападением на коня c6 и вскрытием диагонали. Инициатива нарастает.' },
    { san: 'Ne5',  from: 'c6', to: 'e5', side: 'b', cls: 'normal', eval: 120,
      r: 'Увожу коня в центр под защиту. Пытаюсь зацепиться, но конь e4 уже под прицелом.' },
    { san: 'Re1',  from: 'f1', to: 'e1', side: 'w', cls: 'good', eval: 165,
      r: 'Ладья на открытую линию — абсолютная связка коня e4 с королём e8. Фигура практически выиграна.' },
    { san: 'd6',   from: 'd7', to: 'd6', side: 'b', cls: 'inaccuracy', eval: 210,
      r: 'Поддерживаю коня e5, но связку по e-линии это не снимает. Позиция трещит.' },
    { san: 'Nxe5', from: 'f3', to: 'e5', side: 'w', cls: 'good', eval: 230,
      r: 'Снимаю защитника. После размена коней связанный конь e4 окончательно повисает.' },
    { san: 'dxe5', from: 'd6', to: 'e5', side: 'b', cls: 'normal', eval: 235,
      r: 'Вынужденно отыгрываю коня. Но открытая e-линия теперь работает против меня.' },
    { san: 'Rxe4+', from: 'e1', to: 'e4', side: 'w', cls: 'good', eval: 600,
      r: 'Забираю связанного коня с шахом. Чистая лишняя фигура — позиция выиграна.' },
  ];

  const GAME = {
    id: 'g_7Q2',
    white: 'claude-opus-4-5',
    black: 'gpt-5.1',
    opening: 'Итальянская партия · Гамбит Мёллера',
    result: '1–0',
    termination: 'Чёрные сдались',
    moves: GAME_MOVES,
    hintsWhite: 0, hintsBlack: 1, hintsMax: 3,
    accW: 94.2, accB: 71.8,
  };

  // recent games for archive / home
  const RECENT = [
    { id: 'g_7Q2', white: 'claude-opus-4-5', black: 'gpt-5.1', result: '1–0', moves: 23, status: 'finished', opening: 'Итальянская партия', when: '12 мин назад' },
    { id: 'g_7P9', white: 'gemini-3-pro', black: 'claude-sonnet-4-5', result: '½–½', moves: 67, status: 'finished', opening: 'Берлинская защита', when: '40 мин назад' },
    { id: 'g_7P1', white: 'gpt-5.1', black: 'gemini-3-pro', result: '0–1', moves: 51, status: 'finished', opening: 'Сицилианская защита', when: '1 ч назад' },
    { id: 'g_7N4', white: 'claude-opus-4-5', black: 'gemini-2.5-flash', result: '1–0', moves: 38, status: 'finished', opening: 'Защита Каро-Канн', when: '2 ч назад' },
    { id: 'g_7N0', white: 'gpt-5-mini', black: 'claude-sonnet-4-5', result: '0–1', moves: 44, status: 'finished', opening: 'Французская защита', when: '3 ч назад' },
  ];

  const LEADERBOARD = [
    { id: 'claude-opus-4-5',   games: 128, w: 81, d: 28, l: 19, score: 95.0, acc: 92.4, elo: 1842 },
    { id: 'gemini-3-pro',      games: 124, w: 72, d: 31, l: 21, score: 87.5, acc: 90.1, elo: 1798 },
    { id: 'gpt-5.1',           games: 131, w: 70, d: 35, l: 26, score: 87.5, acc: 88.7, elo: 1771 },
    { id: 'claude-opus-4-1',   games: 121, w: 64, d: 33, l: 24, score: 80.5, acc: 89.3, elo: 1749 },
    { id: 'gpt-5',             games: 126, w: 63, d: 34, l: 29, score: 80.0, acc: 87.9, elo: 1726 },
    { id: 'gemini-2.5-pro',    games: 118, w: 59, d: 31, l: 28, score: 74.5, acc: 86.8, elo: 1704 },
    { id: 'claude-sonnet-4-5', games: 119, w: 58, d: 33, l: 28, score: 74.5, acc: 85.2, elo: 1693 },
    { id: 'o4-mini',           games: 114, w: 52, d: 30, l: 32, score: 67.0, acc: 84.0, elo: 1651 },
    { id: 'claude-3-7-sonnet', games: 110, w: 47, d: 28, l: 35, score: 61.0, acc: 82.6, elo: 1612 },
    { id: 'gemini-3-flash',    games: 116, w: 48, d: 27, l: 41, score: 61.5, acc: 81.3, elo: 1589 },
    { id: 'gemini-2.5-flash',  games: 112, w: 41, d: 29, l: 42, score: 55.5, acc: 79.4, elo: 1558 },
    { id: 'gpt-4.1',           games: 109, w: 37, d: 26, l: 46, score: 50.0, acc: 77.9, elo: 1531 },
    { id: 'gpt-5-mini',        games: 108, w: 33, d: 27, l: 48, score: 46.5, acc: 76.8, elo: 1502 },
  ];

  const TOURNAMENT = {
    name: 'Round-robin · Июнь 2026',
    format: 'Круговой, 2 круга',
    participants: ['claude-opus-4-5', 'gemini-3-pro', 'gpt-5.1', 'claude-sonnet-4-5'],
    standings: [
      { id: 'claude-opus-4-5',   played: 6, w: 4, d: 2, l: 0, pts: 5.0 },
      { id: 'gemini-3-pro',      played: 6, w: 3, d: 2, l: 1, pts: 4.0 },
      { id: 'gpt-5.1',           played: 6, w: 2, d: 2, l: 2, pts: 3.0 },
      { id: 'claude-sonnet-4-5', played: 6, w: 0, d: 0, l: 6, pts: 0.0 },
    ],
    schedule: [
      { round: 1, white: 'claude-opus-4-5', black: 'gpt-5.1', result: '1–0' },
      { round: 1, white: 'gemini-3-pro', black: 'claude-sonnet-4-5', result: '1–0' },
      { round: 2, white: 'gpt-5.1', black: 'gemini-3-pro', result: '½–½' },
      { round: 2, white: 'claude-sonnet-4-5', black: 'claude-opus-4-5', result: '0–1' },
      { round: 3, white: 'claude-opus-4-5', black: 'gemini-3-pro', result: '—', live: true },
      { round: 3, white: 'gpt-5.1', black: 'claude-sonnet-4-5', result: '—' },
    ],
  };

  const CLS_META = {
    brilliant:   { glyph: '!!', label: 'Блестящий',  color: 'var(--c-brilliant)' },
    good:        { glyph: '!',  label: 'Хороший',     color: 'var(--c-good)' },
    interesting: { glyph: '!?', label: 'Интересный',  color: 'var(--c-interesting)' },
    book:        { glyph: '',   label: 'Теория',      color: 'var(--c-book)' },
    normal:      { glyph: '',   label: 'Обычный',     color: 'var(--muted)' },
    inaccuracy:  { glyph: '?!', label: 'Неточность',  color: 'var(--c-inaccuracy)' },
    mistake:     { glyph: '?',  label: 'Ошибка',      color: 'var(--c-mistake)' },
    blunder:     { glyph: '??', label: 'Зевок',       color: 'var(--c-blunder)' },
  };

  window.ARENA = { PROVIDERS, MODELS, FAMILIES, byId, GAME, RECENT, LEADERBOARD, TOURNAMENT, CLS_META };
})();
