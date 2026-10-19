/** Formatação pt-BR. Sem `Date` para datas ISO: evita o deslocamento de fuso (2024-01-01 virar 31/12). */

const NBSP = ' '
const MENOS = '−'

const nf = (casas: number) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })

const FORMATOS = new Map<number, Intl.NumberFormat>()
function formato(casas: number): Intl.NumberFormat {
  let f = FORMATOS.get(casas)
  if (!f) {
    f = nf(casas)
    FORMATOS.set(casas, f)
  }
  return f
}

export function numero(v: number, casas = 0): string {
  return formato(casas).format(v)
}

/** "R$ 1.234,00" — negativo com sinal de menos tipográfico: "−R$ 1.234,00". `mais` mostra "+" nos ganhos. */
export function brl(v: number, opts: { casas?: number; mais?: boolean } = {}): string {
  const { casas = 2, mais = false } = opts
  const abs = formato(casas).format(Math.abs(v))
  if (v < 0) return `${MENOS}R$${NBSP}${abs}`
  return `${mais && v > 0 ? '+' : ''}R$${NBSP}${abs}`
}

export function pts(v: number, opts: { mais?: boolean } = {}): string {
  const abs = formato(0).format(Math.abs(v))
  if (v < 0) return `${MENOS}${abs}`
  return `${opts.mais && v > 0 ? '+' : ''}${abs}`
}

export function pct(v: number, casas = 1): string {
  return `${formato(casas).format(v)}%`
}

/** "2024-03-05" -> "05/03/2024" */
export function dataBR(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a}`
}

/** "2024-03-05" -> "05/03/24" */
export function dataCurta(iso: string): string {
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${(a ?? '').slice(2)}`
}

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** "2024-03" -> "mar/24" */
export function mesCurto(ym: string): string {
  const [a, m] = ym.split('-')
  return `${MESES[Number(m) - 1] ?? m}/${(a ?? '').slice(2)}`
}

/** "2024-03" -> "março de 2024" */
const MESES_LONGOS = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]
export function mesLongo(ym: string): string {
  const [a, m] = ym.split('-')
  return `${MESES_LONGOS[Number(m) - 1] ?? m} de ${a}`
}

const DIAS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
export function diaDaSemana(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  return DIAS[new Date(Date.UTC(a ?? 0, (m ?? 1) - 1, d ?? 1)).getUTCDay()] ?? ''
}

export function plural(n: number, um: string, varios: string): string {
  return `${numero(n)} ${n === 1 ? um : varios}`
}

export function segundos(ms: number): string {
  return `${formato(ms < 10_000 ? 1 : 0).format(ms / 1000)} s`
}

/** "2026-10-08T21:14:05-03:00" -> "08/10/2026 21:14" */
export function dataHoraBR(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso)
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : iso
}
