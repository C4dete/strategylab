import type { BD, DiaBarras, Estrategia, ListaEstrategias, Meta, Params, Resultado } from './types'

/** Erro com a mensagem em português que a API devolveu (`detail`). */
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function mensagemDe(res: Response): Promise<string> {
  try {
    const corpo = (await res.json()) as { detail?: unknown }
    if (typeof corpo.detail === 'string') return corpo.detail
    if (Array.isArray(corpo.detail)) return corpo.detail.map((d: { msg?: string }) => d.msg).join('; ')
  } catch {
    /* corpo vazio ou não-JSON */
  }
  if (res.status >= 500) return 'O servidor do StrategyLab encontrou um erro. Veja o terminal onde ele está rodando.'
  return `Falha na requisição (${res.status}).`
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError('Não foi possível falar com o servidor do StrategyLab. Ele está rodando?', 0)
  }
  if (!res.ok) throw new ApiError(await mensagemDe(res), res.status)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const json = (metodo: string, corpo: unknown): RequestInit => ({
  method: metodo,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(corpo),
})

export const api = {
  meta: () => req<Meta>('/api/meta'),
  dataset: () => req<BD>('/api/dataset'),
  enviarDataset: (arquivo: File) => {
    const form = new FormData()
    form.append('arquivo', arquivo)
    return req<BD>('/api/dataset', { method: 'POST', body: form })
  },
  voltarPadrao: () => req<BD>('/api/dataset/reset', { method: 'POST' }),
  estrategias: () => req<ListaEstrategias>('/api/strategies'),
  criar: (nome: string, params: Params | null) => req<Estrategia>('/api/strategies', json('POST', { nome, params })),
  salvar: (id: string, params: Params) => req<Estrategia>(`/api/strategies/${id}`, json('PUT', { params })),
  renomear: (id: string, nome: string) => req<Estrategia>(`/api/strategies/${id}`, json('PATCH', { nome })),
  excluir: (id: string) => req<void>(`/api/strategies/${id}`, { method: 'DELETE' }),
  definirUltima: (id: string) => req<void>('/api/estado/ultima', json('PUT', { id })),
  backtest: (params: Params) => req<Resultado>('/api/backtest', json('POST', { params })),
  /** Conjunto: o primeiro componente é a principal. */
  portfolio: (componentes: { nome: string; params: Params }[]) => req<Resultado>('/api/portfolio', json('POST', { componentes })),
  definirCorrelacionar: (id: string, ids: string[]) => req<{ ids: string[] }>('/api/estado/correlacionar', json('PUT', { id, ids })),
  dia: (data: string, ind?: { mm: number; bb: number; k: number }) =>
    req<DiaBarras>(`/api/dia/${data}${ind ? `?mm=${ind.mm}&bb=${ind.bb}&k=${ind.k}` : ''}`),
}
