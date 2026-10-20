import type { Estrategia, Params } from '../../api/types'

/** Máximo de estratégias no conjunto (a principal + 11). Espelha `LIMITE_COMPONENTES` do servidor. */
export const MAX_ESTRATEGIAS = 12
/** Cores distintas (`--e1`…`--e6`); acima disso as cores repetem, e a letra continua única. */
export const NUM_CORES = 6
const LETRAS = 'ABCDEFGHIJKL'

export interface Identidade {
  indice: number
  /** A principal é sempre "A". */
  letra: string
  /** Referência CSS da cor (tokens do tema). */
  cor: string
  /** 0…5: posição na paleta (para os gráficos lerem `paleta.estrategia[corIndice]`). */
  corIndice: number
  /** A cor já foi usada por outra estratégia do conjunto: a interface reforça com padrão/contorno tracejado. */
  repetida: boolean
}

/** Identidade (letra + cor) da estratégia de índice `i` no conjunto; 0 = principal. A cor NUNCA é o único sinal. */
export function identidade(i: number): Identidade {
  const indice = Math.max(0, Math.floor(i))
  const corIndice = indice % NUM_CORES
  return { indice, letra: LETRAS[indice] ?? String(indice + 1), cor: `var(--e${corIndice + 1})`, corIndice, repetida: indice >= NUM_CORES }
}

/**
 * Ids marcados em "Correlacionar" que ainda valem: existem, são válidos, não são a própria principal e não se repetem.
 * A ordem em que o usuário marcou é mantida (ela decide letra e cor).
 */
export function saneiaCorrelacionadas(ids: readonly string[], estrategias: readonly Estrategia[], principalId: string | null): string[] {
  const validas = new Set(estrategias.filter((e) => e.valida).map((e) => e.id))
  const saida: string[] = []
  for (const id of ids) {
    if (id !== principalId && validas.has(id) && !saida.includes(id)) saida.push(id)
  }
  return saida.slice(0, MAX_ESTRATEGIAS - 1)
}

/** Marca/desmarca `id` na lista, respeitando o limite e a ordem de marcação. */
export function alternaCorrelacionada(ids: readonly string[], id: string): string[] {
  if (ids.includes(id)) return ids.filter((x) => x !== id)
  return ids.length >= MAX_ESTRATEGIAS - 1 ? [...ids] : [...ids, id]
}

/**
 * Identifica uma execução do conjunto: parâmetros da principal (rascunho) + os parâmetros SALVOS de cada correlacionada.
 * Se mudar (um parâmetro, ou uma correlacionada salva depois), o resultado na tela está desatualizado.
 */
export function assinaturaConjunto(principal: Params, correlacionadas: readonly { id: string; params: Params }[]): string {
  return JSON.stringify([principal, ...correlacionadas.map((c) => [c.id, c.params])])
}
