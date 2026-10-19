import './ui.css'

interface Props {
  checked: boolean
  onChange: (v: boolean) => void
  /** Id do elemento que rotula o interruptor. */
  'aria-labelledby': string
  disabled?: boolean
}

/** Interruptor liga/desliga (role="switch"). Teclado: Espaço/Enter alternam. */
export function Switch({ checked, onChange, disabled, ...aria }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`sw ${checked ? 'is-on' : ''}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      {...aria}
    >
      <span className="sw__estado" aria-hidden>
        {checked ? 'ON' : 'OFF'}
      </span>
      <span className="sw__trilho" aria-hidden>
        <span className="sw__botao" />
      </span>
    </button>
  )
}
