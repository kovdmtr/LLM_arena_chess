/* Состояния данных: загрузка (скелетон), пусто, ошибка (DESIGN_BRIEF §3). */

export function Skeletons({ count = 3, height = 68 }) {
  return (
    <div className="col gap-2" aria-busy="true" aria-label="Загрузка">
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
  if (!error) return null
  return (
    <div className="banner banner-error" role="alert">
      <span>⚠</span>
      <span>{error.message || String(error)}</span>
    </div>
  )
}
