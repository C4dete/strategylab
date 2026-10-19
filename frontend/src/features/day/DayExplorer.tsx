import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { api } from '../../api/client'
import type { Resultado } from '../../api/types'
import { IconButton } from '../../components/ui/Button'
import { brl, dataBR, diaDaSemana, numero, pct, pts } from '../../lib/format'
import { DayChart } from './DayChart'
import { TradesTable } from './TradesTable'
import './DayExplorer.css'

export function DayExplorer({ resultado }: { resultado: Resultado }) {
  const { diario, operacoes, params, bd, resumo } = resultado
  const [escolhido, setDia] = useState<string>('')
  // se o resultado mudar e o pregão escolhido deixar de existir, vale o último
  const dia = diario.some((d) => d.data === escolhido) ? escolhido : (diario[diario.length - 1]?.data ?? '')

  const idx = diario.findIndex((d) => d.data === dia)
  const atual = diario[idx]
  const opsDoDia = useMemo(() => operacoes.filter((o) => o.data === dia), [operacoes, dia])

  // indicadores do gráfico: períodos da execução (não do rascunho), para casar com as entradas mostradas
  const ind = { mm: params.mm_periodo, bb: params.bb_periodo, k: params.bb_desvio }
  const barras = useQuery({
    queryKey: ['dia', bd.id, dia, ind.mm, ind.bb, ind.k],
    queryFn: () => api.dia(dia, ind),
    enabled: dia !== '',
    staleTime: Infinity,
  })

  const ir = (i: number) => {
    const alvo = diario[Math.min(diario.length - 1, Math.max(0, i))]
    if (alvo) setDia(alvo.data)
  }

  const onKey = (e: KeyboardEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).tagName === 'SELECT') return
    if (e.key === 'ArrowLeft') ir(idx - 1)
    else if (e.key === 'ArrowRight') ir(idx + 1)
  }

  if (!atual) return null
  const fechadas = atual.ganhos + atual.perdas
  const sinal = atual.rs > 0 ? 'pos' : atual.rs < 0 ? 'neg' : ''

  return (
    <section className="bloco reveal" style={{ '--i': 3 } as CSSProperties} aria-labelledby="titulo-dia" onKeyDown={onKey}>
      <header className="bloco__topo">
        <div>
          <h2 id="titulo-dia" className="bloco__titulo">Operações do dia</h2>
          <p className="bloco__sub">Escolha o pregão — use ← → para andar entre os dias.</p>
        </div>
        <div className="dia-nav">
          <IconButton label="Pregão anterior" onClick={() => ir(idx - 1)} disabled={idx <= 0}>
            <ChevronLeft size={18} />
          </IconButton>
          <label className="sr-only" htmlFor="sel-dia">Pregão</label>
          <select id="sel-dia" className="select mono dia-nav__sel" value={dia} onChange={(e) => setDia(e.target.value)}>
            {[...diario].reverse().map((d) => (
              <option key={d.data} value={d.data}>
                {dataBR(d.data)} · {diaDaSemana(d.data)} · {brl(d.rs, { mais: true, casas: 0 })}
              </option>
            ))}
          </select>
          <IconButton label="Próximo pregão" onClick={() => ir(idx + 1)} disabled={idx >= diario.length - 1}>
            <ChevronRight size={18} />
          </IconButton>
          <div className="dia-nav__atalhos">
            <button type="button" className="chip" onClick={() => resumo.melhor_dia && setDia(resumo.melhor_dia.data)}>Melhor</button>
            <button type="button" className="chip" onClick={() => resumo.pior_dia && setDia(resumo.pior_dia.data)}>Pior</button>
            <button type="button" className="chip" onClick={() => ir(diario.length - 1)}>Último</button>
          </div>
        </div>
      </header>

      <dl className="dia-stats">
        <div>
          <dt className="label">Resultado do dia</dt>
          <dd className={`mono dia-stats__v ${sinal}`}>{brl(atual.rs, { mais: true })}</dd>
          <dd className="dia-stats__s"><span className="mono">{pts(atual.pts, { mais: true })}</span> pts</dd>
        </div>
        <div>
          <dt className="label">Operações</dt>
          <dd className="mono dia-stats__v">{numero(atual.operacoes)}</dd>
        </div>
        <div>
          <dt className="label">Gains / Losses</dt>
          <dd className="mono dia-stats__v">
            <span className="pos">{atual.ganhos}</span> / <span className="neg">{atual.perdas}</span>
          </dd>
        </div>
        <div>
          <dt className="label">Win rate</dt>
          <dd className="mono dia-stats__v">{fechadas ? pct((atual.ganhos / fechadas) * 100, 0) : '—'}</dd>
        </div>
      </dl>

      <div className="dia-chart">
        {barras.isPending && <div className="skel" style={{ height: 400 }} aria-busy="true" />}
        {barras.isError && <p className="aviso-erro">Não foi possível carregar os candles deste pregão: {barras.error.message}</p>}
        {barras.data && (
          <DayChart barras={barras.data.barras} operacoes={opsDoDia} params={params} timeframeMin={10} />
        )}
      </div>

      <TradesTable operacoes={opsDoDia} zeragem={params.janela_fim} mostrarFiltro={params.filtro_afast_mm_ativo} periodoMM={params.mm_periodo} />
    </section>
  )
}
