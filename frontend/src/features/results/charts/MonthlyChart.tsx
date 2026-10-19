import { useMemo } from 'react'
import type { Mensal } from '../../../api/types'
import { brl, mesCurto, mesLongo, numero, plural } from '../../../lib/format'
import { EChart } from './EChart'
import type { Option } from './echarts'
import { estiloEixo, estiloTooltip, FONTE_MONO, FONTE_UI, usePaleta } from './palette'

/** Resultado por mês, verde/vermelho conforme o sinal. */
export function MonthlyChart({ mensal }: { mensal: Mensal[] }) {
  const p = usePaleta()

  const option = useMemo<Option>(() => {
    const eixo = estiloEixo(p)
    return {
      animationDuration: 600,
      animationEasing: 'cubicOut',
      grid: { left: 64, right: 24, top: 16, bottom: 34 },
      tooltip: {
        ...estiloTooltip(p),
        trigger: 'axis',
        axisPointer: { type: 'shadow', shadowStyle: { color: p.line, opacity: 0.4 } },
        formatter: (params: unknown) => {
          const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? 0
          const m = mensal[i]
          if (!m) return ''
          const cor = m.rs >= 0 ? p.gain : p.loss
          return (
            `<div style="font-family:${FONTE_UI};min-width:170px">` +
            `<div style="color:${p.text3};margin-bottom:4px;text-transform:capitalize">${mesLongo(m.mes)}</div>` +
            `<b style="font-family:${FONTE_MONO};color:${cor};font-size:14px">${brl(m.rs, { mais: true })}</b>` +
            `<div style="color:${p.text3};margin-top:4px">${plural(m.dias, 'pregão', 'pregões')} · ${m.dias_positivos} no positivo</div></div>`
          )
        },
      },
      xAxis: {
        type: 'category', data: mensal.map((m) => m.mes), ...eixo, splitLine: { show: false },
        axisLabel: { ...eixo.axisLabel, formatter: (v: string) => mesCurto(v), hideOverlap: true },
      },
      yAxis: {
        type: 'value', ...eixo, axisLine: { show: false },
        axisLabel: { ...eixo.axisLabel, formatter: (v: number) => numero(v) },
      },
      series: [
        {
          type: 'bar', barMaxWidth: 22, barCategoryGap: '30%',
          data: mensal.map((m) => ({ value: m.rs, itemStyle: { color: m.rs >= 0 ? p.gain : p.loss } })),
        },
      ],
    }
  }, [mensal, p])

  return <EChart option={option} height={270} ariaLabel={`Resultado por mês em ${mensal.length} meses`} />
}
