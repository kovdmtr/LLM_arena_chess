/* Оболочка приложения: шапка, экран по текущему маршруту, подвал.
 *
 * Экраны подключаются по мере готовности (docs/TODO.md, раздел «Редизайн
 * фронтенда»); ещё не написанные показывают заглушку, но их адреса уже
 * маршрутизируются — навигация и deep links работают целиком.
 */
import { useState } from 'react'

import Footer from './components/Footer.jsx'
import Header from './components/Header.jsx'
import { LangProvider } from './lib/LangContext.jsx'
import { useRoute } from './lib/navigation.js'
import { applyTheme, nextTheme, storeTheme } from './lib/theme.js'
import Archive from './screens/Archive.jsx'
import Game from './screens/Game.jsx'
import Home from './screens/Home.jsx'
import NewGame from './screens/NewGame.jsx'
import NewTournament from './screens/NewTournament.jsx'
import Placeholder from './screens/Placeholder.jsx'
import Tournament from './screens/Tournament.jsx'
import Tournaments from './screens/Tournaments.jsx'

function Screen({ route }) {
  switch (route.name) {
    case 'home':
      return <Home />
    case 'archive':
      return <Archive />
    case 'new-game':
      return <NewGame />
    case 'game':
      return <Game id={route.params.id} />
    case 'tournaments':
      return <Tournaments />
    case 'new-tournament':
      return <NewTournament />
    case 'tournament':
      return <Tournament id={route.params.id} />
    default:
      return <Placeholder titleKey="notFound.title" noteKey="notFound.note" eyebrowKey="notFound.eyebrow" />
  }
}

export default function App() {
  const route = useRoute()
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute('data-theme') || 'light',
  )

  const toggleTheme = () => {
    const value = nextTheme(theme)
    applyTheme(value)
    storeTheme(value)
    setTheme(value)
  }

  return (
    <LangProvider>
      <div className="app">
        <Header route={route} theme={theme} onToggleTheme={toggleTheme} />
        <main style={{ flex: 1 }}>
          <Screen route={route} />
        </main>
        <Footer />
      </div>
    </LangProvider>
  )
}
