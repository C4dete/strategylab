import { describe, expect, it } from 'vitest'
import type { Estrategia, Params } from '../../api/types'
import { alternaCorrelacionada, assinaturaConjunto, identidade, MAX_ESTRATEGIAS, NUM_CORES, saneiaCorrelacionadas } from './identidade'

const est = (id: string, valida = true): Estrategia => ({
  id, nome: id, atualizada_em: '', valida, erro: valida ? null : 'arquivo inválido', params: valida ? ({} as Params) : null,
})

describe('identidade', () => {
  it('a principal é A e usa a primeira cor', () => {
    expect(identidade(0)).toMatchObject({ letra: 'A', cor: 'var(--e1)', corIndice: 0, repetida: false })
  })

  it('as letras são únicas em todo o conjunto', () => {
    const letras = Array.from({ length: MAX_ESTRATEGIAS }, (_, i) => identidade(i).letra)
    expect(new Set(letras).size).toBe(MAX_ESTRATEGIAS)
  })

  it('as 6 primeiras cores são distintas; depois repetem e ficam marcadas como repetidas', () => {
    const cores = Array.from({ length: NUM_CORES }, (_, i) => identidade(i).cor)
    expect(new Set(cores).size).toBe(NUM_CORES)
    expect(identidade(NUM_CORES)).toMatchObject({ cor: identidade(0).cor, repetida: true })
    expect(identidade(NUM_CORES - 1).repetida).toBe(false)
  })

  it('índice inválido não quebra', () => {
    expect(identidade(-3).letra).toBe('A')
    expect(identidade(2.9).letra).toBe('C')
  })
})

describe('saneiaCorrelacionadas', () => {
  const lista = [est('a'), est('b'), est('c'), est('ruim', false)]

  it('tira a própria principal, inexistentes, inválidas e repetidas, mantendo a ordem marcada', () => {
    expect(saneiaCorrelacionadas(['c', 'a', 'x', 'ruim', 'b', 'c'], lista, 'a')).toEqual(['c', 'b'])
  })

  it('lista vazia continua vazia', () => {
    expect(saneiaCorrelacionadas([], lista, 'a')).toEqual([])
  })

  it('respeita o limite do conjunto (a principal + 11)', () => {
    const muitas = Array.from({ length: 20 }, (_, i) => est(`e${i}`))
    expect(saneiaCorrelacionadas(muitas.map((e) => e.id), muitas, null)).toHaveLength(MAX_ESTRATEGIAS - 1)
  })
})

describe('alternaCorrelacionada', () => {
  it('marca no fim (a ordem de marcação decide a letra) e desmarca preservando a ordem', () => {
    expect(alternaCorrelacionada(['b'], 'c')).toEqual(['b', 'c'])
    expect(alternaCorrelacionada(['b', 'c', 'd'], 'c')).toEqual(['b', 'd'])
  })

  it('no limite não aceita mais uma', () => {
    const cheia = Array.from({ length: MAX_ESTRATEGIAS - 1 }, (_, i) => `e${i}`)
    expect(alternaCorrelacionada(cheia, 'novo')).toEqual(cheia)
    expect(alternaCorrelacionada(cheia, 'e0')).toHaveLength(MAX_ESTRATEGIAS - 2)
  })
})

describe('assinaturaConjunto', () => {
  const p1 = { stop_x_media: 1 } as Params
  const p2 = { stop_x_media: 2 } as Params

  it('muda quando muda o parâmetro da principal ou o de uma correlacionada, e quando a lista muda', () => {
    const base = assinaturaConjunto(p1, [{ id: 'b', params: p1 }])
    expect(assinaturaConjunto(p1, [{ id: 'b', params: p1 }])).toBe(base)
    expect(assinaturaConjunto(p2, [{ id: 'b', params: p1 }])).not.toBe(base)
    expect(assinaturaConjunto(p1, [{ id: 'b', params: p2 }])).not.toBe(base)
    expect(assinaturaConjunto(p1, [])).not.toBe(base)
  })

  it('a ordem das correlacionadas conta (muda letra e cor)', () => {
    const x = { id: 'b', params: p1 }
    const y = { id: 'c', params: p1 }
    expect(assinaturaConjunto(p1, [x, y])).not.toBe(assinaturaConjunto(p1, [y, x]))
  })
})
