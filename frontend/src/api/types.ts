export type Book = 'ambas' | 'cont' | 'recuo' | 'acima' | 'abaixo'
export type ContagemLosses = 'dia' | 'seguidos'
/** `proximo_candle`: a entrada só acontece na abertura da barra seguinte (a mercado). */
export type ModoEntrada = 'padrao' | 'proximo_candle'
export type EscadaAcao = 'manter' | 'somar' | 'subtrair'
/** O que encerrou a operação. */
export type SaidaPor = 'stop' | 'trailing' | 'alvo' | 'mm' | 'zeragem' | 'fim_dados' | 'tempo'

/** Campos editáveis de uma estratégia (espelha `strategylab/engine/params.py`). */
export interface Params {
  janela_inicio: string
  janela_fim: string
  ultima_entrada: string | null
  candles_gatilho: number
  candles_media: number
  bracket_fracao: number
  modo_entrada: ModoEntrada
  reversoes: number
  rev_stop_x_media: number
  rev_alvo_x_media: number
  book: Book
  penetracao_ticks: number
  parar_apos_losses: number
  contagem_losses: ContagemLosses
  operacoes_por_dia: number
  stop_x_media: number
  alvo_x_media: number
  // 04 Indicadores (EMA)
  mm_periodo: number
  bb_periodo: number
  bb_desvio: number
  // 05 Filtros
  filtro_afast_mm_ativo: boolean
  filtro_afast_mm_x_media: number
  rastrear_mm: boolean
  sair_ao_tocar_mm: boolean
  // Controle de cauda e filtros de regime (desligados por padrão)
  parar_dia_perda_x_media: number
  tempo_max_min: number
  filtro_gap_ativo: boolean
  filtro_gap_max_x_media: number
  filtro_vol_ontem_ativo: boolean
  filtro_vol_ontem_max: number
  filtro_bb_ativo: boolean
  filtro_bb_largura_min_pct: number
  filtro_bb_largura_max_pct: number
  filtro_inclinacao_ativo: boolean
  filtro_inclinacao_barras: number
  filtro_inclinacao_max_x_media: number
  trailing_inicio_r: number
  escada_contratos: number
  escada_ganho_acao: EscadaAcao
  escada_ganho_qtd: number
  escada_perda_acao: EscadaAcao
  escada_perda_qtd: number
  escada_min: number
  escada_max: number
  filtro_candle_discrepante_ativo: boolean
  filtro_candle_discrepante_x: number
}

export interface Faixa {
  min: number
  max: number
}

export interface Meta {
  execucao: {
    ativo: string
    descricao_ativo: string
    perfil: string
    valor_ponto: number
    contratos: number
    timeframe_min: number
    leitura_min: number
    slippage_pts: number
    spread_pts: number
    tick_pts: number
    entrada: string
  }
  faixas: Record<string, Faixa>
  padrao: Params
  /** Ausente em servidor antigo. */
  capacidades?: { correlacao: boolean }
}

export interface Estrategia {
  id: string
  nome: string
  atualizada_em: string
  valida: boolean
  erro: string | null
  params: Params | null
}

export interface ListaEstrategias {
  estrategias: Estrategia[]
  ultima: string | null
  /** principal -> ids marcados em "Correlacionar" (lembrado entre sessões). */
  correlacionar?: Record<string, string[]>
}

export interface BD {
  estado: 'carregando' | 'pronto' | 'erro'
  erro: string | null
  id: string | null
  nome: string | null
  padrao: boolean | null
  linhas: number | null
  pregoes: number | null
  inicio: string | null
  fim: string | null
  timeframe_min: number | null
  avisos: string[]
}

export interface DiaValor {
  data: string
  rs: number
}

export interface Sequencia {
  dias: number
  total: number
  inicio: string
  fim: string
}

export interface Resumo {
  total_rs: number
  total_pts: number
  pregoes_operados: number
  operacoes: number
  ganhos: number
  perdas: number
  zeradas: number
  win_rate: number
  drawdown: { rs: number; pts: number; pico: string | null; fundo: string | null; pregoes: number }
  melhor_dia: DiaValor | null
  pior_dia: DiaValor | null
  seq_ganho: Sequencia | null
  seq_perda: Sequencia | null
}

export interface Diario {
  data: string
  rs: number
  pts: number
  acumulado: number
  operacoes: number
  ganhos: number
  perdas: number
  /** Só no conjunto: resultado do dia de cada estratégia, na ordem dos componentes (A, B, C…). */
  rs_por?: number[]
}

export interface Mensal {
  mes: string
  rs: number
  pts: number
  dias: number
  dias_positivos: number
  /** false = mês que o BD cobre e em que a estratégia não operou (vem zerado). Ausente em servidor antigo = operado. */
  operado?: boolean
  /** Só no conjunto: resultado do mês de cada estratégia, na ordem dos componentes. */
  rs_por?: number[]
}

export type Desfecho = 'gain' | 'loss' | 'time_close' | 'eod'

export interface Operacao {
  data: string
  ciclo: number
  lado: 'buy' | 'sell'
  entrada: string
  entrada_barra: string
  preco_entrada: number
  saida: string
  saida_barra: string
  preco_saida: number
  contratos: number
  pts: number
  rs: number
  desfecho: Desfecho
  saida_por: SaidaPor
  /** 0 = entrada original do ciclo; n = n-ésima reversão (mesmo `ciclo`). */
  reversao: number
  /** O que o filtro "Afastamento da MM" viu (null com o filtro desligado). */
  ref: RefFiltro | null
  /** Só no conjunto: índice da estratégia (0 = principal). */
  estrategia?: number
}

export interface RefFiltro {
  /** Início da barra fechada anterior à do gatilho (o candle de referência). */
  barra: string
  /** EMA no fechamento dessa barra. */
  mm: number | null
  /** Pontos entre o candle e a MM (0 = toca/cruza). */
  afast_pts: number | null
  /** Em múltiplos da media_operacao vigente. */
  afast_x: number | null
}

/** Uma estratégia dentro do conjunto (a principal é a de índice 0). */
export interface ComponenteResumo {
  indice: number
  nome: string
  total_rs: number
  total_pts: number
  operacoes: number
  pregoes_operados: number
  win_rate: number
  drawdown: { rs: number; pts: number }
  /** Correlação (Pearson) do R$ diário com a principal; null na principal ou quando indefinida. */
  correlacao_principal: number | null
}

export interface Diversificacao {
  dd_conjunto: number
  soma_dd_isolados: number
}

export interface Resultado {
  resumo: Resumo
  diario: Diario[]
  mensal: Mensal[]
  operacoes: Operacao[]
  /** Só quando há estratégias correlacionadas (`/api/portfolio`). */
  estrategias?: ComponenteResumo[]
  diversificacao?: Diversificacao
  tempo_ms: number
  em_cache: boolean
  bd: BD
  params: Params
}

export interface BarraDia {
  t: string
  o: number
  h: number
  l: number
  c: number
  /** Indicadores NO FECHAMENTO desta barra (null enquanto a EMA não tem histórico). Só vêm quando pedidos. */
  mm?: number | null
  bbm?: number | null
  bbs?: number | null
  bbi?: number | null
}

export interface DiaBarras {
  data: string
  barras: BarraDia[]
}
