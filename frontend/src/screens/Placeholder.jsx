/* Заглушка экрана, который приедет следующей задачей плана (docs/TODO.md).
 * Нужна, чтобы навигация и deep links работали целиком уже сейчас. */
import Link from '../components/Link.jsx'

export default function Placeholder({ title, note }) {
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <span className="eyebrow">Экран в работе</span>
      <h1 style={{ fontSize: 34, margin: '12px 0 14px' }}>{title}</h1>
      <p style={{ color: 'var(--muted)', maxWidth: 560, marginTop: 0 }}>{note}</p>
      <Link href="/" className="btn btn-ghost" style={{ marginTop: 18 }}>
        ← На главную
      </Link>
    </div>
  )
}
