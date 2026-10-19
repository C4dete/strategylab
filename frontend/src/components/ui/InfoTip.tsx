import { Info } from 'lucide-react'
import { useId, useState, type CSSProperties, type ReactNode } from 'react'
import './ui.css'

interface Props {
  children: ReactNode
  rotulo?: string
  /** `esq`: a dica nasce no ícone e cresce para a direita; `dir`: termina na borda direita do ícone. */
  alinhar?: 'esq' | 'dir'
}

/**
 * Dica ao lado de um rótulo: aparece em hover e em foco de teclado.
 * Usa `position: fixed` calculada na hora, para não ser cortada pelo `overflow` do painel.
 */
export function InfoTip({ children, rotulo = 'Mais informações', alinhar = 'esq' }: Props) {
  const id = useId()
  const [estilo, setEstilo] = useState<CSSProperties>()

  const posicionar = (el: HTMLElement) => {
    const r = el.getBoundingClientRect()
    const largura = document.documentElement.clientWidth
    setEstilo(
      alinhar === 'dir'
        ? { top: r.bottom + 6, right: Math.max(8, largura - r.right - 8) }
        : { top: r.bottom + 6, left: Math.max(8, Math.min(r.left - 8, largura - 276)) },
    )
  }

  return (
    <span className="tip" onPointerEnter={(e) => posicionar(e.currentTarget)} onFocusCapture={(e) => posicionar(e.currentTarget)}>
      <button type="button" className="tip__btn" aria-label={rotulo} aria-describedby={id}>
        <Info size={13} aria-hidden />
      </button>
      <span role="tooltip" id={id} className="tip__body" style={estilo}>
        {children}
      </span>
    </span>
  )
}
