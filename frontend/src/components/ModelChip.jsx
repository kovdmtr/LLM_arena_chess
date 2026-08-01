/* Аватар модели и «чип» (аватар + имя + провайдер) — из импортированного дизайна. */
import { initials, providerColor, providerLabel } from '../lib/models.js'

export function Avatar({ name, provider, size = 26 }) {
  return (
    <span
      className="av"
      style={{ background: providerColor(provider), width: size, height: size, fontSize: size * 0.42 }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}

export default function ModelChip({ name, provider, size = 26, sub = false }) {
  return (
    <span className="mchip">
      <Avatar name={name} provider={provider} size={size} />
      <span className="col" style={{ lineHeight: 1.15, minWidth: 0 }}>
        <span style={{ fontSize: 14.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {name}
        </span>
        {sub && (
          <span style={{ fontWeight: 500, fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
            {providerLabel(provider)}
          </span>
        )}
      </span>
    </span>
  )
}
