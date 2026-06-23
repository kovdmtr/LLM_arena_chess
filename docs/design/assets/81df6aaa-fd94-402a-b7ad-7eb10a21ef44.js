/* screens_home.jsx — Home + New Game */
const { MODELS: HM_MODELS, FAMILIES: HM_FAM, PROVIDERS: HM_PROV, byId: HM_BY, GAME: HM_GAME, RECENT: HM_RECENT, LEADERBOARD: HM_LB } = window.ARENA;

function StatStrip() {
  const items = [
    ['1 248', 'партий сыграно'],
    ['14', 'моделей в арене'],
    ['7', 'классов оценки'],
    ['Stockfish', 'судит качество'],
  ];
  return (
    <div className="row gap-6" style={{ flexWrap: 'wrap', marginTop: 38, paddingTop: 26, borderTop: '1px solid var(--line)' }}>
      {items.map(([n, l]) => (
        <div className="col" key={l} style={{ minWidth: 130 }}>
          <span className="serif" style={{ fontSize: 30, fontWeight: 700 }}>{n}</span>
          <span style={{ color: 'var(--muted)', fontSize: 13.5 }}>{l}</span>
        </div>
      ))}
    </div>
  );
}

function LiveTeaser({ go }) {
  const positions = buildPositions(HM_GAME.moves);
  const ply = 15; // after O-O — sharp position
  const last = HM_GAME.moves[ply - 1];
  const shown = HM_GAME.moves.slice(Math.max(0, ply - 5), ply);
  return (
    <div className="card" style={{ padding: 14, width: 320, flex: 'none' }}>
      <div className="row gap-2" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <span className="badge badge-live"><span className="dot"></span> В ЭФИРЕ</span>
        <span className="mono" style={{ fontSize: 11.5, color: 'var(--faint)' }}>{HM_GAME.opening}</span>
      </div>
      <div className="row gap-3" style={{ alignItems: 'stretch' }}>
        <div style={{ width: 200 }}><Board position={positions[ply]} lastMove={last} coords={false} /></div>
        <EvalBar cp={last.eval} />
      </div>
      <div className="col gap-2" style={{ marginTop: 12 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}><ModelChip id={HM_GAME.white} sub size={22} /><span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>белые</span></div>
        <div className="row" style={{ justifyContent: 'space-between' }}><ModelChip id={HM_GAME.black} sub size={22} /><span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>чёрные</span></div>
      </div>
      <div className="moves" style={{ marginTop: 10, background: 'var(--paper)', borderRadius: 8, padding: '4px 0', maxHeight: 58, overflow: 'hidden' }}>
        {shown.slice(-2).map((m, i) => {
          const realIdx = ply - 2 + i;
          const moveNo = Math.floor(realIdx / 2) + 1;
          return (
            <div key={i} style={{ padding: '2px 12px', color: 'var(--ink-2)' }}>
              <span style={{ color: 'var(--faint)' }}>{m.side === 'w' ? moveNo + '.' : moveNo + '…'} </span>
              {m.san}<Glyph cls={m.cls} />
            </div>
          );
        })}
      </div>
      <button className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: 10 }} onClick={() => go('live', HM_GAME)}>Смотреть партию →</button>
    </div>
  );
}

function FeatureCard({ icon, title, body }) {
  return (
    <div className="card" style={{ padding: '22px 22px 24px' }}>
      <div style={{ fontSize: 22, marginBottom: 12 }} className="mono">{icon}</div>
      <h3 style={{ fontSize: 19, marginBottom: 7 }}>{title}</h3>
      <p style={{ margin: 0, color: 'var(--muted)', fontSize: 14.5, lineHeight: 1.55 }}>{body}</p>
    </div>
  );
}

function Home({ go }) {
  return (
    <div className="fade-in">
      <section className="wrap" style={{ paddingTop: 28, paddingBottom: 24 }}>
        <div className="row gap-6" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 340 }}>
            <span className="eyebrow">Шахматная арена для языковых моделей</span>
            <h1 style={{ fontSize: 'clamp(30px, 3.4vw, 42px)', marginTop: 12, lineHeight: 1.1 }}>Арена</h1>
            <p style={{ fontSize: 16, color: 'var(--ink-2)', maxWidth: 440, marginTop: 12, lineHeight: 1.55 }}>
              Запустите партию двух моделей или откройте сыгранную — с разбором качества ходов от Stockfish.
            </p>
            <div className="row gap-3" style={{ marginTop: 22 }}>
              <button className="btn btn-primary btn-lg" onClick={() => go('new')}>Запустить партию</button>
              <button className="btn btn-ghost btn-lg" onClick={() => go('report', HM_GAME)}>Открыть пример</button>
            </div>
          </div>
          <LiveTeaser go={go} />
        </div>
      </section>

      <section className="wrap" style={{ paddingTop: 8, paddingBottom: 56 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <h2 style={{ fontSize: 24 }}>Последние партии</h2>
          <button className="btn btn-quiet btn-sm" onClick={() => go('archive')}>Все партии →</button>
        </div>
        <div className="col gap-2">
          {HM_RECENT.map(g => <GameRow key={g.id} g={g} go={go} />)}
        </div>
      </section>
    </div>
  );
}

/* ---------------- New Game ---------------- */
function ModelPick({ value, onPick }) {
  const [open, setOpen] = React.useState(false);
  const cur = HM_BY[value];
  const fam = HM_FAM.find(f => f.family === cur.family);
  const pickFamily = (f) => {
    setOpen(false);
    // keep same version label if the new family has it, else first version
    const same = f.versions.find(v => v.version === cur.version);
    onPick((same || f.versions[0]).id);
  };
  return (
    <div className="col gap-2">
      {/* family dropdown */}
      <div style={{ position: 'relative' }}>
        <button onClick={() => setOpen(o => !o)} style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left', cursor: 'pointer',
          background: 'var(--card)', border: '1.5px solid ' + (open ? 'var(--green)' : 'var(--line-2)'),
          borderRadius: 10, padding: '11px 13px', transition: 'border-color .12s',
        }}>
          <Avatar id={cur.id} size={28} />
          <span style={{ flex: 1, fontWeight: 700, fontSize: 15 }}>{cur.family}</span>
          <span style={{ fontSize: 11, color: 'var(--faint)' }}>{HM_PROV[cur.provider].label}</span>
          <span style={{ fontSize: 11, color: 'var(--muted)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .12s' }}>▾</span>
        </button>
        {open && (
          <div className="card" style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, padding: 5, boxShadow: 'var(--shadow-lg)', zIndex: 40, maxHeight: 320, overflowY: 'auto' }} onMouseLeave={() => setOpen(false)}>
            {HM_FAM.map(f => {
              const on = f.family === cur.family;
              return (
                <button key={f.family} onClick={() => pickFamily(f)} style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left', cursor: 'pointer',
                  background: on ? 'var(--green-soft)' : 'transparent', border: 0, borderRadius: 8, padding: '9px 10px',
                }}>
                  <Avatar id={f.versions[0].id} size={24} />
                  <span style={{ flex: 1, fontWeight: 650, fontSize: 14 }}>{f.family}</span>
                  <span style={{ fontSize: 11, color: 'var(--faint)' }}>{f.versions.length > 1 ? f.versions.length + ' версии' : '1 версия'}</span>
                  {on && <span style={{ color: 'var(--green)', fontWeight: 800 }}>✓</span>}
                </button>
              );
            })}
          </div>
        )}
      </div>
      {/* version selector */}
      {fam.versions.length > 1 ? (
        <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
          {fam.versions.map(v => {
            const on = v.id === value;
            return (
              <button key={v.id} onClick={() => onPick(v.id)} style={{
                cursor: 'pointer', fontWeight: 700, fontSize: 12.5, padding: '6px 12px', borderRadius: 8,
                background: on ? 'var(--ink)' : 'var(--card)', color: on ? 'var(--card)' : 'var(--ink-2)',
                border: '1.5px solid ' + (on ? 'var(--ink)' : 'var(--line-2)'), transition: 'all .12s',
              }}>{v.version}</button>
            );
          })}
        </div>
      ) : (
        <span style={{ fontSize: 12, color: 'var(--faint)', paddingLeft: 2 }}>версия {fam.versions[0].version} · единственная</span>
      )}
    </div>
  );
}

function Segmented({ value, onChange, options, disabled }) {
  return (
    <div className="row" style={{ background: 'var(--paper-2)', borderRadius: 9, padding: 3, gap: 3, alignSelf: 'flex-start' }}>
      {options.map(([v, label]) => {
        const on = value === v;
        return (
          <button key={v} disabled={disabled} onClick={() => !disabled && onChange(v)} style={{
            border: 0, cursor: disabled ? 'default' : 'pointer', fontWeight: 700, fontSize: 12.5, padding: '6px 13px', borderRadius: 7,
            background: on ? 'var(--card)' : 'transparent', color: on ? 'var(--ink)' : 'var(--muted)', boxShadow: on ? 'var(--shadow-sm)' : 'none',
          }}>{label}</button>
        );
      })}
    </div>
  );
}

function ModeSelect({ model, value, onChange }) {
  const canThink = HM_BY[model] && HM_BY[model].think;
  if (!canThink) {
    return (
      <div className="row gap-3" style={{ alignItems: 'center' }}>
        <Segmented value="fast" options={[['fast', 'Быстрая']]} disabled />
        <span style={{ fontSize: 12, color: 'var(--faint)' }}>модель без режима размышления</span>
      </div>
    );
  }
  return (
    <div className="row gap-3" style={{ alignItems: 'center' }}>
      <Segmented value={value} onChange={onChange} options={[['fast', 'Быстрая'], ['think', 'Думающая']]} />
      <span style={{ fontSize: 12, color: 'var(--faint)' }}>{value === 'think' ? 'глубже · дороже · медленнее' : 'дешевле · быстрее'}</span>
    </div>
  );
}

function ModeBadge({ mode }) {
  return <span className="badge" style={{ fontSize: 10.5, marginTop: 4 }}>{mode === 'think' ? 'Думающая' : 'Быстрая'}</span>;
}

function Toggle({ on, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: 44, height: 26, borderRadius: 999, border: 0, cursor: 'pointer', padding: 3, flex: 'none',
      background: on ? 'var(--green)' : 'var(--line-2)', transition: 'background .15s',
    }}>
      <span style={{ display: 'block', width: 20, height: 20, borderRadius: 999, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,.2)', transform: on ? 'translateX(18px)' : 'none', transition: 'transform .15s' }}></span>
    </button>
  );
}

function NewGame({ go }) {
  const [white, setWhite] = React.useState('claude-opus-4-5');
  const [black, setBlack] = React.useState('gpt-5.1');
  const [whiteMode, setWhiteMode] = React.useState('think');
  const [blackMode, setBlackMode] = React.useState('think');
  const [hints, setHints] = React.useState(true);
  const [reason, setReason] = React.useState(true);
  const effW = HM_BY[white].think ? whiteMode : 'fast';
  const effB = HM_BY[black].think ? blackMode : 'fast';
  const ready = !!(white && black);
  const start = () => go('live', { ...HM_GAME, white, black, whiteMode: effW, blackMode: effB });
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64, maxWidth: 920 }}>
      <span className="eyebrow">Настройка партии</span>
      <h1 style={{ fontSize: 36, marginTop: 12, marginBottom: 8 }}>Новая партия</h1>
      <p style={{ color: 'var(--muted)', marginTop: 0, maxWidth: 560 }}>Выберите модели для обеих сторон. Можно поставить одну и ту же модель против себя самой. Партия идёт без контроля времени; легальность ходов судит python-chess.</p>

      {/* matchup preview */}
      <div className="card" style={{ padding: '18px 22px', margin: '24px 0', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 28 }}>
        <div className="col" style={{ alignItems: 'flex-end', flex: 1 }}><ModelChip id={white} size={30} /><div className="row gap-2" style={{ marginTop: 5, alignItems: 'center' }}><ModeBadge mode={effW} /><span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>БЕЛЫЕ</span></div></div>
        <span className="serif" style={{ fontSize: 30, fontWeight: 800, color: 'var(--faint)', fontStyle: 'italic' }}>vs</span>
        <div className="col" style={{ alignItems: 'flex-start', flex: 1 }}><ModelChip id={black} size={30} /><div className="row gap-2" style={{ marginTop: 5, alignItems: 'center' }}><span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>ЧЁРНЫЕ</span><ModeBadge mode={effB} /></div></div>
      </div>

      <div className="row gap-6" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div className="field" style={{ flex: 1, minWidth: 300 }}>
          <label>♔ Белые</label>
          <ModeSelect model={white} value={whiteMode} onChange={setWhiteMode} />
          <ModelPick value={white} onPick={setWhite} />
        </div>
        <div className="field" style={{ flex: 1, minWidth: 300 }}>
          <label>♚ Чёрные</label>
          <ModeSelect model={black} value={blackMode} onChange={setBlackMode} />
          <ModelPick value={black} onPick={setBlack} />
        </div>
      </div>

      <div className="card" style={{ padding: '6px 20px', marginTop: 24 }}>
        <div className="row" style={{ justifyContent: 'space-between', padding: '14px 0', borderBottom: '1px solid var(--line)' }}>
          <div className="col"><span style={{ fontWeight: 700 }}>Подсказки Stockfish</span><span style={{ fontSize: 13, color: 'var(--muted)' }}>До 3 на сторону за партию</span></div>
          <Toggle on={hints} onClick={() => setHints(!hints)} />
        </div>
        <div className="row" style={{ justifyContent: 'space-between', padding: '14px 0' }}>
          <div className="col"><span style={{ fontWeight: 700 }}>Показывать рассуждения</span><span style={{ fontSize: 13, color: 'var(--muted)' }}>Транслировать мысли модели по ходу партии</span></div>
          <Toggle on={reason} onClick={() => setReason(!reason)} />
        </div>
      </div>

      <div className="row gap-3" style={{ marginTop: 28 }}>
        <button className="btn btn-primary btn-lg" disabled={!ready} onClick={start}>▶ Запустить партию</button>
        <button className="btn btn-quiet btn-lg" onClick={() => go('home')}>Отмена</button>
      </div>
    </div>
  );
}

Object.assign(window, { Home, NewGame });
