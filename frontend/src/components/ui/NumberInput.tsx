import { Minus, Plus } from 'lucide-react'
import { useState, type KeyboardEvent } from 'react'
import { numero } from '../../lib/format'
import './ui.css'

interface Props {
  id: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  /** Casas decimais exibidas (e usadas ao arredondar). */
  casas?: number
  disabled?: boolean
  invalid?: boolean
  'aria-describedby'?: string
}

function arredonda(v: number, casas: number): number {
  const f = 10 ** casas
  return Math.round(v * f) / f
}

function ler(texto: string): number {
  // aceita "0,05" e "0.05"; "1.234" (milhar pt-BR) não é um caso aqui: os campos são pequenos
  return Number(texto.trim().replace(',', '.'))
}

/** Campo numérico com passos −/+, digitação em pt-BR e limites. Confirma em Enter/blur/setas. */
export function NumberInput({
  id, value, onChange, min, max, step = 1, casas = 0, disabled, invalid, 'aria-describedby': descr,
}: Props) {
  const [texto, setTexto] = useState(() => numero(value, casas))
  const [editando, setEditando] = useState(false)
  const [anterior, setAnterior] = useState(value)
  if (value !== anterior) {          // o valor mudou por fora (troca de estratégia, passos...): reescreve o texto
    setAnterior(value)
    if (!editando) setTexto(numero(value, casas))
  }

  const aplica = (v: number) => {
    const limpo = arredonda(Math.min(max, Math.max(min, v)), casas)
    onChange(limpo)
    setTexto(numero(limpo, casas))
  }

  const confirma = () => {
    setEditando(false)
    const v = ler(texto)
    if (texto.trim() === '' || Number.isNaN(v)) setTexto(numero(value, casas))
    else aplica(v)
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      confirma()
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault()
      const base = editando ? ler(texto) : value
      aplica((Number.isNaN(base) ? value : base) + (e.key === 'ArrowUp' ? step : -step))
    }
  }

  return (
    <div className={`num ${invalid ? 'num--invalid' : ''} ${disabled ? 'num--disabled' : ''}`}>
      <button
        type="button"
        className="num__btn"
        aria-label="Diminuir"
        tabIndex={-1}
        disabled={disabled || value <= min}
        onClick={() => aplica(value - step)}
      >
        <Minus size={14} aria-hidden />
      </button>
      <input
        id={id}
        className="num__input mono"
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={texto}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        aria-describedby={descr}
        onFocus={(e) => {
          setEditando(true)
          e.currentTarget.select()
        }}
        onChange={(e) => setTexto(e.target.value)}
        onBlur={confirma}
        onKeyDown={onKey}
      />
      <button
        type="button"
        className="num__btn"
        aria-label="Aumentar"
        tabIndex={-1}
        disabled={disabled || value >= max}
        onClick={() => aplica(value + step)}
      >
        <Plus size={14} aria-hidden />
      </button>
    </div>
  )
}
