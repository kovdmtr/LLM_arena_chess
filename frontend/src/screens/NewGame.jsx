/* Новая партия: выбор моделей для сторон и старт через POST /api/games. */
import { useEffect, useState } from 'react'

import Link from '../components/Link.jsx'
import ModelChip from '../components/ModelChip.jsx'
import ModelPicker from '../components/ModelPicker.jsx'
import { ErrorBanner, Skeletons } from '../components/States.jsx'
import { useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { indexModels } from '../lib/models.js'
import { navigate } from '../lib/navigation.js'
import { defaultPick, startBlockedReason } from '../lib/newGame.js'
import { hrefFor } from '../lib/router.js'
import { useAsync } from '../lib/useAsync.js'

export default function NewGame() {
  const t = useT()
  const catalog = useAsync(() => api.models(), [])
  const models = catalog.data || []
  const [pick, setPick] = useState({ white: '', black: '' })
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState(null)

  // как только каталог приехал — подставляем первые доступные модели
  useEffect(() => {
    if (models.length) setPick(defaultPick(models))
  }, [catalog.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const index = indexModels(models)
  const white = index.find(pick.white)
  const black = index.find(pick.black)
  const blockedKey = startBlockedReason(pick.white, pick.black, models)

  const start = async () => {
    setStartError(null)
    setStarting(true)
    try {
      const { id } = await api.startGame(pick.white, pick.black)
      navigate(hrefFor('game', { id }))
    } catch (error) {
      setStartError(error)
      setStarting(false)
    }
  }

  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64, maxWidth: 920 }}>
      <span className="eyebrow">{t('newGame.eyebrow')}</span>
      <h1 style={{ fontSize: 36, marginTop: 12, marginBottom: 8 }}>{t('newGame.title')}</h1>
      <p style={{ color: 'var(--muted)', marginTop: 0, maxWidth: 560 }}>{t('newGame.lead')}</p>

      <ErrorBanner error={catalog.error || startError} />

      {catalog.loading && <Skeletons count={4} height={56} />}

      {!catalog.loading && !catalog.error && (
        <>
          <div
            className="card"
            style={{
              padding: '18px 22px',
              margin: '24px 0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 28,
              flexWrap: 'wrap',
            }}
          >
            <div className="col" style={{ alignItems: 'flex-end', flex: 1, minWidth: 180 }}>
              <ModelChip
                name={white ? white.display_name : t('model.none')}
                provider={white && white.provider}
                size={30}
                sub
              />
              <span className="mono" style={{ fontSize: 11, color: 'var(--muted)', marginTop: 5 }}>
                {t('newGame.whiteShort')}
              </span>
            </div>
            <span className="serif" style={{ fontSize: 30, fontWeight: 800, color: 'var(--faint)', fontStyle: 'italic' }}>
              vs
            </span>
            <div className="col" style={{ alignItems: 'flex-start', flex: 1, minWidth: 180 }}>
              <ModelChip
                name={black ? black.display_name : t('model.none')}
                provider={black && black.provider}
                size={30}
                sub
              />
              <span className="mono" style={{ fontSize: 11, color: 'var(--muted)', marginTop: 5 }}>
                {t('newGame.blackShort')}
              </span>
            </div>
          </div>

          <div className="row gap-6" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <ModelPicker
              label={t('newGame.white')}
              models={models}
              value={pick.white}
              onPick={(id) => setPick((p) => ({ ...p, white: id }))}
            />
            <ModelPicker
              label={t('newGame.black')}
              models={models}
              value={pick.black}
              onPick={(id) => setPick((p) => ({ ...p, black: id }))}
            />
          </div>

          <div className="banner" style={{ marginTop: 24 }}>
            <span>💳</span>
            <span>{t('newGame.cost')}</span>
          </div>

          {blockedKey && (
            <p className="hint" style={{ marginTop: 14 }}>
              {t(blockedKey)}
            </p>
          )}

          <div className="row gap-3" style={{ marginTop: 20, flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary btn-lg"
              disabled={Boolean(blockedKey) || starting}
              onClick={start}
            >
              {starting ? t('newGame.starting') : t('newGame.start')}
            </button>
            <Link href={hrefFor('home')} className="btn btn-quiet btn-lg">
              {t('action.cancel')}
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
