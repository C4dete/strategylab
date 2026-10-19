import './ui.css'

interface Opcao<T extends string> {
  valor: T
  rotulo: string
}

interface Props<T extends string> {
  nome: string
  valor: T
  opcoes: Opcao<T>[]
  onChange: (v: T) => void
  disabled?: boolean
  'aria-labelledby'?: string
}

/** Escolha exclusiva entre poucas opções (grupo de rádios estilizado). */
export function Segmented<T extends string>({ nome, valor, opcoes, onChange, disabled, ...aria }: Props<T>) {
  return (
    <div className={`seg ${disabled ? 'seg--disabled' : ''}`} role="radiogroup" {...aria}>
      {opcoes.map((o) => (
        <label key={o.valor} className={`seg__op ${o.valor === valor ? 'is-on' : ''}`}>
          <input
            type="radio"
            name={nome}
            value={o.valor}
            checked={o.valor === valor}
            disabled={disabled}
            onChange={() => onChange(o.valor)}
          />
          <span>{o.rotulo}</span>
        </label>
      ))}
    </div>
  )
}
