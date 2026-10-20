import { useMemo } from 'react'
import type { ComponenteResumo, Mensal } from '../../../api/types'
import { brl, mesCurto, mesLongo, numero, plural } from '../../../lib/format'
import { identidade } from '../../correlacao/identidade'
import { corDe, escapa, seloHtml } from '../../correlacao/seloHtml'
import { EChart } from './EChart'
import type { Option } from './echarts'
import { estiloEixo, estiloTooltip, FONTE_MONO, FONTE_UI, usePaleta } from './palette'

/** Mês em que o BD tem pregões e a estratégia não operou: o servidor devolve a linha zerada com `operado: false`. */
const semOperacao = (m: Mensal) => m.operado === false

interface Props {
  mensal: Mensal[]
  /** Só no conjunto. */
  estrategias?: ComponenteResumo[]
  /** Barras empilhadas, uma cor por estratégia (só faz sentido no conjunto). */
  porEstrategia?: boolean
}

/**
 * Resultado por mês. Padrão: verde/vermelho conforme o sinal. Mês sem operação = barra baixa e cinza, com o mesmo tooltip (zerado).
 * Com `porEstrategia`: barras empilhadas, a cor de cada estratégia na mesma barra, e um traço marcando o total líquido do mês.
 */
export function MonthlyChart({ mensal, estrategias, porEstrategia = false }: Props) {
  const p = usePaleta()
  const vazios = useMemo(() => mensal.filter(semOperacao).length, [mensal])
  const empilhado = porEstrategia && !!estrategias && estrategias.length > 0 && mensal.every((m) => m.rs_por)

  const option = useMemo<Option>(() => {
    const eixo = estiloEixo(p)

    const tooltip = {
      ...estiloTooltip(p),
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: p.line, opacity: 0.4 } },
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? 0
        const m = mensal[i]
        if (!m) return ''
        const vazio = semOperacao(m)
        const cor = vazio ? p.text3 : m.rs >= 0 ? p.gain : p.loss
        const quebra = empilhado && estrategias && m.rs_por
          ? `<div style="margin:6px 0;padding:6px 0;border-top:1px solid ${p.line};border-bottom:1px solid ${p.line}">` +
            estrategias
              .map((e) => {
                const v = m.rs_por?.[e.indice] ?? 0
                return (
                  `<div style="display:flex;justify-content:space-between;gap:16px;align-items:center"><span>${seloHtml(p, e.indice)}${escapa(e.nome)}</span>` +
                  `<b style="font-family:${FONTE_MONO};color:${v > 0 ? p.gain : v < 0 ? p.loss : p.text3}">${brl(v, { mais: true, casas: 0 })}</b></div>`
                )
              })
              .join('') +
            '</div>'
          : ''
        return (
          `<div style="font-family:${FONTE_UI};min-width:${empilhado ? 220 : 170}px">` +
          `<div style="color:${p.text3};margin-bottom:4px">${mesLongo(m.mes).replace(/^./, (c) => c.toUpperCase())}</div>` +
          (empilhado ? `<div style="color:${p.text3};font-size:11px">Total do mês</div>` : '') +
          `<b style="font-family:${FONTE_MONO};color:${cor};font-size:14px">${brl(m.rs, { mais: !vazio })}</b>` +
          quebra +
          `<div style="color:${p.text3};margin-top:${quebra ? 0 : 4}px">${plural(m.dias, 'pregão', 'pregões')} · ${m.dias_positivos} no positivo</div>` +
          (vazio ? `<div style="color:${p.text3};margin-top:2px">Sem operações no mês</div>` : '') +
          '</div>'
        )
      },
    }

    const series = empilhado && estrategias
      ? [
          ...estrategias.map((e) => {
            const cor = corDe(p, e.indice)
            const repetida = identidade(e.indice).repetida
            return {
              name: e.nome, type: 'bar', stack: 'mes', barMaxWidth: 22, barCategoryGap: '30%',
              itemStyle: { color: cor, ...(repetida ? { borderColor: p.text, borderWidth: 1, borderType: 'dashed' as const } : {}) },
              data: mensal.map((m) => m.rs_por?.[e.indice] ?? 0),
            }
          }),
          // mês zerado ainda aparece como uma barra baixa e cinza
          {
            name: 'Sem operação', type: 'bar', stack: 'mes', barMaxWidth: 22, barMinHeight: 4,
            itemStyle: { color: p.neutroBarra },
            data: mensal.map((m) => (semOperacao(m) ? 0 : null)),
          },
          // o líquido do mês (positivos e negativos se compensam dentro da barra)
          {
            name: 'Total do mês', type: 'scatter', symbol: 'rect', symbolSize: [24, 3], z: 5,
            itemStyle: { color: p.text, borderColor: p.surface, borderWidth: 0.5 },
            data: mensal.map((m) => (semOperacao(m) ? null : m.rs)),
          },
        ]
      : [
          {
            type: 'bar', barMaxWidth: 22, barCategoryGap: '30%', barMinHeight: 4,      // mês zerado ainda aparece como uma barra baixa
            data: mensal.map((m) => ({
              value: m.rs,
              itemStyle: semOperacao(m) ? { color: p.neutroBarra } : { color: m.rs >= 0 ? p.gain : p.loss },
            })),
          },
        ]

    return {
      animationDuration: 600,
      animationEasing: 'cubicOut',
      grid: { left: 64, right: 24, top: 16, bottom: 34 },
      tooltip,
      xAxis: {
        type: 'category', data: mensal.map((m) => m.mes), ...eixo, splitLine: { show: false },
        axisLabel: { ...eixo.axisLabel, formatter: (v: string) => mesCurto(v), hideOverlap: true },
      },
      yAxis: {
        type: 'value', ...eixo, axisLine: { show: false },
        axisLabel: { ...eixo.axisLabel, formatter: (v: number) => numero(v) },
      },
      series,
    }
  }, [mensal, estrategias, empilhado, p])

  return (
    <EChart
      option={option}
      height={270}
      ariaLabel={
        `Resultado por mês em ${mensal.length} meses${vazios ? `, ${plural(vazios, 'mês', 'meses')} sem operação` : ''}` +
        (empilhado && estrategias ? `, uma cor por estratégia (${estrategias.map((e) => `${identidade(e.indice).letra} ${e.nome}`).join(', ')})` : '')
      }
    />
  )
}
