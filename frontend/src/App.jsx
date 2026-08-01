/* Каркас приложения: шапка с брендом, область экрана, подвал.
 *
 * На этом шаге — только оболочка дизайна; навигация, API-клиент и экраны
 * приезжают следующими задачами (см. docs/TODO.md).
 */
export default function App() {
  return (
    <div className="app">
      <header className="hdr">
        <div className="wrap hdr-in">
          <div className="brand">
            <span className="brand-mark">
              <i>♟</i>
              <i />
              <i />
              <i />
            </span>
            <span className="brand-name">
              LLM Chess <b>Arena</b>
            </span>
          </div>
          <div className="hdr-spacer" />
        </div>
      </header>

      <main style={{ flex: 1 }}>
        <div className="wrap" style={{ padding: '48px 28px' }}>
          <h1>LLM Chess Arena</h1>
        </div>
      </main>

      <footer style={{ borderTop: '1px solid var(--line)', background: 'var(--card)' }}>
        <div
          className="wrap row"
          style={{ justifyContent: 'space-between', alignItems: 'center', height: 64, flexWrap: 'wrap', gap: 12 }}
        >
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>
            LLM Chess Arena · FastAPI · python-chess · Stockfish
          </span>
          <span className="mono" style={{ fontSize: 12, color: 'var(--faint)' }}>
            Источник истины — game.json → PGN + HTML
          </span>
        </div>
      </footer>
    </div>
  )
}
