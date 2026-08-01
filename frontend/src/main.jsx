/* Точка входа SPA: шрифты дизайна, дизайн-система, монтирование App. */
import React from 'react'
import { createRoot } from 'react-dom/client'

// Шрифты дизайна — локально (без CDN): гротеск для текста, serif для заголовков,
// моноширинный для ходов и чисел. Веса те же, что использует дизайн-система.
import '@fontsource/hanken-grotesk/400.css'
import '@fontsource/hanken-grotesk/500.css'
import '@fontsource/hanken-grotesk/600.css'
import '@fontsource/hanken-grotesk/700.css'
import '@fontsource/hanken-grotesk/800.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'
import '@fontsource/spectral/700.css'
import '@fontsource/spectral/800.css'

import './styles/app.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
