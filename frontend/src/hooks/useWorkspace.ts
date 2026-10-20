import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { BD, Estrategia, ListaEstrategias, Params, Resultado } from '../api/types'
import { useToast } from '../components/ui/Toast'
import { alternaCorrelacionada, saneiaCorrelacionadas } from '../features/correlacao/identidade'
import { clonar, paramsIguais, validar, type Erros } from '../lib/params'

interface EstadoExecucao {
  executando: boolean
  resultado: Resultado | null
  erro: string | null
  /** Quais correlacionadas (e com quais parâmetros salvos) entraram nesta execução; '' = sem conjunto. */
  correl: string
  /** Quantas estratégias a execução em andamento junta (para a mensagem "Executando o conjunto…"). */
  tamanho: number
}

const SEM_EXECUCAO: EstadoExecucao = { executando: false, resultado: null, erro: null, correl: '', tamanho: 1 }

function mensagem(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

/** Identifica as correlacionadas de uma execução pelos ids e pelos parâmetros SALVOS (se um deles mudar, o resultado envelheceu). */
const assinaturaCorrel = (comps: readonly Estrategia[]) =>
  comps.length ? JSON.stringify(comps.map((e) => [e.id, e.params])) : ''

/**
 * Estado do espaço de trabalho: estratégias (salvas no servidor), rascunho dos parâmetros em edição,
 * BD ativo, as estratégias marcadas em "Correlacionar" e o último resultado (da principal sozinha ou do conjunto).
 * Concentra as regras de "alterações não salvas" e de execução.
 */
export function useWorkspace() {
  const qc = useQueryClient()
  const { toast } = useToast()

  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  const lista = useQuery({ queryKey: ['strategies'], queryFn: api.estrategias })
  const bd = useQuery({
    queryKey: ['dataset'],
    queryFn: api.dataset,
    refetchInterval: (q) => (q.state.data?.estado === 'carregando' ? 800 : false),
  })

  const [selecionadaId, setSelecionadaId] = useState<string | null>(null)
  const [rascunho, setRascunho] = useState<Params | null>(null)
  const [pendenteId, setPendenteId] = useState<string | null>(null)
  const [correlacionadas, setCorrelacionadas] = useState<string[]>([])
  const [exec, setExec] = useState<EstadoExecucao>(SEM_EXECUCAO)
  const [bdConferido, setBdConferido] = useState(false)

  const seq = useRef(0)
  const iniciou = useRef(false)
  const rodouAoAbrir = useRef(false)

  const estrategias = useMemo(() => lista.data?.estrategias ?? [], [lista.data])
  const mapaCorrel = lista.data?.correlacionar
  const selecionada: Estrategia | null = estrategias.find((e) => e.id === selecionadaId) ?? null
  const salvos = selecionada?.params ?? null
  const alterado = rascunho !== null && salvos !== null && !paramsIguais(rascunho, salvos)
  const erros: Erros = useMemo(() => (rascunho ? validar(rascunho) : {}), [rascunho])
  const valido = Object.keys(erros).length === 0

  // as execuções são disparadas de callbacks antigos: elas leem o que há de mais novo por aqui
  const estrategiasRef = useRef<Estrategia[]>([])
  const mapaRef = useRef<Record<string, string[]>>({})
  const correlRef = useRef<string[]>([])
  useEffect(() => {
    estrategiasRef.current = estrategias
    mapaRef.current = mapaCorrel ?? {}
    correlRef.current = correlacionadas
  })

  const comps = useMemo(
    () => correlacionadas.flatMap((id) => estrategias.find((e) => e.id === id && e.valida) ?? []),
    [correlacionadas, estrategias],
  )
  const desatualizado =
    exec.resultado !== null && rascunho !== null && (!paramsIguais(exec.resultado.params, rascunho) || exec.correl !== assinaturaCorrel(comps))

  // ------------------------------------------------------------------ execução
  /** Roda a principal sozinha ou, com correlacionadas, o conjunto (a principal usa o rascunho; as outras, o salvo). */
  const executar = useCallback(async (params: Params, nome: string, ids: string[]) => {
    const id = ++seq.current
    const outras = ids.flatMap((i) => estrategiasRef.current.find((e) => e.id === i && e.params) ?? [])
    setExec((s) => ({ ...s, executando: true, erro: null, tamanho: 1 + outras.length }))
    try {
      const r = outras.length
        ? await api.portfolio([{ nome, params }, ...outras.map((e) => ({ nome: e.nome, params: e.params as Params }))])
        : await api.backtest(params)
      if (id === seq.current) {
        setExec({ executando: false, resultado: r, erro: null, correl: assinaturaCorrel(outras), tamanho: 1 + outras.length })
        qc.setQueryData(['dataset'], r.bd)       // mantém o chip do BD em dia (outra aba pode ter trocado)
      }
    } catch (e) {
      if (id === seq.current) setExec((s) => ({ ...s, executando: false, erro: mensagem(e) }))
    }
  }, [qc])

  const rodar = useCallback(() => {
    if (rascunho && valido && selecionada) void executar(rascunho, selecionada.nome, correlacionadas)
  }, [rascunho, valido, selecionada, correlacionadas, executar])

  // ------------------------------------------------------------------ seleção
  const aplicarSelecao = useCallback(
    (e: Estrategia) => {
      if (!e.params) {
        toast('erro', `“${e.nome}” não pôde ser lida: ${e.erro ?? 'arquivo inválido'}`)
        return
      }
      // cada estratégia lembra as suas correlacionadas (e lembra que ficou sem nenhuma)
      const ids = saneiaCorrelacionadas(mapaRef.current[e.id] ?? [], estrategiasRef.current, e.id)
      setSelecionadaId(e.id)
      setRascunho(clonar(e.params))
      setCorrelacionadas(ids)
      setPendenteId(null)
      api.definirUltima(e.id).catch(() => undefined)
      void executar(e.params, e.nome, ids)
    },
    [executar, toast],
  )

  // abertura: seleciona a última usada (ou a primeira válida) uma única vez
  useEffect(() => {
    if (iniciou.current || !lista.data) return
    iniciou.current = true
    const { estrategias: itens, ultima, correlacionar } = lista.data
    const alvo = itens.find((e) => e.id === ultima && e.valida) ?? itens.find((e) => e.valida)
    if (alvo?.params) {
      setSelecionadaId(alvo.id)
      setRascunho(clonar(alvo.params))
      setCorrelacionadas(saneiaCorrelacionadas(correlacionar?.[alvo.id] ?? [], itens, alvo.id))
    }
  }, [lista.data])

  // abertura: o BD alternativo vale só até recarregar a página — ao abrir, volta ao padrão
  const estadoBd = bd.data?.estado
  const bdEhPadrao = bd.data?.padrao
  useEffect(() => {
    if (bdConferido || estadoBd !== 'pronto') return
    if (bdEhPadrao === false) {
      api
        .voltarPadrao()
        .then((padrao) => qc.setQueryData(['dataset'], padrao))
        .catch(() => undefined)
        .finally(() => setBdConferido(true))
    } else {
      setBdConferido(true)
    }
  }, [bdConferido, estadoBd, bdEhPadrao, qc])

  // abertura: roda sozinho assim que o BD padrão estiver pronto
  useEffect(() => {
    if (rodouAoAbrir.current || !rascunho || !bdConferido || !selecionada) return
    rodouAoAbrir.current = true
    void executar(rascunho, selecionada.nome, correlacionadas)
  }, [rascunho, bdConferido, selecionada, correlacionadas, executar])

  const selecionar = useCallback(
    (id: string) => {
      if (id === selecionadaId) return
      const alvo = estrategias.find((e) => e.id === id)
      if (!alvo) return
      if (alterado) setPendenteId(id)
      else aplicarSelecao(alvo)
    },
    [alterado, aplicarSelecao, estrategias, selecionadaId],
  )

  const atualizaLista = useCallback(async (): Promise<ListaEstrategias> => {
    return qc.fetchQuery({ queryKey: ['strategies'], queryFn: api.estrategias, staleTime: 0 })
  }, [qc])

  // ------------------------------------------------------------------ correlacionar
  const aplicarCorrelacionadas = useCallback(
    (ids: string[]) => {
      if (!selecionada) return
      setCorrelacionadas(ids)
      // grava no servidor (lista vazia apaga a marca) e espelha no cache para o próximo clique na estratégia já vir certo
      api
        .definirCorrelacionar(selecionada.id, ids)
        .then(() =>
          qc.setQueryData<ListaEstrategias>(['strategies'], (antigo) => {
            if (!antigo) return antigo
            const mapa = { ...(antigo.correlacionar ?? {}) }
            if (ids.length) mapa[selecionada.id] = ids
            else delete mapa[selecionada.id]
            return { ...antigo, correlacionar: mapa }
          }),
        )
        .catch((err) => toast('erro', `Não foi possível lembrar a seleção: ${mensagem(err)}`))
      if (rascunho && valido) void executar(rascunho, selecionada.nome, ids)
    },
    [selecionada, rascunho, valido, executar, qc, toast],
  )

  const alternarCorrelacionada = useCallback(
    (id: string) => aplicarCorrelacionadas(alternaCorrelacionada(correlRef.current, id)),
    [aplicarCorrelacionadas],
  )
  const limparCorrelacionadas = useCallback(() => aplicarCorrelacionadas([]), [aplicarCorrelacionadas])

  // ------------------------------------------------------------------ CRUD
  const criar = useCallback(
    async (nome: string, copiarAtual: boolean) => {
      const nova = await api.criar(nome, copiarAtual ? rascunho : null)
      await atualizaLista()
      if (nova.params) aplicarSelecao(nova)
      toast('ok', `Estratégia “${nova.nome}” criada.`)
    },
    [rascunho, atualizaLista, aplicarSelecao, toast],
  )

  const salvar = useCallback(async (): Promise<boolean> => {
    if (!selecionada || !rascunho || !valido) return false
    try {
      const e = await api.salvar(selecionada.id, rascunho)
      await atualizaLista()
      if (e.params) setRascunho(clonar(e.params))
      toast('ok', `“${e.nome}” salva.`)
      return true
    } catch (err) {
      toast('erro', mensagem(err))
      return false
    }
  }, [selecionada, rascunho, valido, atualizaLista, toast])

  const renomear = useCallback(
    async (nome: string) => {
      if (!selecionada) return
      const e = await api.renomear(selecionada.id, nome)
      await atualizaLista()
      toast('ok', `Renomeada para “${e.nome}”.`)
    },
    [selecionada, atualizaLista, toast],
  )

  const excluir = useCallback(
    async (id: string) => {
      const alvo = estrategias.find((e) => e.id === id)
      await api.excluir(id)
      const nova = await atualizaLista()
      toast('ok', `“${alvo?.nome ?? id}” excluída.`)
      if (id !== selecionadaId) {
        // era uma correlacionada: o servidor já tirou das listas; o conjunto na tela passa a ser sem ela
        if (correlRef.current.includes(id) && rascunho && selecionada) {
          const restantes = correlRef.current.filter((x) => x !== id)
          setCorrelacionadas(restantes)
          void executar(rascunho, selecionada.nome, restantes)
        }
        return
      }
      const proxima = nova.estrategias.find((e) => e.id === nova.ultima && e.valida) ?? nova.estrategias.find((e) => e.valida)
      if (proxima) {
        mapaRef.current = nova.correlacionar ?? {}
        estrategiasRef.current = nova.estrategias
        aplicarSelecao(proxima)
      } else {
        setSelecionadaId(null)
        setRascunho(null)
        setCorrelacionadas([])
        seq.current++
        setExec(SEM_EXECUCAO)
      }
    },
    [estrategias, selecionadaId, selecionada, rascunho, atualizaLista, aplicarSelecao, executar, toast],
  )

  const descartar = useCallback(() => {
    if (salvos) setRascunho(clonar(salvos))
  }, [salvos])

  // ------------------------------------------------------------------ BD
  const trocouBD = useCallback(
    (novo: BD) => {
      qc.setQueryData(['dataset'], novo)
      seq.current++                                   // o resultado antigo é de outro BD: descarta
      setExec(SEM_EXECUCAO)
      if (rascunho && selecionada) void executar(rascunho, selecionada.nome, correlacionadas)
    },
    [qc, rascunho, selecionada, correlacionadas, executar],
  )

  // ------------------------------------------------------------------ atalhos e proteção
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        rodar()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [rodar])

  useEffect(() => {
    if (!alterado) return
    const onBefore = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', onBefore)
    return () => window.removeEventListener('beforeunload', onBefore)
  }, [alterado])

  return {
    meta: meta.data ?? null,
    metaErro: meta.error ? mensagem(meta.error) : null,
    estrategias,
    listaCarregando: lista.isPending,
    listaErro: lista.error ? mensagem(lista.error) : null,
    bd: bd.data ?? null,
    selecionada,
    rascunho,
    setRascunho,
    erros,
    valido,
    alterado,
    desatualizado,
    pendenteId,
    cancelarTroca: () => setPendenteId(null),
    confirmarTroca: () => {
      const alvo = estrategias.find((e) => e.id === pendenteId)
      if (alvo) aplicarSelecao(alvo)
    },
    selecionar,
    criar,
    salvar,
    renomear,
    excluir,
    descartar,
    trocouBD,
    correlacionadas,
    alternarCorrelacionada,
    limparCorrelacionadas,
    executando: exec.executando,
    /** Quantas estratégias a execução em andamento junta. */
    tamanhoExecucao: exec.tamanho,
    resultado: exec.resultado,
    erroExecucao: exec.erro,
    rodar,
  }
}

export type Workspace = ReturnType<typeof useWorkspace>
