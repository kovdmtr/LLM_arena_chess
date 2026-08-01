/* Шапка: бренд (ссылка на главную), навигация по разделам, переключатели языка
 * и темы, кнопка запуска партии. Вёрстка и классы — из импортированного дизайна. */
import { useLang, useT } from '../lib/LangContext.jsx'
import { otherLang } from '../lib/i18n.js'
import { hrefFor, isActiveNav } from '../lib/router.js'
import Link from './Link.jsx'

const TABS = [
  ['home', 'nav.home'],
  ['new-game', 'nav.newGame'],
  ['archive', 'nav.archive'],
  ['tournaments', 'nav.tournaments'],
]

export default function Header({ route, theme, onToggleTheme }) {
  const t = useT()
  const { lang, setLang } = useLang()
  const next = otherLang(lang)

  return (
    <header className="hdr">
      <div className="wrap hdr-in">
        <Link href="/" className="brand" style={{ textDecoration: 'none' }}>
          <span className="brand-mark">
            <i>♞</i>
            <i />
            <i />
            <i />
          </span>
          <span className="brand-name">
            LLM&nbsp;Chess&nbsp;<b>Arena</b>
          </span>
        </Link>

        <nav className="nav">
          {TABS.map(([name, key]) => (
            <Link
              key={name}
              href={hrefFor(name)}
              className={'nav-link' + (isActiveNav(name, route) ? ' active' : '')}
              style={{ textDecoration: 'none' }}
            >
              {t(key)}
            </Link>
          ))}
        </nav>

        <span className="hdr-spacer" />

        <button
          className="icon-btn"
          style={{ width: 'auto', padding: '0 10px', fontWeight: 700, fontSize: 12.5 }}
          onClick={() => setLang(next)}
          title={t('lang.switch')}
          aria-label={t('lang.switch')}
        >
          {next.toUpperCase()}
        </button>
        <button
          className="icon-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? t('theme.toLight') : t('theme.toDark')}
          aria-label={theme === 'dark' ? t('theme.toLight') : t('theme.toDark')}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
        <Link href={hrefFor('new-game')} className="btn btn-primary btn-sm">
          {t('action.start')}
        </Link>
      </div>
    </header>
  )
}
