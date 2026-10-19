import { AlertTriangle, Database, FileUp, Loader2, Undo2 } from 'lucide-react'
import { useRef, useState, type ChangeEvent } from 'react'
import { api } from '../../api/client'
import type { BD } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { useToast } from '../../components/ui/Toast'
import { dataBR, numero } from '../../lib/format'
import './DatasetBar.css'

interface Props {
  bd: BD | null
  onTrocou: (bd: BD) => void
}

export function DatasetBar({ bd, onTrocou }: Props) {
  const { toast } = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [ocupado, setOcupado] = useState<'enviando' | 'voltando' | null>(null)
  const [falha, setFalha] = useState<{ arquivo: string; mensagem: string } | null>(null)

  const aoEscolher = async (e: ChangeEvent<HTMLInputElement>) => {
    const arquivo = e.target.files?.[0]
    e.target.value = ''                 // permite escolher o mesmo arquivo de novo
    if (!arquivo) return
    setOcupado('enviando')
    try {
      const novo = await api.enviarDataset(arquivo)
      onTrocou(novo)
      toast('ok', `BD carregado: ${novo.nome} · ${numero(novo.pregoes ?? 0)} pregões.`)
      novo.avisos.forEach((a) => toast('info', a))
    } catch (err) {
      setFalha({ arquivo: arquivo.name, mensagem: err instanceof Error ? err.message : String(err) })
    } finally {
      setOcupado(null)
    }
  }

  const voltar = async () => {
    setOcupado('voltando')
    try {
      const padrao = await api.voltarPadrao()
      onTrocou(padrao)
      toast('ok', `De volta ao BD padrão: ${padrao.nome}.`)
    } catch (err) {
      toast('erro', err instanceof Error ? err.message : String(err))
    } finally {
      setOcupado(null)
    }
  }

  const pronto = bd?.estado === 'pronto'

  return (
    <div className="bd">
      <div className="bd__chip" aria-live="polite">
        {bd === null || bd.estado === 'carregando' ? (
          <>
            <Loader2 size={16} className="spin" aria-hidden />
            <span className="bd__txt">Carregando o BD padrão…</span>
          </>
        ) : bd.estado === 'erro' ? (
          <>
            <AlertTriangle size={16} className="neg" aria-hidden />
            <span className="bd__txt neg">{bd.erro ?? 'BD indisponível'}</span>
          </>
        ) : (
          <>
            <Database size={16} aria-hidden />
            <span className="bd__nome" title={bd.nome ?? ''}>{bd.nome}</span>
            <span className={`bd__tag ${bd.padrao ? '' : 'bd__tag--custom'}`}>{bd.padrao ? 'padrão' : 'outro BD'}</span>
            <span className="bd__meta mono">
              {bd.timeframe_min} min · {numero(bd.linhas ?? 0)} candles · {numero(bd.pregoes ?? 0)} pregões · {dataBR(bd.inicio)} → {dataBR(bd.fim)}
            </span>
            {bd.avisos.length > 0 && (
              <span className="bd__aviso" title={bd.avisos.join('\n')}>
                <AlertTriangle size={14} aria-hidden />
                <span className="sr-only">{bd.avisos.join(' ')}</span>
              </span>
            )}
          </>
        )}
      </div>

      <input ref={input} type="file" accept=".csv,text/csv,text/plain" className="sr-only" tabIndex={-1} onChange={aoEscolher} />
      <Button
        size="sm"
        icon={<FileUp size={14} aria-hidden />}
        loading={ocupado === 'enviando'}
        disabled={ocupado !== null}
        aria-label="Selecionar outro BD"
        title="Selecionar outro BD"
        onClick={() => input.current?.click()}
      >
        <span className="rot-lg">Selecionar outro BD</span>
      </Button>
      {pronto && bd && !bd.padrao && (
        <Button size="sm" variant="ghost" icon={<Undo2 size={14} aria-hidden />} loading={ocupado === 'voltando'} disabled={ocupado !== null} onClick={voltar} aria-label="Voltar ao padrão" title="Voltar ao BD padrão">
          <span className="rot-lg">Voltar ao padrão</span>
        </Button>
      )}

      <Modal aberto={falha !== null} titulo="Não foi possível carregar o arquivo" onFechar={() => setFalha(null)}
        acoes={<Button variant="primary" onClick={() => setFalha(null)}>Entendi</Button>}>
        <p><b className="mono">{falha?.arquivo}</b></p>
        <p className="erro-dialogo" role="alert">{falha?.mensagem}</p>
        <p>
          O BD precisa estar no mesmo padrão do BD padrão: separador <span className="mono">;</span>, cabeçalho{' '}
          <span className="mono">CANDLE;OPEN;HIGH;LOW;CLOSE;VFIN;VNEG</span> e datas <span className="mono">dd/mm/aaaa hh:mm</span>.
          Candles de 1 minuto são o recomendado. O BD atual continua ativo.
        </p>
      </Modal>
    </div>
  )
}
