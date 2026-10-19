import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import './ui.css'

type Tipo = 'ok' | 'erro' | 'info'
interface Item {
  id: number
  tipo: Tipo
  texto: string
}

interface Ctx {
  toast: (tipo: Tipo, texto: string) => void
}

const ToastCtx = createContext<Ctx>({ toast: () => undefined })

export function useToast(): Ctx {
  return useContext(ToastCtx)
}

const ICONES = { ok: CheckCircle2, erro: AlertTriangle, info: Info }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [itens, setItens] = useState<Item[]>([])
  const seq = useRef(0)

  const fechar = useCallback((id: number) => setItens((l) => l.filter((i) => i.id !== id)), [])
  const toast = useCallback(
    (tipo: Tipo, texto: string) => {
      const id = ++seq.current
      setItens((l) => [...l.slice(-3), { id, tipo, texto }])
      window.setTimeout(() => fechar(id), tipo === 'erro' ? 8000 : 4200)
    },
    [fechar],
  )
  const valor = useMemo(() => ({ toast }), [toast])

  return (
    <ToastCtx.Provider value={valor}>
      {children}
      <div className="toasts" role="region" aria-label="Avisos" aria-live="polite">
        {itens.map((i) => {
          const Icone = ICONES[i.tipo]
          return (
            <div key={i.id} className={`toast toast--${i.tipo}`} role={i.tipo === 'erro' ? 'alert' : 'status'}>
              <Icone size={16} aria-hidden />
              <span>{i.texto}</span>
              <button type="button" className="toast__x" aria-label="Dispensar aviso" onClick={() => fechar(i.id)}>
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}
