/* Шапка: бренд (ссылка на главную), навигация по разделам, переключатель темы
 * и кнопка запуска партии. Вёрстка и классы — из импортированного дизайна. */
import { hrefFor, isActiveNav } from '../lib/router.js'
import Link from './Link.jsx'

const TABS = [
  ['home', 'Арена'],
  ['new-game', 'Новая партия'],
  ['archive', 'Партии'],
  ['tournaments', 'Турниры'],
]

export default function Header({ route, theme, onToggleTheme }) {
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
          {TABS.map(([name, label]) => (
            <Link
              key={name}
              href={hrefFor(name)}
              className={'nav-link' + (isActiveNav(name, route) ? ' active' : '')}
              style={{ textDecoration: 'none' }}
            >
              {label}
            </Link>
          ))}
        </nav>

        <span className="hdr-spacer" />

        <button
          className="icon-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
        <Link href={hrefFor('new-game')} className="btn btn-primary btn-sm">
          ＋ Запустить
        </Link>
      </div>
    </header>
  )
}
