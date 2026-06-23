/* screens_auth.jsx — Authorization (login / register) + Profile */
const { RECENT: AU_RECENT } = window.ARENA;

function TextField({ label, type = 'text', value, onChange, placeholder, autoFocus }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        type={type} value={value} placeholder={placeholder} autoFocus={autoFocus}
        onChange={e => onChange(e.target.value)}
        style={{
          font: 'inherit', fontSize: 15, padding: '11px 13px', borderRadius: 10,
          border: '1.5px solid var(--line-2)', background: 'var(--card)', color: 'var(--ink)', outline: 'none',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--green)'}
        onBlur={e => e.target.style.borderColor = 'var(--line-2)'}
      />
    </div>
  );
}

function Auth({ go, onAuth }) {
  const [tab, setTab] = React.useState('login');
  const [name, setName] = React.useState('');
  const [email, setEmail] = React.useState('');
  const [pass, setPass] = React.useState('');
  const isReg = tab === 'register';
  const valid = email.includes('@') && pass.length >= 4 && (!isReg || name.trim().length >= 2);
  const submit = () => {
    if (!valid) return;
    const nm = isReg ? name.trim() : (email.split('@')[0] || 'Игрок');
    onAuth({ name: nm, email });
    go('home');
  };
  return (
    <div className="wrap fade-in" style={{ paddingTop: 56, paddingBottom: 72, maxWidth: 460 }}>
      <div className="col" style={{ alignItems: 'center', marginBottom: 22 }}>
        <span className="brand-mark" style={{ width: 46, height: 46, borderRadius: 11 }}><i style={{ fontSize: 20 }}>♞</i><i></i><i></i><i></i></span>
        <h1 className="serif" style={{ fontSize: 30, marginTop: 16, lineHeight: 1.1, whiteSpace: 'nowrap' }}>{isReg ? 'Регистрация' : 'Вход в арену'}</h1>
        <p style={{ color: 'var(--muted)', margin: '12px 0 0', textAlign: 'center', fontSize: 14.5 }}>
          {isReg ? 'Создайте аккаунт, чтобы сохранять свои партии и турниры.' : 'Войдите, чтобы вернуться к своим партиям.'}
        </p>
      </div>

      <div className="card" style={{ padding: 22 }}>
        {/* tabs */}
        <div className="row" style={{ background: 'var(--paper-2)', borderRadius: 10, padding: 4, gap: 4, marginBottom: 18 }}>
          {[['login', 'Вход'], ['register', 'Регистрация']].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} style={{
              flex: 1, border: 0, cursor: 'pointer', fontWeight: 700, fontSize: 14, padding: '9px 0', borderRadius: 7,
              background: tab === k ? 'var(--card)' : 'transparent', color: tab === k ? 'var(--ink)' : 'var(--muted)',
              boxShadow: tab === k ? 'var(--shadow-sm)' : 'none',
            }}>{l}</button>
          ))}
        </div>

        <div className="col gap-4">
          {isReg && <TextField label="Имя" value={name} onChange={setName} placeholder="Как вас называть" autoFocus />}
          <TextField label="E-mail" type="email" value={email} onChange={setEmail} placeholder="you@example.com" autoFocus={!isReg} />
          <TextField label="Пароль" type="password" value={pass} onChange={setPass} placeholder="••••••••" />
          {!isReg && <button className="btn btn-quiet btn-sm" style={{ alignSelf: 'flex-start', padding: '4px 0' }}>Забыли пароль?</button>}
          <button className="btn btn-primary btn-lg" disabled={!valid} onClick={submit} style={{ marginTop: 4 }}>
            {isReg ? 'Создать аккаунт' : 'Войти'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Profile({ user, go, onLogout }) {
  const [lang, setLang] = React.useState('ru');
  const mine = AU_RECENT.slice(0, 3);
  if (!user) {
    return (
      <div className="wrap fade-in" style={{ paddingTop: 64, textAlign: 'center' }}>
        <p style={{ color: 'var(--muted)' }}>Вы не вошли.</p>
        <button className="btn btn-primary" onClick={() => go('auth')}>Войти</button>
      </div>
    );
  }
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64, maxWidth: 820 }}>
      <div className="row gap-4" style={{ alignItems: 'center', marginBottom: 28 }}>
        <span style={{ width: 56, height: 56, borderRadius: 999, background: 'var(--green)', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 24, flex: 'none' }}>{user.name[0].toUpperCase()}</span>
        <div className="col" style={{ flex: 1 }}>
          <h1 className="serif" style={{ fontSize: 28 }}>{user.name}</h1>
          <span style={{ color: 'var(--muted)', fontSize: 14 }}>{user.email}</span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onLogout}>Выйти</button>
      </div>

      <div className="row gap-6" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div className="col gap-4" style={{ width: 320, flex: 'none' }}>
          <h2 style={{ fontSize: 20 }}>Настройки</h2>
          <div className="card" style={{ padding: '6px 18px' }}>
            <div className="row" style={{ justifyContent: 'space-between', padding: '14px 0', borderBottom: '1px solid var(--line)' }}>
              <div className="col"><span style={{ fontWeight: 700 }}>Язык интерфейса</span><span style={{ fontSize: 13, color: 'var(--muted)' }}>RU или EN, без смешения</span></div>
              <div className="row" style={{ background: 'var(--paper-2)', borderRadius: 9, padding: 3, gap: 3 }}>
                {[['ru', 'RU'], ['en', 'EN']].map(([v, l]) => (
                  <button key={v} onClick={() => setLang(v)} style={{ border: 0, cursor: 'pointer', fontWeight: 700, fontSize: 12.5, padding: '6px 14px', borderRadius: 7, background: lang === v ? 'var(--card)' : 'transparent', color: lang === v ? 'var(--ink)' : 'var(--muted)', boxShadow: lang === v ? 'var(--shadow-sm)' : 'none' }}>{l}</button>
                ))}
              </div>
            </div>
            <div className="row" style={{ justifyContent: 'space-between', padding: '14px 0' }}>
              <div className="col"><span style={{ fontWeight: 700 }}>Свои API-ключи</span><span style={{ fontSize: 13, color: 'var(--muted)' }}>Играть на собственных ключах провайдеров</span></div>
              <button className="btn btn-ghost btn-sm">Добавить</button>
            </div>
          </div>
        </div>

        <div className="col gap-4" style={{ flex: 1, minWidth: 320 }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
            <h2 style={{ fontSize: 20 }}>Мои партии</h2>
            <button className="btn btn-quiet btn-sm" onClick={() => go('archive')}>Все →</button>
          </div>
          <div className="col gap-2">
            {mine.map(g => <GameRow key={g.id} g={g} go={go} />)}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Auth, Profile });
