import { AlertTriangle, ChevronDown } from 'lucide-react'
import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { Estrategia } from '../../api/types'
import { identidade, MAX_ESTRATEGIAS } from './identidade'
import { Selo } from './Selo'
import './correlacao.css'

interface Props {
  /** Todas as estratégias salvas. */
  estrategias: Estrategia[]
  /** A selecionada (principal, letra A); null sem seleção. */
  principal: Estrategia | null
  /** Ids marcados, na ordem em que foram marcados (a ordem decide letra e cor). */
  marcadas: string[]
  onAlternar: (id: string) => void
  onLimpar: () => void
}

const LIMITE_BUSCA = 8

/**
 * "Correlacionar": marque quantas estratégias quiser para somar ao resultado da principal. Recolhido por padrão (só mostra
 * quantas e os selos); aberto lista as outras com caixa de marcar. Usa a versão SALVA de cada uma.
 */
export function CorrelacionarPicker({ estrategias, principal, marcadas, onAlternar, onLimpar }: Props) {
  const uid = useId()
  const [aberto, setAberto] = useState(false)
  const [busca, setBusca] = useState('')
  const lista = useRef<HTMLUListElement>(null)

  const outras = useMemo(() => estrategias.filter((e) => e.id !== principal?.id), [estrategias, principal])
  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase()
    return q ? outras.filter((e) => e.nome.toLowerCase().includes(q)) : outras
  }, [outras, busca])
  const cheio = marcadas.length >= MAX_ESTRATEGIAS - 1

  if (!principal || outras.length === 0) return null

  const onKey = (e: KeyboardEvent<HTMLUListElement>) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    const caixas = Array.from(lista.current?.querySelectorAll<HTMLInputElement>('input[type=checkbox]:not(:disabled)') ?? [])
    const i = caixas.findIndex((c) => c === document.activeElement)
    if (i < 0) return
    e.preventDefault()
    caixas[Math.min(caixas.length - 1, Math.max(0, i + (e.key === 'ArrowDown' ? 1 : -1)))]?.focus()
  }

  return (
    <section className={`corr ${marcadas.length ? 'tem-selecao' : ''}`} aria-labelledby={`${uid}-t`}>
      <button
        type="button"
        className="corr__topo"
        aria-expanded={aberto}
        aria-controls={`${uid}-corpo`}
        onClick={() => setAberto((v) => !v)}
      >
        <span id={`${uid}-t`} className="label">Correlacionar</span>
        <span className="corr__n" aria-label={marcadas.length ? `${marcadas.length} marcadas` : 'nenhuma marcada'}>{marcadas.length}</span>
        {marcadas.length > 0 && (
          <span className="corr__resumo" aria-hidden>
            <Selo i={0} />
            {marcadas.slice(0, 6).map((id, k) => <Selo key={id} i={k + 1} />)}
          </span>
        )}
        {marcadas.length === 0 && <span className="corr__resumo" />}
        <ChevronDown size={16} className="corr__seta" aria-hidden />
      </button>

      {aberto && (
        <div id={`${uid}-corpo`} className="corr__corpo">
          <p className="corr__nota">
            Soma ao resultado de <b>{principal.nome}</b>. Cada uma entra com a <b>versão salva</b>; a principal usa o que está na tela.
          </p>
          {outras.length > LIMITE_BUSCA && (
            <input
              type="search"
              className="corr__busca"
              placeholder="Buscar estratégia"
              aria-label="Buscar estratégia para correlacionar"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          )}
          <ul className="corr__lista" ref={lista} onKeyDown={onKey} aria-label="Estratégias para correlacionar">
            <li className="corr__item is-principal">
              <span className="corr__rotulo" style={{ cursor: 'default' }}>
                <Selo i={0} />
                <span className="nome-selo__nome">{principal.nome}</span>
                <span className="nome-selo__tag">principal</span>
              </span>
            </li>
            {filtradas.length === 0 && <li className="corr__vazio">Nenhuma estratégia com esse nome.</li>}
            {filtradas.map((e) => {
              const pos = marcadas.indexOf(e.id)
              const marcada = pos >= 0
              const bloqueada = !e.valida || (!marcada && cheio)
              return (
                <li key={e.id} className={`corr__item ${marcada ? 'is-marcada' : ''} ${e.valida ? '' : 'is-off'}`}>
                  <label className="corr__rotulo" title={e.valida ? undefined : (e.erro ?? 'Arquivo inválido')}>
                    <input type="checkbox" checked={marcada} disabled={bloqueada} onChange={() => onAlternar(e.id)} />
                    {marcada ? <Selo i={pos + 1} /> : e.valida ? null : <AlertTriangle size={14} aria-hidden />}
                    <span className="nome-selo__nome">{e.nome}</span>
                    {marcada && <span className="sr-only"> (estratégia {identidade(pos + 1).letra})</span>}
                  </label>
                </li>
              )
            })}
          </ul>
          <div className="corr__rodape">
            <span>{marcadas.length ? `${marcadas.length} de ${outras.length} marcadas` : 'Nenhuma marcada'}{cheio ? ' · limite atingido' : ''}</span>
            <button type="button" className="corr__limpar" disabled={marcadas.length === 0} onClick={onLimpar}>Limpar</button>
          </div>
        </div>
      )}
    </section>
  )
}
