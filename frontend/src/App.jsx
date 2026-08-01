/* Оболочка приложения: шапка, экран по текущему маршруту, подвал.
 *
 * Экраны подключаются по мере готовности (docs/TODO.md, раздел «Редизайн
 * фронтенда»); ещё не написанные показывают заглушку, но их адреса уже
 * маршрутизируются — навигация и deep links работают целиком.
 */
import { useState } from 'react'

import Footer from './components/Footer.jsx'
import Header from './components/Header.jsx'
import { useRoute } from './lib/navigation.js'
import { applyTheme, nextTheme, storeTheme } from './lib/theme.js'
import Archive from './screens/Archive.jsx'
import Home from './screens/Home.jsx'
import NewGame from './screens/NewGame.jsx'
import Placeholder from './screens/Placeholder.jsx'

function Screen({ route }) {
  switch (route.name) {
    case 'home':
      return <Home />
    case 'archive':
      return <Archive />
    case 'new-game':
      return <NewGame />
    case 'game':
      return (
        <Placeholder
          title={`Партия ${route.params.id}`}
          note="Живой просмотр и отчёт приедут отдельными задачами плана."
        />
      )
    case 'tournaments':
      return <Placeholder title="Турниры" note="Список турниров приедет отдельной задачей плана." />
    case 'new-tournament':
      return <Placeholder title="Новый турнир" note="Создание турнира приедет отдельной задачей плана." />
    case 'tournament':
      return (
        <Placeholder
          title={`Турнир ${route.params.id}`}
          note="Таблица и расписание приедут отдельной задачей плана."
        />
      )
    default:
      return <Placeholder title="Страница не найдена" note="Проверьте адрес — такого экрана нет." />
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
    <div className="app">
      <Header route={route} theme={theme} onToggleTheme={toggleTheme} />
      <main style={{ flex: 1 }}>
        <Screen route={route} />
      </main>
      <Footer />
    </div>
  )
}
