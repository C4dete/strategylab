import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { useMemo, type CSSProperties, type ReactNode } from 'react'
import type { Diario, Resumo, Sequencia } from '../../api/types'
import { InfoTip } from '../../components/ui/InfoTip'
import { useCountUp } from '../../hooks/useCountUp'
import { brl, dataBR, diaDaSemana, numero, pct, plural, pts } from '../../lib/format'
import './KpiBoard.css'

const sinal = (v: number) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')
const indice = (i: number) => ({ '--i': i }) as CSSProperties

function Sparkline({ diario, positivo }: { diario: Diario[]; positivo: boolean }) {
  const d = useMemo(() => {
    if (diario.length < 2) return null
    const passo = Math.max(1, Math.ceil(diario.length / 140))
    const pontos = diario.filter((_, i) => i % passo === 0 || i === diario.length - 1).map((x) => x.acumulado)
    const min = Math.min(0, ...pontos)
    const max = Math.max(0, ...pontos)
    const h = max - min || 1
    const xy = pontos.map((v, i) => [(i / (pontos.length - 1)) * 100, 28 - ((v - min) / h) * 26 - 1] as const)
    const linha = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`).join(' ')
    const zero = 28 - ((0 - min) / h) * 26 - 1
    return { linha, area: `${linha} L100 ${zero.toFixed(2)} L0 ${zero.toFixed(2)} Z`, zero }
  }, [diario])
  if (!d) return null
  return (
    <svg className="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden>
      <line x1="0" x2="100" y1={d.zero} y2={d.zero} className="spark__zero" vectorEffect="non-scaling-stroke" />
      <path d={d.area} className={positivo ? 'spark__area spark__area--pos' : 'spark__area spark__area--neg'} />
      <path d={d.linha} className={positivo ? 'spark__line spark__line--pos' : 'spark__line spark__line--neg'} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

function Kpi({ rotulo, dica, i, children }: { rotulo: string; dica?: ReactNode; i: number; children: ReactNode }) {
  return (
    <article className="kpi reveal" style={indice(i)}>
      <header className="kpi__topo">
        <h3 className="label">{rotulo}</h3>
        {dica && <InfoTip rotulo={`Sobre ${rotulo}`} alinhar="dir">{dica}</InfoTip>}
      </header>
      {children}
    </article>
  )
}

function Seq({ tipo, s }: { tipo: 'ganho' | 'perda'; s: Sequencia | null }) {
  const Icone = tipo === 'ganho' ? ArrowUpRight : ArrowDownRight
  const cor = tipo === 'ganho' ? 'pos' : 'neg'
  if (!s) {
    return (
      <div className="seq seq--vazia">
        <Icone size={16} aria-hidden />
        <span>{tipo === 'ganho' ? 'Nenhum pregão positivo' : 'Nenhum pregão negativo'}</span>
      </div>
    )
  }
  return (
    <div className="seq">
      <Icone size={18} className={cor} aria-hidden />
      <div>
        <p className="seq__linha">
          <b className="mono">{plural(s.dias, 'dia', 'dias')}</b>
          <span className="seq__tipo">{tipo === 'ganho' ? 'ganhando' : 'perdendo'}</span>
          <b className={`mono ${cor}`}>{brl(s.total, { mais: true, casas: 0 })}</b>
        </p>
        <p className="kpi__sub">
          {dataBR(s.inicio)} → {dataBR(s.fim)}
        </p>
      </div>
    </div>
  )
}

interface Props {
  resumo: Resumo | null
  diario: Diario[]
}

export function KpiBoard({ resumo, diario }: Props) {
  const total = useCountUp(resumo?.total_rs ?? 0)

  if (!resumo) {
    return (
      <section className="kpis" aria-label="Resultados principais" aria-busy="true">
        <div className="kpi kpi--hero skel" />
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="kpi skel" />
        ))}
      </section>
    )
  }

  const { drawdown: dd } = resumo
  const temDd = dd.rs < 0 && dd.pico !== null && dd.fundo !== null

  return (
    <section className="kpis" aria-label="Resultados principais">
      <article className="kpi kpi--hero reveal" style={indice(0)}>
        <header className="kpi__topo">
          <h3 className="label">Resultado total</h3>
        </header>
        <p className={`kpi__hero mono ${sinal(resumo.total_rs)}`}>{brl(total)}</p>
        <p className="kpi__sub">
          <span className="mono">{pts(resumo.total_pts, { mais: true })}</span> pts · {plural(resumo.operacoes, 'operação', 'operações')} em{' '}
          {plural(resumo.pregoes_operados, 'pregão', 'pregões')}
        </p>
        <Sparkline diario={diario} positivo={resumo.total_rs >= 0} />
      </article>

      <Kpi
        i={1}
        rotulo="Drawdown máximo"
        dica="A maior queda do topo ao fundo da curva de capital, medida no fechamento de cada pregão. Não mede o vale dentro do dia."
      >
        <p className={`kpi__valor mono ${temDd ? 'neg' : ''}`}>{brl(dd.rs)}</p>
        <p className="kpi__sub">{temDd ? <><span className="mono">{pts(dd.pts)}</span> pts</> : 'A curva nunca caiu'}</p>
      </Kpi>

      <Kpi
        i={2}
        rotulo="Win rate (por operação)"
        dica="Gains ÷ (gains + losses). Posições zeradas a mercado, por horário ou fim dos dados, não entram na conta."
      >
        <p className="kpi__valor mono">{pct(resumo.win_rate)}</p>
        <p className="kpi__sub">
          <span className="mono pos">{numero(resumo.ganhos)}</span> gains ·{' '}
          <span className="mono neg">{numero(resumo.perdas)}</span> losses
          {resumo.zeradas > 0 && <> · <span className="mono">{numero(resumo.zeradas)}</span> zeradas</>}
        </p>
      </Kpi>

      <Kpi i={3} rotulo="Melhor dia">
        <p className={`kpi__valor mono ${sinal(resumo.melhor_dia?.rs ?? 0)}`}>{resumo.melhor_dia ? brl(resumo.melhor_dia.rs, { mais: true }) : '—'}</p>
        <p className="kpi__sub">{resumo.melhor_dia ? `${dataBR(resumo.melhor_dia.data)} · ${diaDaSemana(resumo.melhor_dia.data)}` : '—'}</p>
      </Kpi>

      <Kpi i={4} rotulo="Pior dia">
        <p className={`kpi__valor mono ${sinal(resumo.pior_dia?.rs ?? 0)}`}>{resumo.pior_dia ? brl(resumo.pior_dia.rs) : '—'}</p>
        <p className="kpi__sub">{resumo.pior_dia ? `${dataBR(resumo.pior_dia.data)} · ${diaDaSemana(resumo.pior_dia.data)}` : '—'}</p>
      </Kpi>

      <Kpi
        i={5}
        rotulo="Período do drawdown"
        dica="Do topo anterior até o fundo do maior drawdown, contado em pregões com operação. É quanto tempo a curva ficaria abaixo da marca d'água."
      >
        <p className="kpi__valor mono">{temDd ? plural(dd.pregoes, 'pregão', 'pregões') : '—'}</p>
        <p className="kpi__sub">{temDd ? `${dataBR(dd.pico)} → ${dataBR(dd.fundo)}` : 'Sem drawdown'}</p>
      </Kpi>

      <Kpi
        i={6}
        rotulo="Sequências de dias"
        dica="A maior sequência de pregões seguidos fechando no positivo e no negativo. Pregões sem operação não contam."
      >
        <div className="seqs">
          <Seq tipo="ganho" s={resumo.seq_ganho} />
          <Seq tipo="perda" s={resumo.seq_perda} />
        </div>
      </Kpi>
    </section>
  )
}
