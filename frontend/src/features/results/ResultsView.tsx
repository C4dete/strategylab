import { AlertTriangle, CircleDot, FlaskConical, Zap } from 'lucide-react'
import { Fragment, useState, type CSSProperties } from 'react'
import type { Estrategia } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { segundos } from '../../lib/format'
import { PerformancePanel } from '../correlacao/PerformancePanel'
import { NomeComSelo } from '../correlacao/Selo'
import { DayExplorer } from '../day/DayExplorer'
import { DailyOverviewChart } from './charts/DailyOverviewChart'
import { MonthlyChart } from './charts/MonthlyChart'
import { KpiBoard } from './KpiBoard'
import './ResultsView.css'
import type { Workspace } from '../../hooks/useWorkspace'

function Contexto({ ws, selecionada }: { ws: Workspace; selecionada: Estrategia }) {
  const r = ws.resultado
  const outras = ws.correlacionadas.flatMap((id) => ws.estrategias.find((e) => e.id === id) ?? [])
  return (
    <div className="contexto" role="status" aria-live="polite">
      <div className="contexto__id">
        <FlaskConical size={16} aria-hidden />
        {outras.length === 0 ? (
          <span className="contexto__nome">{selecionada.nome}</span>
        ) : (
          <span className="contexto__conjunto">
            <span className="contexto__nome"><NomeComSelo i={0} nome={selecionada.nome} /></span>
            {outras.map((e, k) => (
              <Fragment key={e.id}>
                <span className="contexto__mais" aria-hidden>+</span>
                <span className="contexto__nome"><NomeComSelo i={k + 1} nome={e.nome} /></span>
              </Fragment>
            ))}
          </span>
        )}
        {outras.length > 0 && <span className="tag">Conjunto de {outras.length + 1}</span>}
        {ws.alterado && <span className="tag tag--accent">rascunho não salvo</span>}
      </div>
      <div className="contexto__estado">
        {ws.executando ? (
          <span className="contexto__run">
            <Zap size={14} aria-hidden /> {ws.tamanhoExecucao > 1 ? `Executando o conjunto (${ws.tamanhoExecucao} estratégias)…` : 'Executando o backtest…'}
          </span>
        ) : ws.desatualizado ? (
          <span className="contexto__run contexto__run--alerta">
            <CircleDot size={14} aria-hidden /> Parâmetros alterados — execute para atualizar
          </span>
        ) : r ? (
          <span className="contexto__ok">
            {r.em_cache ? 'Resultado em cache' : `Executado em ${segundos(r.tempo_ms)}`} · {r.bd.nome}
          </span>
        ) : null}
        {ws.desatualizado && !ws.executando && (
          <Button size="sm" variant="primary" onClick={ws.rodar} disabled={!ws.valido}>Executar</Button>
        )}
      </div>
    </div>
  )
}

export function ResultsView({ ws }: { ws: Workspace }) {
  const { selecionada, resultado: r } = ws
  const bdPronto = ws.bd?.estado === 'pronto'
  const [mesPorEstrategia, setMesPorEstrategia] = useState(false)

  if (ws.listaCarregando) {
    return <div className="vazio"><span className="skel" style={{ width: 220, height: 20, display: 'block' }} /></div>
  }

  if (!selecionada) {
    return (
      <div className="vazio reveal">
        <FlaskConical size={36} aria-hidden />
        <h2>Nenhuma estratégia selecionada</h2>
        <p>Crie a primeira estratégia no painel à esquerda. Ela nasce com os valores padrão e fica salva no projeto.</p>
      </div>
    )
  }

  return (
    <div className="resultados">
      <Contexto ws={ws} selecionada={selecionada} />
      {ws.executando && <div className="progresso" aria-hidden><span /></div>}

      {ws.erroExecucao && (
        <div className="erro-exec" role="alert">
          <AlertTriangle size={18} aria-hidden />
          <div>
            <b>Não foi possível executar o backtest.</b>
            <p>{ws.erroExecucao}</p>
          </div>
          <Button size="sm" onClick={ws.rodar} disabled={!ws.valido}>Tentar de novo</Button>
        </div>
      )}

      {!r && !ws.erroExecucao && (
        <>
          <KpiBoard resumo={null} diario={[]} />
          {!bdPronto && <p className="dica-carga">Carregando o BD padrão (≈ 6 s na primeira vez)…</p>}
        </>
      )}

      {r && (
        <div className={ws.executando ? 'resultados__corpo is-busy' : 'resultados__corpo'}>
          {r.resumo.operacoes === 0 ? (
            <div className="vazio vazio--bloco">
              <h2>Nenhuma operação com esses parâmetros</h2>
              <p>O motor não encontrou entradas no BD ativo. Tente uma janela maior, menos candles no gatilho ou outro “book”.</p>
            </div>
          ) : (
            <>
              <KpiBoard resumo={r.resumo} diario={r.diario} titulo={r.estrategias ? 'Resultado conjunto' : undefined} />

              {r.estrategias && r.diversificacao && (
                <PerformancePanel estrategias={r.estrategias} resumo={r.resumo} diversificacao={r.diversificacao} />
              )}

              <section className="bloco reveal" style={{ '--i': 2 } as CSSProperties} aria-labelledby="t-panorama">
                <header className="bloco__topo">
                  <div>
                    <h2 id="t-panorama" className="bloco__titulo">Panorama diário</h2>
                    <p className="bloco__sub">
                      {r.estrategias
                        ? 'Resultado conjunto de cada pregão (barras) e capital acumulado (linha). Clique na legenda para ver a curva de cada estratégia.'
                        : 'Resultado de cada pregão (barras) e capital acumulado (linha, eixo à direita).'}
                    </p>
                  </div>
                </header>
                <div className="bloco__corpo"><DailyOverviewChart diario={r.diario} estrategias={r.estrategias} /></div>
              </section>

              <section className="bloco reveal" style={{ '--i': 3 } as CSSProperties} aria-labelledby="t-mes">
                <header className="bloco__topo">
                  <div>
                    <h2 id="t-mes" className="bloco__titulo">Resultado por mês</h2>
                    {r.estrategias && mesPorEstrategia && <p className="bloco__sub">Cada cor é uma estratégia; o traço branco marca o total líquido do mês.</p>}
                  </div>
                  {r.estrategias && (
                    <button type="button" className="chip" aria-pressed={mesPorEstrategia} onClick={() => setMesPorEstrategia((v) => !v)}>
                      Por estratégia
                    </button>
                  )}
                </header>
                {r.estrategias && mesPorEstrategia && (
                  <ul className="corr-chips" aria-label="Legenda das estratégias">
                    {r.estrategias.map((e) => (
                      <li key={e.indice} style={{ listStyle: 'none' }}><NomeComSelo i={e.indice} nome={e.nome} principal={e.indice === 0} /></li>
                    ))}
                  </ul>
                )}
                <div className="bloco__corpo"><MonthlyChart mensal={r.mensal} estrategias={r.estrategias} porEstrategia={mesPorEstrategia} /></div>
              </section>

              <DayExplorer resultado={r} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
