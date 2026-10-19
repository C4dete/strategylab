import type { Book, ContagemLosses, EscadaAcao, ModoEntrada, Params } from '../api/types'

export const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

export function hhmmParaMin(v: string): number {
  const [h, m] = v.split(':')
  return Number(h) * 60 + Number(m)
}

const CHAVES: (keyof Params)[] = [
  'janela_inicio', 'janela_fim', 'ultima_entrada', 'candles_gatilho', 'candles_media', 'bracket_fracao',
  'modo_entrada', 'reversoes', 'rev_stop_x_media', 'rev_alvo_x_media', 'book', 'penetracao_ticks', 'parar_apos_losses', 'contagem_losses', 'operacoes_por_dia',
  'stop_x_media', 'alvo_x_media', 'mm_periodo', 'bb_periodo', 'bb_desvio', 'filtro_afast_mm_ativo',
  'filtro_afast_mm_x_media', 'rastrear_mm', 'sair_ao_tocar_mm',
  'parar_dia_perda_x_media', 'tempo_max_min', 'filtro_gap_ativo', 'filtro_gap_max_x_media', 'filtro_vol_ontem_ativo',
  'filtro_vol_ontem_max', 'filtro_bb_ativo', 'filtro_bb_largura_min_pct', 'filtro_bb_largura_max_pct', 'filtro_inclinacao_ativo',
  'filtro_inclinacao_barras', 'filtro_inclinacao_max_x_media', 'filtro_candle_discrepante_ativo', 'filtro_candle_discrepante_x', 'trailing_inicio_r',
  'escada_contratos', 'escada_ganho_acao', 'escada_ganho_qtd', 'escada_perda_acao', 'escada_perda_qtd', 'escada_min', 'escada_max',
]

/** Campos que esta interface conhece e que o servidor não devolve em `padrao` (servidor iniciado antes da atualização). */
export function camposAusentesNoServidor(padrao: object): string[] {
  return CHAVES.filter((k) => !(k in padrao))
}

/** Largura mínima das bandas precisa ser menor que a máxima (mesma regra do servidor); 0 = sem mínimo. */
export function validarRegime(p: Params): Partial<Record<keyof Params, string>> {
  const e: Partial<Record<keyof Params, string>> = {}
  if (p.filtro_bb_ativo && p.filtro_bb_largura_min_pct > 0 && p.filtro_bb_largura_min_pct >= p.filtro_bb_largura_max_pct) {
    e.filtro_bb_largura_min_pct = 'O mínimo precisa ser menor que o máximo.'
  }
  if (p.escada_contratos > 0) {
    if (p.escada_min > p.escada_max) e.escada_min = 'O mínimo precisa ser menor ou igual ao máximo.'
    else if (p.escada_contratos < p.escada_min || p.escada_contratos > p.escada_max) e.escada_contratos = 'Precisa estar entre o mínimo e o máximo.'
  }
  return e
}

export function clonar(p: Params): Params {
  return { ...p }
}

export function paramsIguais(a: Params | null | undefined, b: Params | null | undefined): boolean {
  if (!a || !b) return a === b
  return CHAVES.every((k) => a[k] === b[k])
}

export type Erros = Partial<Record<keyof Params, string>>

/** Mesmas regras de coerência do servidor (`Params._coerencia`). As faixas numéricas o próprio campo já limita. */
export function validar(p: Params): Erros {
  const e: Erros = { ...validarRegime(p) }
  if (!HHMM.test(p.janela_inicio)) e.janela_inicio = 'Informe um horário válido.'
  if (!HHMM.test(p.janela_fim)) e.janela_fim = 'Informe um horário válido.'
  if (p.ultima_entrada !== null && !HHMM.test(p.ultima_entrada)) e.ultima_entrada = 'Informe um horário válido.'
  if (e.janela_inicio || e.janela_fim) return e

  const ini = hhmmParaMin(p.janela_inicio)
  const fim = hhmmParaMin(p.janela_fim)
  if (ini >= fim) e.janela_fim = 'A zeragem precisa ser depois do início.'
  if (p.ultima_entrada !== null && !e.ultima_entrada) {
    const ult = hhmmParaMin(p.ultima_entrada)
    if (ult <= ini) e.ultima_entrada = 'Precisa ser depois do início da janela.'
    else if (ult > fim) e.ultima_entrada = 'Não pode ser depois da zeragem.'
  }
  return e
}

export const BOOK_OPCOES: { valor: Book; rotulo: string; descricao: string }[] = [
  {
    valor: 'cont',
    rotulo: 'Só a de continuação',
    descricao: 'Uma ordem, além do gatilho. Só executa depois de o preço realmente cruzar a zona.',
  },
  {
    valor: 'ambas',
    rotulo: 'As duas pontas',
    descricao: 'Ordens dos dois lados do gatilho; a primeira tocada executa e cancela a outra.',
  },
  {
    valor: 'recuo',
    rotulo: 'Só a de recuo',
    descricao: 'Uma ordem, dentro da zona: espera o preço voltar depois de cruzar o gatilho.',
  },
  { valor: 'acima', rotulo: 'Só a de cima', descricao: 'Uma ordem, sempre acima do gatilho.' },
  { valor: 'abaixo', rotulo: 'Só a de baixo', descricao: 'Uma ordem, sempre abaixo do gatilho.' },
]

export const MODO_ENTRADA_OPCOES: { valor: ModoEntrada; rotulo: string }[] = [
  { valor: 'padrao', rotulo: 'Padrão' },
  { valor: 'proximo_candle', rotulo: 'Próximo candle' },
]

export const ESCADA_ACAO_OPCOES: { valor: EscadaAcao; rotulo: string }[] = [
  { valor: 'manter', rotulo: 'Manter' },
  { valor: 'somar', rotulo: 'Somar' },
  { valor: 'subtrair', rotulo: 'Subtrair' },
]

export const CONTAGEM_OPCOES: { valor: ContagemLosses; rotulo: string }[] = [
  { valor: 'dia', rotulo: 'Todos do pregão' },
  { valor: 'seguidos', rotulo: 'Só seguidos' },
]
