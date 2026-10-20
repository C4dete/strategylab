import type { ComponenteResumo, Desfecho, Operacao } from '../../api/types'
import { brl, numero, plural, pts } from '../../lib/format'
import { NomeComSelo, Selo } from '../correlacao/Selo'

function Desfechos({ d, zeragem, saida }: { d: Desfecho; zeragem: string | null; saida: string }) {
  switch (d) {
    case 'gain':
      return <span className="badge badge--gain">Gain</span>
    case 'loss':
      return <span className="badge badge--loss">Loss</span>
    case 'time_close':
      // no conjunto cada estratégia tem a sua zeragem: o horário vem da própria operação
      return zeragem ? <span className="badge badge--neutro">Zerada {zeragem}</span> : <span className="badge badge--neutro" title={`Zerada às ${saida}`}>Zerada</span>
    default:
      return <span className="badge badge--neutro">Fim dos dados</span>
  }
}

interface Props {
  operacoes: Operacao[]
  /** Horário de zeragem da principal; null no conjunto (cada estratégia zera no seu). */
  zeragem: string | null
  /** Filtro de afastamento ligado: mostra o candle de referência e o afastamento de cada entrada. */
  mostrarFiltro: boolean
  periodoMM: number
  /** Só no conjunto: as operações aparecem em seções, uma por estratégia, cada linha com o selo dela. */
  estrategias?: ComponenteResumo[]
  /** Há estratégias escondidas pelos chips: o total é só do que está visível. */
  filtrado?: boolean
}

const sinal = (v: number) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')

export function TradesTable({ operacoes, zeragem, mostrarFiltro, periodoMM, estrategias, filtrado }: Props) {
  const total = operacoes.reduce((s, o) => s + o.rs, 0)
  const totalPts = operacoes.reduce((s, o) => s + o.pts, 0)
  const conj = !!estrategias && estrategias.length > 1
  const colunas = 10 + (mostrarFiltro ? 1 : 0)

  // seções por estratégia, na ordem A, B, C… (dentro de cada uma, a ordem do dia)
  const grupos = conj
    ? (estrategias ?? [])
        .map((e) => ({ e, ops: operacoes.filter((o) => (o.estrategia ?? 0) === e.indice) }))
        .filter((g) => g.ops.length > 0)
    : [{ e: null, ops: operacoes }]

  const linha = (o: Operacao) => (
    <tr key={`${o.estrategia ?? 0}-${o.data}-${o.ciclo}-${o.reversao}-${o.entrada}`}>
      <td className="cn mono">
        {conj && <Selo i={o.estrategia ?? 0} />}{' '}
        {o.ciclo}{o.reversao > 0 && <span className="sub" title={`Reversão nº ${o.reversao} deste ciclo`}> ↺{o.reversao}</span>}
      </td>
      <td>
        <span className={`lado lado--${o.lado}`}>{o.lado === 'buy' ? 'Compra' : 'Venda'}</span>
      </td>
      <td className="mono">{o.entrada}</td>
      <td className="cn mono">{numero(o.preco_entrada)}</td>
      <td className="mono">{o.saida}</td>
      <td className="cn mono">{numero(o.preco_saida)}</td>
      <td className="cn mono">{o.contratos}</td>
      <td className={`cn mono ${sinal(o.pts)}`}>{pts(o.pts, { mais: true })}</td>
      <td className={`cn mono ${sinal(o.rs)}`}>{brl(o.rs, { mais: true })}</td>
      <td>
        <Desfechos d={o.desfecho} zeragem={zeragem} saida={o.saida} />
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
  )

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
            {mostrarFiltro && <th scope="col" title={conj ? 'Candle de referência e afastamento até a MM da estratégia, em × media_operacao' : `Candle de referência e afastamento até a MM ${periodoMM}, em × media_operacao`}>Afast. MM</th>}
          </tr>
        </thead>
        {grupos.map((g) => (
          <tbody key={g.e?.indice ?? 'unico'}>
            {g.e && (
              <tr className="tabela__grupo">
                <th scope="rowgroup" colSpan={colunas}>
                  <div className="tabela__grupo-linha">
                    <NomeComSelo i={g.e.indice} nome={g.e.nome} principal={g.e.indice === 0} />
                    <span className="tabela__grupo-resumo">
                      <span>{plural(g.ops.length, 'operação', 'operações')}</span>
                      <b className={`mono ${sinal(g.ops.reduce((s, o) => s + o.rs, 0))}`}>{brl(g.ops.reduce((s, o) => s + o.rs, 0), { mais: true })}</b>
                    </span>
                  </div>
                </th>
              </tr>
            )}
            {g.ops.map(linha)}
          </tbody>
        ))}
        {operacoes.length > 1 && (
          <tfoot>
            <tr>
              <th scope="row" colSpan={7}>{conj ? (filtrado ? 'Total do que está visível' : 'Total do dia (conjunto)') : 'Total do dia'}</th>
              <td className={`cn mono ${sinal(totalPts)}`}>{pts(totalPts, { mais: true })}</td>
              <td className={`cn mono ${sinal(total)}`}>{brl(total, { mais: true })}</td>
              <td />
              {mostrarFiltro && <td />}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
