import { useMemo } from 'react'
import type { BarraDia, ComponenteResumo, Operacao, Params } from '../../api/types'
import { brl, numero, pts } from '../../lib/format'
import { identidade } from '../correlacao/identidade'
import { corDe, escapa, seloHtml } from '../correlacao/seloHtml'
import { EChart } from '../results/charts/EChart'
import type { Option } from '../results/charts/echarts'
import { estiloEixo, estiloTooltip, FONTE_MONO, FONTE_UI, usePaleta } from '../results/charts/palette'

interface Props {
  barras: BarraDia[]
  operacoes: Operacao[]
  /** Parâmetros da principal (A): indicadores, janela e candle de referência são dela. */
  params: Params
  timeframeMin: number
  /** Só no conjunto: marcadores na cor/letra de cada estratégia. */
  estrategias?: ComponenteResumo[]
}

/** "16:07" -> "16:00" (a barra de `tf` minutos que contém o horário). */
function barraDe(hhmm: string, tf: number): string {
  const [h, m] = hhmm.split(':').map(Number)
  const total = (h ?? 0) * 60 + (m ?? 0)
  const b = Math.floor(total / tf) * tf
  return `${String(Math.floor(b / 60)).padStart(2, '0')}:${String(b % 60).padStart(2, '0')}`
}

const ROTULO_DESFECHO: Record<string, string> = {
  gain: 'Gain', loss: 'Loss', time_close: 'Zerada', eod: 'Fim dos dados',
}

const linha = (rotulo: string, valor: string, cor?: string) =>
  `<div style="display:flex;justify-content:space-between;gap:16px"><span>${rotulo}</span>` +
  `<b style="font-family:${FONTE_MONO};${cor ? `color:${cor}` : ''}">${valor}</b></div>`

/**
 * Candles de 10 min do pregão + média móvel, Bandas de Bollinger, entradas/saídas e as linhas de início / última entrada /
 * zeragem. Os indicadores são plotados como as plataformas fazem: o valor de cada barra é o do FECHAMENTO dela. As regras
 * do motor leem o valor da barra anterior — por isso, com o filtro ligado, o candle de referência de cada entrada é destacado.
 */
export function DayChart({ barras, operacoes, params, timeframeMin, estrategias }: Props) {
  const p = usePaleta()
  const conj = !!estrategias && estrategias.length > 1

  const option = useMemo<Option>(() => {
    const eixo = estiloEixo(p)
    const cats = barras.map((b) => b.t)
    const existe = (t: string) => cats.includes(t)
    const temInd = barras.some((b) => b.mm != null || b.bbm != null)
    const nomeMM = `MM ${params.mm_periodo}`
    const nomeBB = `Bollinger ${params.bb_periodo} · ${numero(params.bb_desvio, 1)}`

    const marcas = [
      { hhmm: params.janela_inicio, nome: 'início', cor: p.gain },
      ...(params.ultima_entrada ? [{ hhmm: params.ultima_entrada, nome: 'última entrada', cor: p.accent }] : []),
      { hhmm: params.janela_fim, nome: 'zeragem', cor: p.loss },
    ]
      .map((m) => ({ ...m, barra: barraDe(m.hhmm, timeframeMin) }))
      .filter((m) => existe(m.barra))

    const idx = (o: Operacao) => o.estrategia ?? 0
    const entradas = operacoes.map((o) => ({
      value: [o.entrada_barra, o.preco_entrada],
      symbol: 'triangle',
      symbolRotate: o.lado === 'sell' ? 180 : 0,
      op: o,
      // no conjunto: a entrada leva a cor e a letra da estratégia (a letra fica abaixo da compra e acima da venda)
      ...(conj
        ? {
            itemStyle: { color: corDe(p, idx(o)), borderColor: p.surface, borderWidth: 1.5 },
            label: {
              show: true, formatter: identidade(idx(o)).letra, color: corDe(p, idx(o)), fontFamily: FONTE_MONO, fontSize: 10, fontWeight: 700,
              position: o.lado === 'buy' ? 'bottom' : 'top', distance: 4,
            },
          }
        : {}),
    }))
    const saidas = operacoes.map((o) => ({
      value: [o.saida_barra, o.preco_saida],
      // a cor de resultado (gain/loss) fica no preenchimento; no conjunto, o contorno é o da estratégia
      itemStyle: {
        color: o.desfecho === 'gain' ? p.gain : o.desfecho === 'loss' ? p.loss : p.text3,
        ...(conj ? { borderColor: corDe(p, idx(o)), borderWidth: 2.5 } : {}),
      },
      op: o,
    }))

    const ligacoes = operacoes.map((o, i) => ({
      name: `op${i}`,
      type: 'line',
      silent: true,
      symbol: 'none',
      z: 2,
      lineStyle: { color: o.pts > 0 ? p.gain : o.pts < 0 ? p.loss : p.text3, width: 1.5, type: 'dashed' },
      data: [[o.entrada_barra, o.preco_entrada], [o.saida_barra, o.preco_saida]],
    }))

    // candle de referência de cada entrada (só existe com o filtro ligado): a faixa cobre a barra inteira
    const refs = [...new Set(operacoes.flatMap((o) => (o.ref && (!conj || idx(o) === 0) ? [o.ref.barra] : [])))]       // a referência é da principal
      .map((t) => cats.indexOf(t))
      .filter((i) => i >= 0)
    const areasRef = refs.map((i) => [{ xAxis: i - 0.5 }, { xAxis: i + 0.5 }])

    const serie = (chave: 'mm' | 'bbm' | 'bbs' | 'bbi') => barras.map((b) => b[chave] ?? null)
    const indicadores = temInd
      ? [
          {
            name: nomeMM, type: 'line', silent: true, symbol: 'none', z: 3, connectNulls: false,
            lineStyle: { color: p.accent, width: 1.8 }, itemStyle: { color: p.accent }, data: serie('mm'),
          },
          ...(['bbs', 'bbi'] as const).map((k) => ({
            name: nomeBB, type: 'line', silent: true, symbol: 'none', z: 2, connectNulls: false,
            lineStyle: { color: p.text2, width: 1, type: 'dashed' }, itemStyle: { color: p.text2 }, data: serie(k),
          })),
          ...(params.bb_periodo !== params.mm_periodo
            ? [{
                name: nomeBB, type: 'line', silent: true, symbol: 'none', z: 2, connectNulls: false,
                lineStyle: { color: p.text3, width: 1, type: 'dotted' }, itemStyle: { color: p.text3 }, data: serie('bbm'),
              }]
            : []),
        ]
      : []

    return {
      animationDuration: 500,
      grid: { left: 64, right: 24, top: temInd ? 40 : 28, bottom: 34 },
      legend: temInd
        ? {
            top: 4, right: 8, itemWidth: 16, itemHeight: 8, icon: 'rect',
            textStyle: { color: p.text2, fontFamily: FONTE_UI, fontSize: 12 },
            data: [nomeMM, nomeBB],
          }
        : undefined,
      tooltip: {
        ...estiloTooltip(p),
        trigger: 'item',
        formatter: (raw: unknown) => {
          const q = raw as { seriesType: string; seriesName: string; data: { op?: Operacao }; dataIndex: number }
          if (q.seriesType === 'candlestick') {
            const b = barras[q.dataIndex]
            if (!b) return ''
            const cor = b.c >= b.o ? p.gain : p.loss
            const ind = temInd
              ? `<div style="margin-top:6px;padding-top:6px;border-top:1px solid ${p.line};color:${p.text3}">no fechamento da barra</div>` +
                [[nomeMM, b.mm], ['Banda sup.', b.bbs], ['Banda inf.', b.bbi]]
                  .map(([r, v]) => linha(String(r), v == null ? '—' : numero(Number(v), 0)))
                  .join('')
              : ''
            return (
              `<div style="font-family:${FONTE_UI};min-width:170px"><div style="color:${p.text3};margin-bottom:4px">Barra ${b.t}</div>` +
              linha('Abertura', numero(b.o)) + linha('Máxima', numero(b.h)) + linha('Mínima', numero(b.l)) + linha('Tamanho', `${numero(b.h - b.l)} pts`) +
              linha('Fechamento', numero(b.c), cor) + ind + '</div>'
            )
          }
          const o = q.data.op
          if (!o) return ''
          const entrada = q.seriesName === 'Entradas'
          const ref = entrada && o.ref
            ? `<div style="margin-top:6px;padding-top:6px;border-top:1px solid ${p.line}"><div style="color:${p.text3}">Filtro · candle de referência ${o.ref.barra}</div>` +
              (o.ref.mm != null ? linha(`MM ${params.mm_periodo} (fech. ref.)`, numero(o.ref.mm, 0)) : '') +
              (o.ref.afast_pts != null ? linha('Afastamento', `${numero(o.ref.afast_pts, 0)} pts${o.ref.afast_x != null ? ` · ${numero(o.ref.afast_x, 2)}×` : ''}`) : '') +
              '</div>'
            : ''
          const dona = conj && estrategias
            ? `<div style="margin-bottom:6px">${seloHtml(p, idx(o))}<b>${escapa(estrategias[idx(o)]?.nome ?? '')}</b></div>`
            : ''
          return (
            `<div style="font-family:${FONTE_UI};min-width:190px">${dona}<div style="color:${p.text3};margin-bottom:4px">` +
            `${entrada ? 'Entrada' : 'Saída'} · ${entrada ? o.entrada : o.saida}</div>` +
            `<b>${o.lado === 'buy' ? 'Compra' : 'Venda'}</b> ${entrada ? `a ${numero(o.preco_entrada)}` : `a ${numero(o.preco_saida)} · ${ROTULO_DESFECHO[o.desfecho]}${o.saida_por === 'mm' ? ' · na MM' : o.saida_por === 'trailing' ? ' · no trailing' : o.saida_por === 'tempo' ? ' · por tempo' : ''}`}` +
            (entrada
              ? ''
              : `<div style="margin-top:4px;font-family:${FONTE_MONO};color:${o.pts >= 0 ? p.gain : p.loss}">${pts(o.pts, { mais: true })} pts · ${brl(o.rs, { mais: true })}</div>`) +
            ref + '</div>'
          )
        },
      },
      xAxis: {
        type: 'category', data: cats, boundaryGap: true, ...eixo, splitLine: { show: false },
        axisLabel: { ...eixo.axisLabel, hideOverlap: true },
      },
      yAxis: {
        type: 'value', scale: true, ...eixo, axisLine: { show: false },
        axisLabel: { ...eixo.axisLabel, formatter: (v: number) => numero(v) },
      },
      series: [
        {
          name: 'Candles', type: 'candlestick', z: 1,
          data: barras.map((b) => [b.o, b.c, b.l, b.h]),
          itemStyle: { color: p.gain, color0: p.loss, borderColor: p.gain, borderColor0: p.loss },
          markArea: areasRef.length
            ? {
                silent: true, animation: false,
                itemStyle: { color: p.accent, opacity: 0.16, borderColor: p.accent, borderWidth: 1, borderType: 'dashed' },
                label: { show: true, formatter: 'ref', position: 'insideTop', color: p.accent, fontFamily: FONTE_MONO, fontSize: 10 },
                data: areasRef,
              }
            : undefined,
          markLine: {
            silent: true, symbol: 'none', animation: false,
            data: marcas.map((m) => ({
              xAxis: m.barra, lineStyle: { color: m.cor, type: 'dotted', width: 1.5 },
              label: { formatter: `${m.nome} ${m.hhmm}`, color: m.cor, fontFamily: FONTE_MONO, fontSize: 10, position: 'insideEndTop' },
            })),
          },
        },
        ...indicadores,
        ...ligacoes,
        {
          name: 'Entradas', type: 'scatter', z: 5, symbolSize: 13,
          itemStyle: { color: p.text, borderColor: p.surface, borderWidth: 1.5 },
          data: entradas,
        },
        { name: 'Saídas', type: 'scatter', z: 5, symbolSize: 10, itemStyle: { borderColor: p.surface, borderWidth: 1.5 }, data: saidas },
      ],
    }
  }, [barras, operacoes, params, timeframeMin, estrategias, conj, p])

  return <EChart option={option} height={400} ariaLabel={`Candles do pregão com ${operacoes.length} operação(ões)${conj ? ` de ${estrategias?.length} estratégias, marcadas por letra e cor` : ''}`} />
}
