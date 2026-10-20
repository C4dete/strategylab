import type { CSSProperties } from 'react'
import type { ComponenteResumo, Diversificacao, Resumo } from '../../api/types'
import { InfoTip } from '../../components/ui/InfoTip'
import { brl, numero, pct, plural } from '../../lib/format'
import { identidade } from './identidade'
import { NomeComSelo } from './Selo'
import './correlacao.css'

const sinal = (v: number) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')

interface Props {
  estrategias: ComponenteResumo[]
  resumo: Resumo
  diversificacao: Diversificacao
}

/** "Desempenho por estratégia": o que cada uma entregou no resultado conjunto. Uma tabela, uma linha por estratégia + o conjunto. */
export function PerformancePanel({ estrategias, resumo, diversificacao }: Props) {
  const maior = Math.max(1, ...estrategias.map((e) => Math.abs(e.total_rs)))
  const { dd_conjunto: ddConj, soma_dd_isolados: somaDd } = diversificacao
  // quanto o drawdown do conjunto ficou menor do que a soma das quedas isoladas (só faz sentido com queda isolada)
  const ganhoDiv = somaDd < 0 ? Math.max(0, (1 - ddConj / somaDd) * 100) : 0

  return (
    <section className="bloco reveal" style={{ '--i': 1 } as CSSProperties} aria-labelledby="t-desemp">
      <header className="bloco__topo">
        <div>
          <div className="desemp__titulo">
            <h2 id="t-desemp" className="bloco__titulo">Desempenho por estratégia</h2>
            <InfoTip rotulo="Sobre o resultado conjunto">
          O conjunto é a <b>soma, pregão a pregão, de backtests independentes</b>: cada estratégia roda como se estivesse sozinha. Na conta real,
          posições opostas no mesmo ativo se compensam e dividem margem; isso não é simulado aqui.
          <br /><br />
          <b>Correlação</b>: do resultado diário contra a estratégia A, sobre todos os pregões do BD (zero onde não operou). Perto de 0, elas se
          complementam; perto de 1, andam juntas; negativa, uma compensa a outra.
            </InfoTip>
          </div>
          <p className="bloco__sub">O que cada uma entregou no resultado conjunto.</p>
        </div>
      </header>

      <div className="bloco__corpo desemp">
        <table className="desemp__tabela">
          <caption className="sr-only">Desempenho de cada estratégia no resultado conjunto</caption>
          <thead>
            <tr>
              <th scope="col">Estratégia</th>
              <th scope="col" className="cn">Resultado</th>
              <th scope="col" className="cn">Drawdown</th>
              <th scope="col" className="cn">Operações</th>
              <th scope="col" className="cn">Win rate</th>
              <th scope="col" className="cn" title="Correlação do resultado diário com a estratégia A">Corr. com A</th>
            </tr>
          </thead>
          <tbody>
            {estrategias.map((e) => (
              <tr key={e.indice}>
                <th scope="row" className="desemp__nome"><NomeComSelo i={e.indice} nome={e.nome} principal={e.indice === 0} /></th>
                <td className="cn desemp__res" data-rotulo="Resultado">
                  <b className={`mono ${sinal(e.total_rs)}`}>{brl(e.total_rs, { mais: true, casas: 0 })}</b>
                  <span className="desemp__barra" aria-hidden>
                    <i style={{ width: `${(Math.abs(e.total_rs) / maior) * 100}%`, background: identidade(e.indice).cor }} />
                  </span>
                </td>
                <td className="cn mono" data-rotulo="Drawdown">{brl(e.drawdown.rs, { casas: 0 })}</td>
                <td className="cn mono" data-rotulo="Operações">{numero(e.operacoes)}</td>
                <td className="cn mono" data-rotulo="Win rate">{pct(e.win_rate, 0)}</td>
                <td className="cn mono" data-rotulo="Corr. com A">{e.correlacao_principal === null ? '—' : numero(e.correlacao_principal, 2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="desemp__nome">Conjunto · {plural(estrategias.length, 'estratégia', 'estratégias')}</th>
              <td className="cn desemp__res" data-rotulo="Resultado"><b className={`mono ${sinal(resumo.total_rs)}`}>{brl(resumo.total_rs, { mais: true, casas: 0 })}</b></td>
              <td className="cn mono" data-rotulo="Drawdown">{brl(ddConj, { casas: 0 })}</td>
              <td className="cn mono" data-rotulo="Operações">{numero(resumo.operacoes)}</td>
              <td className="cn mono" data-rotulo="Win rate">{pct(resumo.win_rate, 0)}</td>
              <td className="cn mono" data-rotulo="Corr. com A">—</td>
            </tr>
          </tfoot>
        </table>
        {somaDd < 0 && (
          <p className="desemp__nota">
            O conjunto chega a <b className="mono neg">{brl(ddConj, { casas: 0 })}</b> de drawdown; somando as quedas isoladas seria{' '}
            <b className="mono">{brl(somaDd, { casas: 0 })}</b>
            {ganhoDiv >= 1 && <> ({numero(ganhoDiv, 0)}% a menos por se complementarem)</>}.
          </p>
        )}
      </div>
    </section>
  )
}
