/* components.jsx — shared UI pieces */
const { PROVIDERS, byId, CLS_META } = window.ARENA;

function Avatar({ id, size = 26 }) {
  const m = byId[id]; const p = PROVIDERS[m.provider];
  return <span className="av" style={{ background: p.color, width: size, height: size, fontSize: size * 0.42 }}>{m.tag}</span>;
}

function ModelChip({ id, sub, size = 26 }) {
  const m = byId[id]; const p = PROVIDERS[m.provider];
  return (
    <span className="mchip">
      <Avatar id={id} size={size} />
      <span className="col" style={{ lineHeight: 1.15 }}>
        <span style={{ fontSize: 14.5, whiteSpace: 'nowrap' }}>{m.name}</span>
        {sub && <span style={{ fontWeight: 500, fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{sub || p.label}</span>}
      </span>
    </span>
  );
}

function Glyph({ cls }) {
  const meta = CLS_META[cls];
  if (!meta || !meta.glyph) return null;
  return <span className="glyph" style={{ color: meta.color }}>{meta.glyph}</span>;
}

function Header({ view, go, user, onLogout }) {
  const [menu, setMenu] = React.useState(false);
  const tabs = [
    ['home', 'Арена'],
    ['new', 'Новая партия'],
    ['archive', 'Партии'],
    ['tournaments', 'Турниры'],
    ['leaderboard', 'Рейтинг'],
  ];
  return (
    <header className="hdr">
      <div className="wrap hdr-in">
        <div className="brand" onClick={() => go('home')}>
          <span className="brand-mark"><i>♞</i><i></i><i></i><i></i></span>
          <span className="brand-name">LLM&nbsp;Chess&nbsp;<b>Arena</b></span>
        </div>
        <nav className="nav">
          {tabs.map(([k, label]) => (
            <button key={k} className={'nav-link' + (view === k ? ' active' : '')} onClick={() => go(k)}>{label}</button>
          ))}
        </nav>
        <span className="hdr-spacer"></span>
        <button className="btn btn-primary btn-sm" onClick={() => go('new')}>＋ Запустить</button>
        {user ? (
          <div style={{ position: 'relative' }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setMenu(m => !m)} style={{ gap: 8, paddingLeft: 8 }}>
              <span style={{ width: 26, height: 26, borderRadius: 999, background: 'var(--green)', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 13 }}>{user.name[0].toUpperCase()}</span>
              <span style={{ maxWidth: 110, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.name}</span>
              <span style={{ fontSize: 10, color: 'var(--muted)' }}>▾</span>
            </button>
            {menu && (
              <div className="card" style={{ position: 'absolute', right: 0, top: 'calc(100% + 8px)', width: 200, padding: 6, boxShadow: 'var(--shadow-lg)', zIndex: 50 }} onMouseLeave={() => setMenu(false)}>
                <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--line)', marginBottom: 4 }}><div style={{ fontWeight: 700, fontSize: 13.5 }}>{user.name}</div><div style={{ fontSize: 12, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div></div>
                <button className="nav-link" style={{ width: '100%', textAlign: 'left' }} onClick={() => { setMenu(false); go('profile'); }}>Профиль</button>
                <button className="nav-link" style={{ width: '100%', textAlign: 'left' }} onClick={() => { setMenu(false); go('archive'); }}>Мои партии</button>
                <button className="nav-link" style={{ width: '100%', textAlign: 'left', color: 'var(--c-mistake)' }} onClick={() => { setMenu(false); onLogout(); }}>Выйти</button>
              </div>
            )}
          </div>
        ) : (
          <button className="btn btn-ghost btn-sm" onClick={() => go('auth')}>Войти</button>
        )}
      </div>
    </header>
  );
}

function ResultBadge({ result }) {
  const map = { '1–0': ['#fff', 'var(--ink)'], '0–1': ['var(--ink)', '#fff'], '½–½': ['var(--paper-2)', 'var(--muted)'] };
  const [bg, fg] = map[result] || map['½–½'];
  return <span className="mono tnum" style={{ fontWeight: 600, padding: '3px 10px', borderRadius: 6, background: bg, color: fg, border: '1px solid var(--line)', fontSize: 13 }}>{result}</span>;
}

function GameRow({ g, go }) {
  return (
    <button className="row gap-3" onClick={() => go(g.status === 'finished' ? 'report' : 'live', g)}
      style={{ width: '100%', textAlign: 'left', background: 'var(--card)', border: '1px solid var(--line)', borderRadius: 12, padding: '12px 16px', cursor: 'pointer', alignItems: 'center' }}>
      <div className="col" style={{ flex: 1, minWidth: 0, gap: 3, overflow: 'hidden' }}>
        <div className="row gap-2" style={{ alignItems: 'center', minWidth: 0, overflow: 'hidden' }}>
          <ModelChip id={g.white} size={22} />
          <span className="mono" style={{ color: 'var(--faint)', fontSize: 11 }}>vs</span>
          <ModelChip id={g.black} size={22} />
        </div>
        <div className="row gap-2" style={{ alignItems: 'center', minWidth: 0 }}>
          <span style={{ color: 'var(--muted)', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>{g.opening} · {g.moves} ходов</span>
          <span style={{ color: 'var(--faint)', fontSize: 12, whiteSpace: 'nowrap', marginLeft: 'auto', flex: 'none' }}>{g.when}</span>
        </div>
      </div>
      <ResultBadge result={g.result} />
    </button>
  );
}

Object.assign(window, { Avatar, ModelChip, Glyph, Header, ResultBadge, GameRow });
