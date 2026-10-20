import { useMemo } from 'react'
import type { ComponenteResumo, Diario } from '../../../api/types'
import { brl, dataBR, dataCurta, diaDaSemana, numero } from '../../../lib/format'
import { identidade } from '../../correlacao/identidade'
import { corDe, escapa, seloHtml } from '../../correlacao/seloHtml'
import { EChart } from './EChart'
import type { Option } from './echarts'
import { estiloEixo, estiloTooltip, FONTE_MONO, FONTE_UI, usePaleta } from './palette'

/**
 * Panorama diário: barras do resultado de cada pregão + curva de capital acumulada (eixo à direita).
 * No conjunto, o tooltip quebra o dia por estratégia e a legenda liga/desliga a curva acumulada de cada uma (desligadas por padrão).
 */
export function DailyOverviewChart({ diario, estrategias }: { diario: Diario[]; estrategias?: ComponenteResumo[] }) {
  const p = usePaleta()

  const option = useMemo<Option>(() => {
    const eixo = estiloEixo(p)
    const datas = diario.map((d) => d.data)
    const conj = estrategias && estrategias.length > 1 && diario.every((d) => d.rs_por) ? estrategias : null
    const nomeCurva = (e: ComponenteResumo) => `${identidade(e.indice).letra} · ${e.nome}`
    const acumuladas = conj
      ? conj.map((e) => {
          let acc = 0
          return diario.map((d) => (acc += d.rs_por?.[e.indice] ?? 0))
        })
      : []
    return {
      animationDuration: 700,
      animationEasing: 'cubicOut',
      grid: { left: 64, right: 76, top: 40, bottom: 66 },
      legend: {
        top: 4, right: 8, itemWidth: 14, itemHeight: 8, icon: 'rect',
        textStyle: { color: p.text2, fontFamily: FONTE_UI, fontSize: 12 },
        data: ['Resultado do dia', 'Capital acumulado', ...(conj ? conj.map(nomeCurva) : [])],
        selected: Object.fromEntries((conj ?? []).map((e) => [nomeCurva(e), false])),      // curvas individuais: ligam pela legenda
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
            (conj && d.rs_por
              ? `<div style="margin:6px 0;padding:6px 0;border-top:1px solid ${p.line};border-bottom:1px solid ${p.line}">` +
                conj
                  .map((e) => {
                    const v = d.rs_por?.[e.indice] ?? 0
                    return (
                      `<div style="display:flex;justify-content:space-between;gap:16px;align-items:center"><span>${seloHtml(p, e.indice)}${escapa(e.nome)}</span>` +
                      `<b style="font-family:${FONTE_MONO};color:${v > 0 ? p.gain : v < 0 ? p.loss : p.text3}">${v === 0 ? '—' : brl(v, { mais: true })}</b></div>`
                    )
                  })
                  .join('') +
                '</div>'
              : '') +
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
        ...(conj
          ? conj.map((e, k) => ({
              name: nomeCurva(e), type: 'line', yAxisIndex: 1, showSymbol: false, z: 4, silent: true,
              lineStyle: { color: corDe(p, e.indice), width: 1.4, ...(identidade(e.indice).repetida ? { type: 'dashed' as const } : {}) },
              itemStyle: { color: corDe(p, e.indice) },
              data: acumuladas[k],
            }))
          : []),
      ],
    }
  }, [diario, estrategias, p])

  const ultimo = diario[diario.length - 1]
  return (
    <EChart
      option={option}
      height={360}
      ariaLabel={`Resultado diário e capital acumulado em ${diario.length} pregões${ultimo ? `, terminando em ${brl(ultimo.acumulado)}` : ''}`}
    />
  )
}
