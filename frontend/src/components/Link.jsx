/* Внутренняя ссылка: настоящий <a href> (можно открыть в новой вкладке,
 * видно в статусной строке), но обычный клик обрабатывает роутер SPA. */
import { navigate } from '../lib/navigation.js'

export default function Link({ href, children, className, style, title, onClick }) {
  const handle = (event) => {
    if (event.defaultPrevented) return
    // средний клик / Ctrl+клик / Shift+клик — отдаём браузеру
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    if (onClick) onClick(event)
    navigate(href)
  }

  return (
    <a href={href} className={className} style={style} title={title} onClick={handle}>
      {children}
    </a>
  )
}
