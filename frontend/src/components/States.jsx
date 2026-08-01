/* Состояния данных: загрузка (скелетон), пусто, ошибка (DESIGN_BRIEF §3). */
import { useT } from '../lib/LangContext.jsx'

export function Skeletons({ count = 3, height = 68 }) {
  const t = useT()
  return (
    <div className="col gap-2" aria-busy="true" aria-label={t('state.loading')}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton" style={{ height }} />
      ))}
    </div>
  )
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <span className="ttl">{title}</span>
      {children && <span style={{ fontSize: 14 }}>{children}</span>}
    </div>
  )
}

export function ErrorBanner({ error }) {
  const t = useT()
  if (!error) return null
  // знакомый код переводим; незнакомый (новее фронта) — показываем текст бэкенда
  const text =
    error.key && t.has(error.key)
      ? t(error.key, error.params)
      : error.text || error.message || String(error)
  return (
    <div className="banner banner-error" role="alert">
      <span>⚠</span>
      <span>{text}</span>
    </div>
  )
}
