/* Новый турнир: выбор ≥2 моделей, один или два круга, старт. */
import { useState } from 'react'

import { Avatar } from '../components/ModelChip.jsx'
import Link from '../components/Link.jsx'
import { ErrorBanner, Skeletons } from '../components/States.jsx'
import { useLang, useT } from '../lib/LangContext.jsx'
import { api } from '../lib/api.js'
import { groupByProvider, providerLabel } from '../lib/models.js'
import { navigate } from '../lib/navigation.js'
import { hrefFor } from '../lib/router.js'
import { gameCount, toggleSelection, tournamentBlockedReason } from '../lib/tournament.js'
import { useAsync } from '../lib/useAsync.js'

export default function NewTournament() {
  const t = useT()
  const { lang } = useLang()
  const catalog = useAsync(() => api.models(), [])
  const models = catalog.data || []
  const [selected, setSelected] = useState([])
  const [double, setDouble] = useState(false)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState(null)

  const blockedKey = tournamentBlockedReason(selected, models)
  const total = gameCount(new Set(selected).size, double)

  const start = async () => {
    setStartError(null)
    setStarting(true)
    try {
      const { id } = await api.startTournament([...new Set(selected)], double, lang)
      navigate(hrefFor('tournament', { id }))
    } catch (error) {
      setStartError(error)
      setStarting(false)
    }
  }

  return (
    <div className="wrap fade-in" style={{ paddingTop: 40, paddingBottom: 64, maxWidth: 860 }}>
      <span className="eyebrow">{t('newTournament.eyebrow')}</span>
      <h1 style={{ fontSize: 36, marginTop: 12, marginBottom: 8 }}>{t('newTournament.title')}</h1>
      <p style={{ color: 'var(--muted)', marginTop: 0, maxWidth: 560 }}>{t('newTournament.lead')}</p>

      <ErrorBanner error={catalog.error || startError} />
      {catalog.loading && <Skeletons count={4} height={56} />}

      {!catalog.loading && !catalog.error && (
        <>
          <div className="col gap-4" style={{ marginTop: 22 }}>
            {groupByProvider(models).map((group) => (
              <div key={group.provider} className="col gap-2">
                <span className="eyebrow" style={{ fontSize: 11 }}>
                  {providerLabel(group.provider)}
                </span>
                {group.models.map((model) => {
                  const disabled = !model.has_key
                  const checked = selected.includes(model.id)
                  return (
                    <label
                      key={model.id}
                      className="rowcard"
                      style={{ cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1 }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => setSelected((current) => toggleSelection(current, model.id))}
                        style={{ width: 18, height: 18, accentColor: 'var(--green)' }}
                      />
                      <Avatar name={model.display_name} provider={model.provider} size={26} />
                      <span className="col" style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
                        <span style={{ fontWeight: 700 }}>{model.display_name}</span>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--faint)' }}>
                          {model.id}
                        </span>
                      </span>
                      {disabled && <span className="badge">{t('model.noKey')}</span>}
                    </label>
                  )
                })}
              </div>
            ))}
          </div>

          <label className="rowcard" style={{ marginTop: 18, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={double}
              onChange={() => setDouble((value) => !value)}
              style={{ width: 18, height: 18, accentColor: 'var(--green)' }}
            />
            <span className="col" style={{ flex: 1 }}>
              <span style={{ fontWeight: 700 }}>{t('newTournament.double')}</span>
              <span style={{ fontSize: 13, color: 'var(--muted)' }}>{t('newTournament.doubleNote')}</span>
            </span>
          </label>

          <div className="banner" style={{ marginTop: 18 }}>
            <span>💳</span>
            <span>{t('newTournament.cost', { count: total })}</span>
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
              {starting ? t('newTournament.starting') : t('newTournament.start')}
            </button>
            <Link href={hrefFor('tournaments')} className="btn btn-quiet btn-lg">
              {t('action.cancel')}
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
