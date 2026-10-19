import { describe, expect, it } from 'vitest'
import { brl, dataBR, dataCurta, dataHoraBR, diaDaSemana, mesCurto, numero, pct, plural, pts, segundos } from './format'

describe('format pt-BR', () => {
  it('formata reais com milhar em ponto e decimal em vírgula', () => {
    expect(brl(7391)).toBe('R$ 7.391,00')
    expect(brl(1234567.891)).toBe('R$ 1.234.567,89')
  })

  it('usa o sinal de menos tipográfico e o "+" opcional', () => {
    expect(brl(-4730)).toBe('−R$ 4.730,00')
    expect(brl(544, { mais: true })).toBe('+R$ 544,00')
    expect(brl(0, { mais: true })).toBe('R$ 0,00')
    expect(brl(-191, { casas: 0 })).toBe('−R$ 191')
  })

  it('formata pontos e percentuais', () => {
    expect(pts(36955)).toBe('36.955')
    expect(pts(-23650)).toBe('−23.650')
    expect(pts(5, { mais: true })).toBe('+5')
    expect(pct(27.3333)).toBe('27,3%')
    expect(numero(0.05, 2)).toBe('0,05')
  })

  it('formata datas ISO sem deslocar o dia', () => {
    expect(dataBR('2024-01-01')).toBe('01/01/2024')
    expect(dataBR(null)).toBe('—')
    expect(dataCurta('2022-11-18')).toBe('18/11/22')
    expect(mesCurto('2021-09')).toBe('set/21')
    expect(diaDaSemana('2024-01-01')).toBe('segunda')
    expect(dataHoraBR('2026-10-08T21:14:05-03:00')).toBe('08/10/2026 21:14')
  })

  it('pluraliza e formata tempo', () => {
    expect(plural(1, 'pregão', 'pregões')).toBe('1 pregão')
    expect(plural(1054, 'pregão', 'pregões')).toBe('1.054 pregões')
    expect(segundos(5120)).toBe('5,1 s')
    expect(segundos(42000)).toBe('42 s')
  })
})
