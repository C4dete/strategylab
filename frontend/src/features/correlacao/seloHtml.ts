import { FONTE_MONO, type Paleta } from '../results/charts/palette'
import { identidade } from './identidade'

/** Cor (hex) da estratégia `i` nos gráficos, lida dos tokens do tema atual. */
export const corDe = (p: Paleta, i: number): string => p.estrategia[identidade(i).corIndice] ?? p.text2

/** Texto do usuário (nome da estratégia) dentro do HTML dos tooltips do ECharts. */
export const escapa = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string)

/** O mesmo selo (letra + cor) do restante da interface, em HTML, para os tooltips dos gráficos. */
export function seloHtml(p: Paleta, i: number): string {
  const id = identidade(i)
  const cor = corDe(p, i)
  return (
    `<span style="display:inline-grid;place-items:center;width:14px;height:14px;box-sizing:border-box;` +
    `border:1.5px ${id.repetida ? 'dashed' : 'solid'} ${cor};border-radius:2px;color:${cor};background:${cor}2a;` +
    `font:700 9px/1 ${FONTE_MONO};margin-right:6px;vertical-align:middle">${id.letra}</span>`
  )
}
