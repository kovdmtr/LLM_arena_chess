/* Простой экран-сообщение: сейчас на нём живёт только «страница не найдена»
 * (раньше — заглушки ещё не написанных экранов). */
import Link from '../components/Link.jsx'
import { useT } from '../lib/LangContext.jsx'

export default function Placeholder({ titleKey, noteKey, params, eyebrowKey = 'notFound.eyebrow' }) {
  const t = useT()
  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64 }}>
      <span className="eyebrow">{t(eyebrowKey)}</span>
      <h1 style={{ fontSize: 34, margin: '12px 0 14px' }}>{t(titleKey, params)}</h1>
      <p style={{ color: 'var(--muted)', maxWidth: 560, marginTop: 0 }}>{t(noteKey, params)}</p>
      <Link href="/" className="btn btn-ghost" style={{ marginTop: 18 }}>
        {t('action.home')}
      </Link>
    </div>
  )
}
