import { AlertTriangle, CircleDot, FlaskConical, Zap } from 'lucide-react'
import type { CSSProperties } from 'react'
import type { Estrategia } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { segundos } from '../../lib/format'
import { DayExplorer } from '../day/DayExplorer'
import { DailyOverviewChart } from './charts/DailyOverviewChart'
import { MonthlyChart } from './charts/MonthlyChart'
import { KpiBoard } from './KpiBoard'
import './ResultsView.css'
import type { Workspace } from '../../hooks/useWorkspace'

function Contexto({ ws, selecionada }: { ws: Workspace; selecionada: Estrategia }) {
  const r = ws.resultado
  return (
    <div className="contexto" role="status" aria-live="polite">
      <div className="contexto__id">
        <FlaskConical size={16} aria-hidden />
        <span className="contexto__nome">{selecionada.nome}</span>
        {ws.alterado && <span className="tag tag--accent">rascunho não salvo</span>}
      </div>
      <div className="contexto__estado">
        {ws.executando ? (
          <span className="contexto__run"><Zap size={14} aria-hidden /> Executando o backtest…</span>
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
              <KpiBoard resumo={r.resumo} diario={r.diario} />

              <section className="bloco reveal" style={{ '--i': 1 } as CSSProperties} aria-labelledby="t-panorama">
                <header className="bloco__topo">
                  <div>
                    <h2 id="t-panorama" className="bloco__titulo">Panorama diário</h2>
                    <p className="bloco__sub">Resultado de cada pregão (barras) e capital acumulado (linha, eixo à direita).</p>
                  </div>
                </header>
                <div className="bloco__corpo"><DailyOverviewChart diario={r.diario} /></div>
              </section>

              <section className="bloco reveal" style={{ '--i': 2 } as CSSProperties} aria-labelledby="t-mes">
                <header className="bloco__topo">
                  <div>
                    <h2 id="t-mes" className="bloco__titulo">Resultado por mês</h2>
                  </div>
                </header>
                <div className="bloco__corpo"><MonthlyChart mensal={r.mensal} /></div>
              </section>

              <DayExplorer resultado={r} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
