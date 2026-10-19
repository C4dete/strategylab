import { useState } from 'react'
import { HHMM } from '../../lib/params'
import './ui.css'

interface Props {
  id: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  invalid?: boolean
  'aria-label'?: string
  'aria-describedby'?: string
}

/** Horário HH:MM nativo (passo de 5 min). Só propaga valores completos e válidos. */
export function TimeInput({ id, value, onChange, disabled, invalid, ...aria }: Props) {
  const [texto, setTexto] = useState(value)
  const [anterior, setAnterior] = useState(value)
  if (value !== anterior) {          // o valor veio de fora (outra estratégia, "Sem limite"...): acompanha
    setAnterior(value)
    setTexto(value)
  }

  return (
    <input
      id={id}
      className={`time mono ${invalid ? 'time--invalid' : ''}`}
      type="time"
      step={300}
      value={texto}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      onChange={(e) => {
        setTexto(e.target.value)
        if (HHMM.test(e.target.value)) onChange(e.target.value)
      }}
      onBlur={() => setTexto(value)}
      {...aria}
    />
  )
}
