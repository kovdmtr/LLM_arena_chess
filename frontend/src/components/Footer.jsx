/* Подвал: чем сделано и дисклеймер про платные вызовы API (DESIGN_BRIEF §3). */
import { useT } from '../lib/LangContext.jsx'

export default function Footer() {
  const t = useT()
  return (
    <footer className="ftr">
      <div className="wrap ftr-in">
        <small>{t('footer.stack')}</small>
        <span className="note mono">{t('footer.disclaimer')}</span>
      </div>
    </footer>
  )
}
