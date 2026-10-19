import { AlertTriangle, Pencil, Plus, Trash2 } from 'lucide-react'
import { useRef, type KeyboardEvent } from 'react'
import type { Estrategia } from '../../api/types'
import { IconButton } from '../../components/ui/Button'
import { dataHoraBR } from '../../lib/format'

interface Props {
  estrategias: Estrategia[]
  selecionadaId: string | null
  alterado: boolean
  onSelecionar: (id: string) => void
  onNova: () => void
  onRenomear: () => void
  onExcluir: (e: Estrategia) => void
}

/** Lista das estratégias salvas no projeto. A ativa mostra renomear/excluir e o marcador de alteração. */
export function StrategyList({ estrategias, selecionadaId, alterado, onSelecionar, onNova, onRenomear, onExcluir }: Props) {
  const lista = useRef<HTMLUListElement>(null)

  const onKey = (e: KeyboardEvent<HTMLUListElement>) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    const botoes = Array.from(lista.current?.querySelectorAll<HTMLButtonElement>('button.estr__sel') ?? [])
    const i = botoes.findIndex((b) => b === document.activeElement)
    if (i < 0) return
    e.preventDefault()
    botoes[Math.min(botoes.length - 1, Math.max(0, i + (e.key === 'ArrowDown' ? 1 : -1)))]?.focus()
  }

  return (
    <section className="estr" aria-labelledby="t-estr">
      <header className="estr__topo">
        <h2 id="t-estr" className="label">Estratégias · {estrategias.length}</h2>
        <button type="button" className="estr__nova" onClick={onNova}>
          <Plus size={14} aria-hidden /> Nova
        </button>
      </header>

      {estrategias.length === 0 ? (
        <p className="estr__vazia">Nenhuma estratégia salva. Crie a primeira.</p>
      ) : (
        <ul className="estr__lista" ref={lista} onKeyDown={onKey}>
          {estrategias.map((e) => {
            const ativa = e.id === selecionadaId
            return (
              <li key={e.id} className={`estr__item ${ativa ? 'is-ativa' : ''} ${e.valida ? '' : 'is-invalida'}`}>
                <button
                  type="button"
                  className="estr__sel"
                  aria-current={ativa || undefined}
                  title={e.valida ? `Salva em ${dataHoraBR(e.atualizada_em)}` : (e.erro ?? 'Arquivo inválido')}
                  onClick={() => onSelecionar(e.id)}
                >
                  {e.valida ? (
                    <span className={`estr__ponto ${ativa && alterado ? 'is-alterada' : ''}`} aria-hidden />
                  ) : (
                    <AlertTriangle size={14} aria-hidden />
                  )}
                  <span className="estr__nome">{e.nome}</span>
                  {ativa && alterado && <span className="sr-only"> (alterada, não salva)</span>}
                </button>
                {ativa && (
                  <span className="estr__acoes">
                    <IconButton label={`Renomear “${e.nome}”`} onClick={onRenomear}>
                      <Pencil size={14} />
                    </IconButton>
                    <IconButton label={`Excluir “${e.nome}”`} variant="danger" onClick={() => onExcluir(e)}>
                      <Trash2 size={14} />
                    </IconButton>
                  </span>
                )}
                {!ativa && !e.valida && (
                  <span className="estr__acoes">
                    <IconButton label={`Excluir “${e.nome}”`} variant="danger" onClick={() => onExcluir(e)}>
                      <Trash2 size={14} />
                    </IconButton>
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
