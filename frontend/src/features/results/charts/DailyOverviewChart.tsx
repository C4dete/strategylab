import { useMemo } from 'react'
import type { Diario } from '../../../api/types'
import { brl, dataBR, dataCurta, diaDaSemana, numero } from '../../../lib/format'
import { EChart } from './EChart'
import type { Option } from './echarts'
import { estiloEixo, estiloTooltip, FONTE_MONO, FONTE_UI, usePaleta } from './palette'

/** Panorama diário: barras do resultado de cada pregão + curva de capital acumulada (eixo à direita). */
export function DailyOverviewChart({ diario }: { diario: Diario[] }) {
  const p = usePaleta()

  const option = useMemo<Option>(() => {
    const eixo = estiloEixo(p)
    const datas = diario.map((d) => d.data)
    return {
      animationDuration: 700,
      animationEasing: 'cubicOut',
      grid: { left: 64, right: 76, top: 40, bottom: 66 },
      legend: {
        top: 4, right: 8, itemWidth: 14, itemHeight: 8, icon: 'rect',
        textStyle: { color: p.text2, fontFamily: FONTE_UI, fontSize: 12 },
        data: ['Resultado do dia', 'Capital acumulado'],
      },
      tooltip: {
        ...estiloTooltip(p),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: p.text3, type: 'dashed' } },
        formatter: (params: unknown) => {
          const arr = params as { dataIndex: number }[]
          const i = arr[0]?.dataIndex ?? 0
          const d = diario[i]
          if (!d) return ''
          const cor = d.rs >= 0 ? p.gain : p.loss
          return (
            `<div style="font-family:${FONTE_UI};min-width:190px">` +
            `<div style="color:${p.text3};margin-bottom:4px">${dataBR(d.data)} · ${diaDaSemana(d.data)}</div>` +
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>Dia</span>` +
            `<b style="font-family:${FONTE_MONO};color:${cor}">${brl(d.rs, { mais: true })}</b></div>` +
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>Acumulado</span>` +
            `<b style="font-family:${FONTE_MONO}">${brl(d.acumulado)}</b></div>` +
            `<div style="color:${p.text3};margin-top:4px">${d.ganhos} gain · ${d.perdas} loss</div></div>`
          )
        },
      },
      xAxis: {
        type: 'category', data: datas, boundaryGap: true, ...eixo, splitLine: { show: false },
        axisLabel: { ...eixo.axisLabel, formatter: (v: string) => dataCurta(v), hideOverlap: true },
      },
      yAxis: [
        {
          type: 'value', ...eixo,
          axisLine: { show: false },
          axisLabel: { ...eixo.axisLabel, formatter: (v: number) => numero(v) },
        },
        {
          type: 'value', position: 'right', ...eixo,
          axisLine: { show: false }, splitLine: { show: false },
          axisLabel: { ...eixo.axisLabel, color: p.accent, formatter: (v: number) => numero(v) },
        },
      ],
      dataZoom: [
        { type: 'inside', filterMode: 'none', zoomOnMouseWheel: 'ctrl', moveOnMouseWheel: false },
        {
          type: 'slider', height: 22, bottom: 10, borderColor: p.line, backgroundColor: 'transparent',
          fillerColor: 'rgba(235,170,58,0.14)', handleSize: '100%',
          handleStyle: { color: p.accent, borderColor: p.accent },
          moveHandleStyle: { color: p.lineStrong },
          dataBackground: { lineStyle: { color: p.lineStrong }, areaStyle: { color: p.line } },
          selectedDataBackground: { lineStyle: { color: p.accent }, areaStyle: { color: p.accent, opacity: 0.2 } },
          textStyle: { color: p.text3, fontFamily: FONTE_MONO, fontSize: 10 },
          labelFormatter: (_: number, s: string) => dataCurta(s),
          filterMode: 'none',
        },
      ],
      series: [
        {
          name: 'Resultado do dia', type: 'bar', yAxisIndex: 0, barMaxWidth: 8, barCategoryGap: '25%',
          data: diario.map((d) => ({ value: d.rs, itemStyle: { color: d.rs >= 0 ? p.gain : p.loss } })),
        },
        {
          name: 'Capital acumulado', type: 'line', yAxisIndex: 1, showSymbol: false, z: 3,
          lineStyle: { color: p.accent, width: 2 }, itemStyle: { color: p.accent },
          areaStyle: { color: p.accent, opacity: 0.07 },
          data: diario.map((d) => d.acumulado),
        },
      ],
    }
  }, [diario, p])

  const ultimo = diario[diario.length - 1]
  return (
    <EChart
      option={option}
      height={360}
      ariaLabel={`Resultado diário e capital acumulado em ${diario.length} pregões${ultimo ? `, terminando em ${brl(ultimo.acumulado)}` : ''}`}
    />
  )
}
