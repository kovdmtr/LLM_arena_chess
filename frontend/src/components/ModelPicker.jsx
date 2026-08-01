/* Выбор модели: карточки, сгруппированные по провайдеру.
 * Модель без ключа показывается, но выбрать её нельзя (как и на бэкенде). */
import { groupByProvider, providerLabel } from '../lib/models.js'
import { Avatar } from './ModelChip.jsx'

function ModelOption({ model, selected, onPick }) {
  const disabled = !model.has_key
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onPick(model.id)}
      title={disabled ? 'Ключ провайдера не задан' : model.id}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        textAlign: 'left',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        background: selected ? 'var(--green-soft)' : 'var(--card)',
        border: '1.5px solid ' + (selected ? 'var(--green)' : 'var(--line-2)'),
        borderRadius: 10,
        padding: '10px 12px',
        color: 'inherit',
        transition: 'border-color .12s, background .12s',
      }}
    >
      <Avatar name={model.display_name} provider={model.provider} size={28} />
      <span className="col" style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
        <span style={{ fontWeight: 700, fontSize: 14.5 }}>{model.display_name}</span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--faint)' }}>
          {model.id}
        </span>
      </span>
      {disabled ? (
        <span className="badge" style={{ flex: 'none' }}>
          ключ не задан
        </span>
      ) : (
        selected && <span style={{ color: 'var(--accent-text)', fontWeight: 800 }}>✓</span>
      )}
    </button>
  )
}

export default function ModelPicker({ models, value, onPick, label }) {
  const groups = groupByProvider(models)

  return (
    <div className="field" style={{ flex: '1 1 300px', minWidth: 280 }}>
      <label>{label}</label>
      {groups.map((group) => (
        <div key={group.provider} className="col gap-2" style={{ marginBottom: 6 }}>
          <span className="eyebrow" style={{ fontSize: 11 }}>
            {providerLabel(group.provider)}
          </span>
          {group.models.map((model) => (
            <ModelOption
              key={model.id}
              model={model}
              selected={model.id === value}
              onPick={onPick}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
