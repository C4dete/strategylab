import { describe, expect, it } from 'vitest'
import type { Params } from '../api/types'
import { camposAusentesNoServidor, clonar, hhmmParaMin, paramsIguais, validar } from './params'

const base: Params = {
  janela_inicio: '09:00', janela_fim: '17:30', ultima_entrada: '16:00', candles_gatilho: 5, candles_media: 5,
  bracket_fracao: 0.05, modo_entrada: 'padrao', reversoes: 0, rev_stop_x_media: 0, rev_alvo_x_media: 0, book: 'cont', penetracao_ticks: 1, parar_apos_losses: 0, contagem_losses: 'dia',
  operacoes_por_dia: 1, stop_x_media: 1, alvo_x_media: 3,
  mm_periodo: 15, bb_periodo: 15, bb_desvio: 2, filtro_afast_mm_ativo: false, filtro_afast_mm_x_media: 0.7,
  rastrear_mm: false, sair_ao_tocar_mm: false,
  parar_dia_perda_x_media: 0, tempo_max_min: 0, filtro_gap_ativo: false, filtro_gap_max_x_media: 0.5, filtro_vol_ontem_ativo: false,
  filtro_vol_ontem_max: 1.5, filtro_bb_ativo: false, filtro_bb_largura_min_pct: 0, filtro_bb_largura_max_pct: 1,
  filtro_inclinacao_ativo: false, filtro_inclinacao_barras: 5, filtro_inclinacao_max_x_media: 0.5,
  trailing_inicio_r: 0, escada_contratos: 0, escada_ganho_acao: 'manter', escada_ganho_qtd: 1, escada_perda_acao: 'manter', escada_perda_qtd: 1, escada_min: 1, escada_max: 5, filtro_candle_discrepante_ativo: false, filtro_candle_discrepante_x: 2,
}

describe('params', () => {
  it('compara todos os campos', () => {
    expect(paramsIguais(base, clonar(base))).toBe(true)
    expect(paramsIguais(base, { ...base, book: 'ambas' })).toBe(false)
    expect(paramsIguais(base, { ...base, ultima_entrada: null })).toBe(false)
    expect(paramsIguais(base, { ...base, filtro_afast_mm_ativo: true })).toBe(false)
    expect(paramsIguais(base, { ...base, bb_desvio: 2.5 })).toBe(false)
    expect(paramsIguais(base, { ...base, mm_periodo: 20 })).toBe(false)
    expect(paramsIguais(base, { ...base, modo_entrada: 'proximo_candle' })).toBe(false)
    expect(paramsIguais(base, { ...base, sair_ao_tocar_mm: true })).toBe(false)
    expect(paramsIguais(base, { ...base, rastrear_mm: true })).toBe(false)
    expect(paramsIguais(base, { ...base, reversoes: 2 })).toBe(false)
    expect(paramsIguais(base, { ...base, rev_stop_x_media: 0.5 })).toBe(false)
    expect(paramsIguais(base, { ...base, rev_alvo_x_media: 1 })).toBe(false)
    expect(paramsIguais(base, { ...base, parar_dia_perda_x_media: 1 })).toBe(false)
    expect(paramsIguais(base, { ...base, tempo_max_min: 30 })).toBe(false)
    expect(paramsIguais(base, { ...base, filtro_gap_ativo: true })).toBe(false)
    expect(paramsIguais(base, { ...base, filtro_bb_largura_max_pct: 2 })).toBe(false)
    expect(paramsIguais(base, { ...base, filtro_inclinacao_barras: 8 })).toBe(false)
    expect(paramsIguais(null, null)).toBe(true)
    expect(paramsIguais(base, null)).toBe(false)
  })

  it('detecta servidor desatualizado (campo que o servidor não devolve)', () => {
    expect(camposAusentesNoServidor({ ...base })).toEqual([])
    const { rastrear_mm: _ignorado, ...semRastrear } = base
    expect(camposAusentesNoServidor(semRastrear)).toEqual(['rastrear_mm'])
  })

  it('valida a largura das bandas (mínimo menor que o máximo)', () => {
    expect(validar({ ...base, filtro_bb_ativo: true, filtro_bb_largura_min_pct: 1, filtro_bb_largura_max_pct: 0.8 }).filtro_bb_largura_min_pct).toMatch(/menor/)
    expect(validar({ ...base, filtro_bb_ativo: true, filtro_bb_largura_min_pct: 0, filtro_bb_largura_max_pct: 0.8 })).toEqual({})
    expect(validar({ ...base, filtro_bb_ativo: false, filtro_bb_largura_min_pct: 1, filtro_bb_largura_max_pct: 0.8 })).toEqual({})
  })

  it('aceita o padrão e converte horários', () => {
    expect(validar(base)).toEqual({})
    expect(hhmmParaMin('16:30')).toBe(990)
  })

  it('aplica as mesmas regras de coerência do servidor', () => {
    expect(validar({ ...base, janela_inicio: '17:30', janela_fim: '09:00' }).janela_fim).toMatch(/depois do início/)
    expect(validar({ ...base, ultima_entrada: '08:00' }).ultima_entrada).toMatch(/depois do início/)
    expect(validar({ ...base, ultima_entrada: '18:00' }).ultima_entrada).toMatch(/depois da zeragem/)
    expect(validar({ ...base, ultima_entrada: null })).toEqual({})
    expect(validar({ ...base, janela_inicio: '' }).janela_inicio).toBeDefined()
  })
})
