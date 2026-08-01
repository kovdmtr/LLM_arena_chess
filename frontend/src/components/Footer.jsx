/* Подвал: чем сделано и дисклеймер про платные вызовы API (DESIGN_BRIEF §3). */
export default function Footer() {
  return (
    <footer className="ftr">
      <div className="wrap ftr-in">
        <small>LLM Chess Arena · FastAPI · python-chess · Stockfish</small>
        <span className="note mono">
          Партии — реальные вызовы API моделей: запуск тратит деньги на ключах.
        </span>
      </div>
    </footer>
  )
}
