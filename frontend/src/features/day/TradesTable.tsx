import type { Desfecho, Operacao } from '../../api/types'
import { brl, numero, pts } from '../../lib/format'

function Desfechos({ d, zeragem }: { d: Desfecho; zeragem: string }) {
  switch (d) {
    case 'gain':
      return <span className="badge badge--gain">Gain</span>
    case 'loss':
      return <span className="badge badge--loss">Loss</span>
    case 'time_close':
      return <span className="badge badge--neutro">Zerada {zeragem}</span>
    default:
      return <span className="badge badge--neutro">Fim dos dados</span>
  }
}

interface Props {
  operacoes: Operacao[]
  zeragem: string
  /** Filtro de afastamento ligado: mostra o candle de referência e o afastamento de cada entrada. */
  mostrarFiltro: boolean
  periodoMM: number
}

export function TradesTable({ operacoes, zeragem, mostrarFiltro, periodoMM }: Props) {
  const total = operacoes.reduce((s, o) => s + o.rs, 0)
  const totalPts = operacoes.reduce((s, o) => s + o.pts, 0)

  return (
    <div className="tabela" role="region" aria-label="Operações do dia" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th scope="col" className="cn">Nº</th>
            <th scope="col">Lado</th>
            <th scope="col">Entrada</th>
            <th scope="col" className="cn">Preço entr.</th>
            <th scope="col">Saída</th>
            <th scope="col" className="cn">Preço saída</th>
            <th scope="col" className="cn">Contratos</th>
            <th scope="col" className="cn">Pts</th>
            <th scope="col" className="cn">Resultado</th>
            <th scope="col">Desfecho</th>
            {mostrarFiltro && <th scope="col" title={`Candle de referência e afastamento até a MM ${periodoMM}, em × media_operacao`}>Afast. MM</th>}
          </tr>
        </thead>
        <tbody>
          {operacoes.map((o) => (
            <tr key={`${o.data}-${o.ciclo}-${o.reversao}-${o.entrada}`}>
              <td className="cn mono">{o.ciclo}{o.reversao > 0 && <span className="sub" title={`Reversão nº ${o.reversao} deste ciclo`}> ↺{o.reversao}</span>}</td>
              <td>
                <span className={`lado lado--${o.lado}`}>{o.lado === 'buy' ? 'Compra' : 'Venda'}</span>
              </td>
              <td className="mono">{o.entrada}</td>
              <td className="cn mono">{numero(o.preco_entrada)}</td>
              <td className="mono">{o.saida}</td>
              <td className="cn mono">{numero(o.preco_saida)}</td>
              <td className="cn mono">{o.contratos}</td>
              <td className={`cn mono ${o.pts > 0 ? 'pos' : o.pts < 0 ? 'neg' : ''}`}>{pts(o.pts, { mais: true })}</td>
              <td className={`cn mono ${o.rs > 0 ? 'pos' : o.rs < 0 ? 'neg' : ''}`}>{brl(o.rs, { mais: true })}</td>
              <td>
                <Desfechos d={o.desfecho} zeragem={zeragem} />
                {o.saida_por === 'mm' && <span className="badge badge--neutro" title="Saiu ao tocar a média móvel">MM</span>}
                {o.saida_por === 'trailing' && <span className="badge badge--neutro" title="Saiu no stop protegido pelo trailing (mínima/máxima da última barra fechada)">Trail</span>}
                {o.saida_por === 'tempo' && <span className="badge badge--neutro" title="Saiu pelo tempo máximo na posição">Tempo</span>}
              </td>
              {mostrarFiltro && (
                <td className="mono" title={o.ref ? `Referência: barra ${o.ref.barra} · MM ${o.ref.mm != null ? numero(o.ref.mm) : '—'}` : undefined}>
                  {o.ref?.afast_x != null ? <>{numero(o.ref.afast_x, 2)}× <span className="sub">({numero(o.ref.afast_pts ?? 0)} pts · {o.ref.barra})</span></> : '—'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
        {operacoes.length > 1 && (
          <tfoot>
            <tr>
              <th scope="row" colSpan={7}>Total do dia</th>
              <td className={`cn mono ${totalPts > 0 ? 'pos' : totalPts < 0 ? 'neg' : ''}`}>{pts(totalPts, { mais: true })}</td>
              <td className={`cn mono ${total > 0 ? 'pos' : total < 0 ? 'neg' : ''}`}>{brl(total, { mais: true })}</td>
              <td />
              {mostrarFiltro && <td />}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
