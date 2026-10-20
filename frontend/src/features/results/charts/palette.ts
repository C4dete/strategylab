import { useMemo } from 'react'
import { useTheme } from '../../../hooks/useTheme'

export interface Paleta {
  text: string
  text2: string
  text3: string
  line: string
  lineStrong: string
  surface: string
  surface3: string
  accent: string
  gain: string
  loss: string
  gainWeak: string
  lossWeak: string
  /** Cor de cada estratégia do conjunto (A, B, C…), na ordem. */
  estrategia: string[]
  neutroBarra: string
}

function ler(): Paleta {
  const cs = getComputedStyle(document.documentElement)
  const v = (n: string) => cs.getPropertyValue(n).trim()
  return {
    text: v('--text'), text2: v('--text-2'), text3: v('--text-3'), line: v('--line'), lineStrong: v('--line-strong'),
    surface: v('--surface'), surface3: v('--surface-3'), accent: v('--accent'), gain: v('--gain'), loss: v('--loss'),
    gainWeak: v('--gain-weak'), lossWeak: v('--loss-weak'),
    estrategia: [1, 2, 3, 4, 5, 6].map((n) => v(`--e${n}`)), neutroBarra: v('--neutro-barra'),
  }
}

/** Cores dos gráficos lidas dos tokens CSS — trocam junto com o tema. */
export function usePaleta(): Paleta {
  const { tema } = useTheme()
  // `tema` é o gatilho para reler as variáveis CSS
  return useMemo(() => (tema ? ler() : ler()), [tema])
}

export const FONTE_MONO = "'Fira Code', ui-monospace, monospace"
export const FONTE_UI = "'Fira Sans', system-ui, sans-serif"

export function estiloTooltip(p: Paleta) {
  return {
    backgroundColor: p.surface3,
    borderColor: p.lineStrong,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: { color: p.text, fontFamily: FONTE_UI, fontSize: 12 },
    extraCssText: 'border-radius:2px;box-shadow:0 6px 20px rgba(0,0,0,.35);',
  }
}

export function estiloEixo(p: Paleta) {
  return {
    axisLine: { lineStyle: { color: p.lineStrong } },
    axisTick: { show: false },
    axisLabel: { color: p.text3, fontFamily: FONTE_MONO, fontSize: 11 },
    splitLine: { lineStyle: { color: p.line, type: 'solid' as const } },
  }
}
