/* Язык интерфейса в React: провайдер + хуки `useT`/`useLang`. */
import { createContext, useCallback, useContext, useMemo, useState } from 'react'

import { createT, initLang, storeLang } from './i18n.js'

const LangContext = createContext(null)

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => initLang())

  const change = useCallback((value) => {
    storeLang(value)
    document.documentElement.setAttribute('lang', value)
    setLang(value)
  }, [])

  const value = useMemo(() => ({ lang, t: createT(lang), setLang: change }), [lang, change])
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>
}

function useLangContext() {
  const value = useContext(LangContext)
  if (!value) throw new Error('LangProvider отсутствует выше по дереву')
  return value
}

/** Переводчик текущего языка. */
export function useT() {
  return useLangContext().t
}

/** Текущий язык и переключатель. */
export function useLang() {
  const { lang, setLang } = useLangContext()
  return { lang, setLang }
}
