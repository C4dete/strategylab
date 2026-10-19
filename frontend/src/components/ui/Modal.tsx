import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { IconButton } from './Button'
import './ui.css'

interface Props {
  aberto: boolean
  titulo: string
  onFechar: () => void
  children: ReactNode
  acoes?: ReactNode
  /** Largura máxima em px. */
  largura?: number
}

/** Diálogo modal sobre o elemento nativo <dialog>: foco preso, ESC fecha, fundo inerte. */
export function Modal({ aberto, titulo, onFechar, children, acoes, largura = 440 }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const tituloId = useId()

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (aberto && !d.open) {
      d.showModal()
      // o React não escreve o atributo `autofocus`; o campo principal se marca com data-autofocus
      d.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    }
    if (!aberto && d.open) d.close()
  }, [aberto])

  return (
    <dialog
      ref={ref}
      className="modal"
      style={{ maxWidth: largura }}
      aria-labelledby={tituloId}
      onCancel={(e) => {
        e.preventDefault()
        onFechar()
      }}
      onMouseDown={(e) => {
        if (e.target === ref.current) onFechar()
      }}
    >
      {aberto && (
        <div className="modal__corpo">
          <header className="modal__topo">
            <h2 id={tituloId} className="modal__titulo">
              {titulo}
            </h2>
            <IconButton label="Fechar" onClick={onFechar}>
              <X size={16} />
            </IconButton>
          </header>
          <div className="modal__conteudo">{children}</div>
          {acoes && <footer className="modal__acoes">{acoes}</footer>}
        </div>
      )}
    </dialog>
  )
}
