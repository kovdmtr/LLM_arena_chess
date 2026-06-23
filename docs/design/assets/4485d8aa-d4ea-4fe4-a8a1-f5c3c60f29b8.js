/* screens_game.jsx — Live, Report, Archive, Tournaments, Leaderboard */
const { byId: GG_BY, CLS_META: GG_CLS, GAME: GG_GAME, RECENT: GG_RECENT, LEADERBOARD: GG_LB, TOURNAMENT: GG_TOUR } = window.ARENA;

function MoveList({ moves, ply, onJump, height = 360 }) {
  const rows = [];
  for (let i = 0; i < moves.length; i += 2) rows.push([i, moves[i], moves[i + 1]]);
  return (
    <div className="moves scroll" style={{ maxHeight: height, overflow: 'auto' }} ref={el => {
      if (el) { const cur = el.querySelector('.cur'); if (cur) cur.scrollIntoViewIfNeeded ? cur.scrollIntoViewIfNeeded() : null; }
    }}>
      {rows.map(([i, w, b]) => (
        <div className="mv-row" key={i}>
          <span className="mv-num">{i / 2 + 1}.</span>
          <span className={'mv-cell' + (ply - 1 === i ? ' cur' : '')} onClick={() => onJump(i + 1)}>{w.san}<Glyph cls={w.cls} /></span>
          {b
            ? <span className={'mv-cell' + (ply - 1 === i + 1 ? ' cur' : '')} onClick={() => onJump(i + 2)}>{b.san}<Glyph cls={b.cls} /></span>
            : <span></span>}
        </div>
      ))}
    </div>
  );
}

function HintMeter({ id, used, max, side }) {
  return (
    <div className="row gap-2" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
      <ModelChip id={id} sub={side} size={24} />
      <span className="row gap-2" title={'Подсказки Stockfish: ' + used + ' из ' + max}>
        {Array.from({ length: max }).map((_, i) => (
          <span key={i} style={{ width: 9, height: 9, borderRadius: 999, background: i < used ? 'var(--c-brilliant)' : 'var(--line-2)' }}></span>
        ))}
      </span>
    </div>
  );
}

/* ---------------- LIVE ---------------- */
function Live({ game, go }) {
  game = game || GG_GAME;
  const positions = React.useMemo(() => buildPositions(game.moves), [game]);
  const [ply, setPly] = React.useState(0);
  const [playing, setPlaying] = React.useState(true);
  const done = ply >= game.moves.length;

  React.useEffect(() => {
    if (!playing || done) return;
    const t = setTimeout(() => setPly(p => Math.min(p + 1, game.moves.length)), ply === 0 ? 600 : 1700);
    return () => clearTimeout(t);
  }, [ply, playing, done, game]);

  const last = ply > 0 ? game.moves[ply - 1] : null;
  const cp = last ? last.eval : 20;
  const turnWhite = ply % 2 === 0;
  const usedW = game.moves.slice(0, ply).filter(m => m.side === 'w' && m.hint).length;
  const usedB = game.moves.slice(0, ply).filter(m => m.side === 'b' && m.hint).length || (ply >= 18 ? 1 : 0);

  return (
    <div className="wrap fade-in" style={{ paddingTop: 28, paddingBottom: 56 }}>
      <div className="row gap-3" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 18, flexWrap: 'wrap' }}>
        <div className="row gap-3" style={{ alignItems: 'center' }}>
          {done ? <span className="badge badge-done"><span className="dot"></span> ЗАВЕРШЕНО</span> : <span className="badge badge-live"><span className="dot"></span> В ЭФИРЕ</span>}
          <span style={{ color: 'var(--muted)', fontSize: 14 }}>{game.opening}</span>
          <span className="mono" style={{ fontSize: 12, color: 'var(--faint)' }}>#{game.id}</span>
        </div>
        <span style={{ fontWeight: 700, fontSize: 15, whiteSpace: 'nowrap' }}>
          {done ? <span>Итог: <span className="mono">{game.result}</span> · {game.termination}</span>
            : <span style={{ color: 'var(--green-d)' }}>Ход {turnWhite ? 'белых' : 'чёрных'} · {Math.floor(ply / 2) + 1}</span>}
        </span>
      </div>

      <div className="row gap-6" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div className="row gap-3" style={{ flex: '1 1 440px', alignItems: 'stretch', minWidth: 320 }}>
          <EvalBar cp={cp} />
          <div style={{ flex: 1 }}><Board position={positions[ply]} lastMove={last} /></div>
        </div>

        <div className="col gap-4" style={{ width: 360, flex: 'none' }}>
          <div className="card" style={{ padding: 14 }}>
            <div className="col gap-3">
              <HintMeter id={game.white} used={usedW} max={game.hintsMax} side="белые" />
              <div style={{ height: 1, background: 'var(--line)' }}></div>
              <HintMeter id={game.black} used={usedB} max={game.hintsMax} side="чёрные" />
            </div>
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '9px 14px', borderBottom: '1px solid var(--line)', background: 'var(--paper)' }} className="eyebrow">Мысли модели</div>
            <div style={{ padding: '14px 16px', minHeight: 132 }}>
              {last ? (
                <div className="fade-in" key={ply}>
                  <div className="row gap-2" style={{ marginBottom: 8, alignItems: 'center' }}>
                    <ModelChip id={last.side === 'w' ? game.white : game.black} size={22} />
                    <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-2)' }}>
                      {Math.floor((ply - 1) / 2) + 1}{last.side === 'w' ? '.' : '…'} {last.san}<Glyph cls={last.cls} />
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>{last.r}</p>
                </div>
              ) : <p style={{ margin: 0, color: 'var(--faint)', fontStyle: 'italic' }}>Партия начинается…</p>}
            </div>
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '9px 14px', borderBottom: '1px solid var(--line)', background: 'var(--paper)' }} className="eyebrow">Ходы</div>
            <MoveList moves={game.moves} ply={ply} onJump={(p) => { setPlaying(false); setPly(p); }} height={200} />
          </div>

          {done
            ? <button className="btn btn-primary" onClick={() => go('report', game)}>Открыть отчёт с анализом →</button>
            : (
              <div className="row gap-2">
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setPlaying(p => !p)}>{playing ? '❙❙ Пауза' : '▶ Продолжить'}</button>
                <button className="btn btn-quiet" onClick={() => { setPlaying(false); setPly(game.moves.length); }}>В конец ⏭</button>
              </div>
            )}
        </div>
      </div>
    </div>
  );
}

/* ---------------- REPORT ---------------- */
function buildPGN(game) {
  const r = { '1–0': '1-0', '0–1': '0-1', '½–½': '1/2-1/2' }[game.result] || '*';
  let body = '';
  game.moves.forEach((m, i) => { if (i % 2 === 0) body += (i / 2 + 1) + '. '; body += m.san + ' '; });
  return [
    '[Event "LLM Chess Arena"]',
    '[Site "llm-chess-arena"]',
    '[Date "2026.06.21"]',
    `[White "${GG_BY[game.white].name}"]`,
    `[Black "${GG_BY[game.black].name}"]`,
    `[Result "${r}"]`,
    `[Opening "${game.opening}"]`,
    '', body.trim() + ' ' + r, '',
  ].join('\n');
}

function download(name, text) {
  const blob = new Blob([text], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function AccuracyCard({ id, acc, moves, side }) {
  const counts = {};
  moves.filter(m => m.side === side).forEach(m => counts[m.cls] = (counts[m.cls] || 0) + 1);
  const order = ['brilliant', 'good', 'interesting', 'inaccuracy', 'mistake', 'blunder'];
  return (
    <div className="card" style={{ padding: 16, flex: 1, minWidth: 230 }}>
      <ModelChip id={id} sub={side === 'w' ? 'белые' : 'чёрные'} size={26} />
      <div className="row" style={{ alignItems: 'baseline', gap: 8, margin: '14px 0 4px' }}>
        <span className="serif" style={{ fontSize: 40, fontWeight: 700, color: acc >= 85 ? 'var(--green)' : acc >= 75 ? 'var(--c-inaccuracy)' : 'var(--c-mistake)' }}>{acc.toFixed(1)}</span>
        <span style={{ color: 'var(--muted)', fontSize: 14 }}>% точность</span>
      </div>
      <div className="col gap-2" style={{ marginTop: 10 }}>
        {order.map(c => counts[c] ? (
          <div className="row gap-2" key={c} style={{ justifyContent: 'space-between', fontSize: 13 }}>
            <span className="row gap-2"><span className="glyph" style={{ color: GG_CLS[c].color, width: 18 }}>{GG_CLS[c].glyph || '·'}</span><span style={{ color: 'var(--ink-2)' }}>{GG_CLS[c].label}</span></span>
            <span className="mono tnum" style={{ fontWeight: 600 }}>{counts[c]}</span>
          </div>
        ) : null)}
      </div>
    </div>
  );
}

function Report({ game, go }) {
  game = game || GG_GAME;
  const positions = React.useMemo(() => buildPositions(game.moves), [game]);
  const N = game.moves.length;
  const [ply, setPly] = React.useState(N);
  const last = ply > 0 ? game.moves[ply - 1] : null;
  const cp = last ? last.eval : 20;

  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight') setPly(p => Math.min(p + 1, N));
      else if (e.key === 'ArrowLeft') setPly(p => Math.max(p - 1, 0));
      else if (e.key === 'Home') setPly(0);
      else if (e.key === 'End') setPly(N);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [N]);

  const Ctrl = ({ label, onClick, dis }) => <button className="btn btn-ghost btn-sm" disabled={dis} onClick={onClick} style={{ flex: 1 }}>{label}</button>;

  return (
    <div className="wrap fade-in" style={{ paddingTop: 28, paddingBottom: 56 }}>
      <div className="row gap-3" style={{ justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 18, flexWrap: 'wrap' }}>
        <div>
          <span className="eyebrow">Отчёт о партии · #{game.id}</span>
          <div className="row gap-3" style={{ alignItems: 'center', marginTop: 8 }}>
            <ModelChip id={game.white} size={28} />
            <span className="serif" style={{ fontStyle: 'italic', color: 'var(--faint)', fontSize: 20 }}>vs</span>
            <ModelChip id={game.black} size={28} />
            <ResultBadge result={game.result} />
          </div>
          <p style={{ margin: '8px 0 0', color: 'var(--muted)', fontSize: 14 }}>{game.opening} · {game.termination} · {N} полуходов</p>
        </div>
        <div className="row gap-2">
          <button className="btn btn-ghost btn-sm" onClick={() => download(game.id + '.pgn', buildPGN(game))}>↓ PGN</button>
          <button className="btn btn-ghost btn-sm" onClick={() => download(game.id + '.pgn', buildPGN(game))}>↓ HTML-отчёт</button>
        </div>
      </div>

      {/* точность — сверху: слева белые, справа чёрные */}
      <div className="row gap-4" style={{ alignItems: 'stretch', flexWrap: 'wrap', marginBottom: 22 }}>
        <AccuracyCard id={game.white} acc={game.accW} moves={game.moves} side="w" />
        <AccuracyCard id={game.black} acc={game.accB} moves={game.moves} side="b" />
      </div>

      {/* ниже — доска, ходы и мысли модели */}
      <div className="row gap-6" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 440px', minWidth: 320 }}>
          <div className="row gap-3" style={{ alignItems: 'stretch' }}>
            <EvalBar cp={cp} />
            <div style={{ flex: 1 }}><Board position={positions[ply]} lastMove={last} /></div>
          </div>
          <div className="card" style={{ marginTop: 14, padding: '12px 14px' }}>
            <div className="row gap-2" style={{ marginBottom: 10 }}>
              <Ctrl label="⏮" onClick={() => setPly(0)} dis={ply === 0} />
              <Ctrl label="◀ Назад" onClick={() => setPly(p => Math.max(p - 1, 0))} dis={ply === 0} />
              <Ctrl label="Вперёд ▶" onClick={() => setPly(p => Math.min(p + 1, N))} dis={ply === N} />
              <Ctrl label="⏭" onClick={() => setPly(N)} dis={ply === N} />
            </div>
            {last ? (
              <div className="row gap-3" style={{ alignItems: 'flex-start' }}>
                <span className="badge" style={{ background: GG_CLS[last.cls].color, color: '#fff', flex: 'none' }}>
                  {GG_CLS[last.cls].glyph || '·'} {GG_CLS[last.cls].label}
                </span>
                <div className="col" style={{ flex: 1 }}>
                  <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{Math.floor((ply - 1) / 2) + 1}{last.side === 'w' ? '.' : '…'} {last.san} · {last.side === 'w' ? GG_BY[game.white].name : GG_BY[game.black].name}</span>
                  <p style={{ margin: '4px 0 0', fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.55 }}>{last.r}</p>
                </div>
              </div>
            ) : <p style={{ margin: 0, color: 'var(--faint)', fontStyle: 'italic', fontSize: 13.5 }}>Начальная позиция. ← → для перехода по ходам.</p>}
          </div>
        </div>

        <div className="col gap-4" style={{ width: 360, flex: 'none' }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '9px 14px', borderBottom: '1px solid var(--line)', background: 'var(--paper)' }} className="eyebrow">Ходы партии</div>
            <MoveList moves={game.moves} ply={ply} onJump={setPly} height={360} />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------- ARCHIVE ---------------- */
function Archive({ go }) {
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <span className="eyebrow">Архив</span>
      <h1 style={{ fontSize: 36, margin: '12px 0 20px' }}>Все партии</h1>
      <div className="col gap-2">
        {GG_RECENT.concat(GG_RECENT.map(g => ({ ...g, id: g.id + 'b', when: 'вчера' }))).map((g, i) => <GameRow key={i} g={g} go={go} />)}
      </div>
    </div>
  );
}

/* ---------------- TOURNAMENTS ---------------- */
function Tournaments({ go }) {
  const t = GG_TOUR;
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20 }}>
        <div style={{ minWidth: 280 }}><span className="eyebrow">Турнир</span><h1 style={{ fontSize: 32, margin: '12px 0 0' }}>{t.name}</h1><p style={{ margin: '10px 0 0', color: 'var(--muted)' }}>{t.format} · {t.participants.length} участника</p></div>
        <button className="btn btn-primary">＋ Новый турнир</button>
      </div>
      <div className="row gap-6" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: '1 1 420px', overflow: 'hidden', minWidth: 340 }}>
          <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>Таблица</div>
          <table className="tbl">
            <thead><tr><th>#</th><th>Модель</th><th className="num">И</th><th className="num">+</th><th className="num">=</th><th className="num">−</th><th className="num">Очки</th></tr></thead>
            <tbody>
              {t.standings.map((s, i) => (
                <tr key={s.id} className={i === 0 ? 'me' : ''}>
                  <td style={{ color: 'var(--faint)', fontWeight: 700 }}>{i + 1}</td>
                  <td><ModelChip id={s.id} size={24} /></td>
                  <td className="num mono">{s.played}</td>
                  <td className="num mono">{s.w}</td>
                  <td className="num mono">{s.d}</td>
                  <td className="num mono">{s.l}</td>
                  <td className="num mono" style={{ fontWeight: 700 }}>{s.pts.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card" style={{ width: 360, flex: 'none', overflow: 'hidden' }}>
          <div className="eyebrow" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>Расписание</div>
          <div className="col">
            {t.schedule.map((m, i) => (
              <button key={i} className="row gap-2" onClick={() => m.live && go('live', GG_GAME)} style={{ justifyContent: 'space-between', alignItems: 'center', padding: '11px 16px', borderBottom: '1px solid var(--line)', background: 'none', border: '0', borderBottom: '1px solid var(--line)', cursor: m.live ? 'pointer' : 'default', textAlign: 'left' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--faint)', width: 30 }}>Т{m.round}</span>
                <span style={{ flex: 1, fontSize: 13 }}><span style={{ fontWeight: 600 }}>{GG_BY[m.white].name}</span> <span style={{ color: 'var(--faint)' }}>—</span> <span style={{ fontWeight: 600 }}>{GG_BY[m.black].name}</span></span>
                {m.live ? <span className="badge badge-live"><span className="dot"></span></span> : <span className="mono tnum" style={{ fontWeight: 600, fontSize: 13 }}>{m.result}</span>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------- LEADERBOARD ---------------- */
function Leaderboard({ go }) {
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <span className="eyebrow">Рейтинг</span>
      <h1 style={{ fontSize: 36, margin: '12px 0 6px' }}>Таблица моделей</h1>
      <p style={{ margin: '0 0 20px', color: 'var(--muted)' }}>Очки = % набранных из возможных. Точность — средняя по партиям, по Stockfish.</p>
      <div className="card" style={{ overflow: 'hidden' }}>
        <table className="tbl">
          <thead><tr><th>#</th><th>Модель</th><th className="num">Elo</th><th className="num">Партий</th><th className="num">+ / = / −</th><th className="num">Очки %</th><th className="num">Точность</th></tr></thead>
          <tbody>
            {GG_LB.map((row, i) => (
              <tr key={row.id} className={i === 0 ? 'me' : ''}>
                <td style={{ color: 'var(--faint)', fontWeight: 700 }}>{i + 1}</td>
                <td><ModelChip id={row.id} sub size={26} /></td>
                <td className="num mono" style={{ fontWeight: 700, fontSize: 15 }}>{row.elo}</td>
                <td className="num mono">{row.games}</td>
                <td className="num mono">{row.w} / {row.d} / {row.l}</td>
                <td className="num mono">{row.score.toFixed(1)}</td>
                <td className="num mono" style={{ color: row.acc >= 85 ? 'var(--green)' : 'var(--ink-2)', fontWeight: 600 }}>{row.acc.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

Object.assign(window, { Live, Report, Archive, Tournaments, Leaderboard });
