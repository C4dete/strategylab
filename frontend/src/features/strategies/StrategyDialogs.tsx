import { useId, useState, type FormEvent } from 'react'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'

/** Executa uma ação assíncrona controlando "ocupado" e a mensagem de erro (que fica no diálogo). */
function useAcao() {
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const executar = async (fn: () => Promise<void>): Promise<boolean> => {
    setOcupado(true)
    setErro(null)
    try {
      await fn()
      return true
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e))
      return false
    } finally {
      setOcupado(false)
    }
  }
  return { ocupado, erro, executar }
}

// O <Modal> só monta o conteúdo enquanto está aberto: o estado de cada formulário nasce limpo a cada abertura.

// ----------------------------------------------------------------------------- nova
interface NovaProps {
  aberto: boolean
  podeCopiar: boolean
  nomeAtual: string | null
  /** A estratégia atual tem alterações não salvas (seriam perdidas ao começar dos valores padrão). */
  alterado: boolean
  onFechar: () => void
  onCriar: (nome: string, copiarAtual: boolean) => Promise<void>
}

function NovaForm({ podeCopiar, nomeAtual, alterado, onFechar, onCriar }: Omit<NovaProps, 'aberto'>) {
  const [nome, setNome] = useState('')
  const [copiar, setCopiar] = useState(false)
  const { ocupado, erro, executar } = useAcao()
  const idNome = useId()

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (await executar(() => onCriar(nome, copiar && podeCopiar))) onFechar()
  }

  return (
    <form onSubmit={enviar} className="form-dialogo">
      <div className="campo-dialogo">
        <label htmlFor={idNome}>Nome</label>
        <input
          id={idNome}
          className={`text ${erro ? 'text--invalid' : ''}`}
          value={nome}
          maxLength={60}
          data-autofocus
          autoComplete="off"
          placeholder="ex.: gatilho 8 candles, stop curto"
          onChange={(e) => setNome(e.target.value)}
        />
      </div>
      <fieldset className="opcoes-dialogo">
        <legend className="label">Começar de</legend>
        <label className="check">
          <input type="radio" name="origem" checked={!copiar} onChange={() => setCopiar(false)} />
          <span>Valores padrão</span>
        </label>
        <label className={`check ${podeCopiar ? '' : 'is-off'}`}>
          <input type="radio" name="origem" checked={copiar} disabled={!podeCopiar} onChange={() => setCopiar(true)} />
          <span>Cópia de “{nomeAtual ?? '—'}” (com as alterações em edição)</span>
        </label>
      </fieldset>
      {alterado && !copiar && (
        <p className="aviso-dialogo" role="status">
          As alterações não salvas de “{nomeAtual}” serão descartadas. Para levá-las para a nova estratégia, escolha “Cópia”.
        </p>
      )}
      {erro && <p className="erro-dialogo" role="alert">{erro}</p>}
      <div className="modal__acoes modal__acoes--inline">
        <Button variant="ghost" onClick={onFechar}>Cancelar</Button>
        <Button variant="primary" type="submit" loading={ocupado} disabled={!nome.trim()}>Criar estratégia</Button>
      </div>
    </form>
  )
}

export function NovaDialog({ aberto, ...resto }: NovaProps) {
  return (
    <Modal aberto={aberto} titulo="Nova estratégia" onFechar={resto.onFechar}>
      <NovaForm {...resto} />
    </Modal>
  )
}

// ----------------------------------------------------------------------------- renomear
interface RenomearProps {
  aberto: boolean
  nomeAtual: string
  onFechar: () => void
  onRenomear: (nome: string) => Promise<void>
}

function RenomearForm({ nomeAtual, onFechar, onRenomear }: Omit<RenomearProps, 'aberto'>) {
  const [nome, setNome] = useState(nomeAtual)
  const { ocupado, erro, executar } = useAcao()
  const idNome = useId()

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (await executar(() => onRenomear(nome))) onFechar()
  }

  return (
    <form onSubmit={enviar} className="form-dialogo">
      <div className="campo-dialogo">
        <label htmlFor={idNome}>Novo nome</label>
        <input
          id={idNome}
          className={`text ${erro ? 'text--invalid' : ''}`}
          value={nome}
          maxLength={60}
          data-autofocus
          autoComplete="off"
          onFocus={(e) => e.currentTarget.select()}
          onChange={(e) => setNome(e.target.value)}
        />
      </div>
      {erro && <p className="erro-dialogo" role="alert">{erro}</p>}
      <div className="modal__acoes modal__acoes--inline">
        <Button variant="ghost" onClick={onFechar}>Cancelar</Button>
        <Button variant="primary" type="submit" loading={ocupado} disabled={!nome.trim() || nome.trim() === nomeAtual}>
          Renomear
        </Button>
      </div>
    </form>
  )
}

export function RenomearDialog({ aberto, ...resto }: RenomearProps) {
  return (
    <Modal aberto={aberto} titulo="Renomear estratégia" onFechar={resto.onFechar}>
      <RenomearForm {...resto} />
    </Modal>
  )
}

// ----------------------------------------------------------------------------- excluir
interface ExcluirProps {
  aberto: boolean
  nome: string
  onFechar: () => void
  onExcluir: () => Promise<void>
}

function ExcluirCorpo({ nome, onFechar, onExcluir }: Omit<ExcluirProps, 'aberto'>) {
  const { ocupado, erro, executar } = useAcao()
  return (
    <>
      <p>
        Excluir <b>“{nome}”</b>? O arquivo da estratégia é removido do projeto e <b>não dá para desfazer</b>.
      </p>
      {erro && <p className="erro-dialogo" role="alert">{erro}</p>}
      <div className="modal__acoes modal__acoes--inline">
        <Button variant="ghost" onClick={onFechar}>Cancelar</Button>
        <Button variant="danger" loading={ocupado} onClick={async () => { if (await executar(onExcluir)) onFechar() }}>
          Excluir
        </Button>
      </div>
    </>
  )
}

export function ExcluirDialog({ aberto, ...resto }: ExcluirProps) {
  return (
    <Modal aberto={aberto} titulo="Excluir estratégia" onFechar={resto.onFechar}>
      <ExcluirCorpo {...resto} />
    </Modal>
  )
}

// ----------------------------------------------------------------------------- alterações pendentes
interface TrocaProps {
  aberto: boolean
  nomeAtual: string
  nomeAlvo: string
  podeSalvar: boolean
  onCancelar: () => void
  onDescartar: () => void
  onSalvar: () => Promise<void>
}

function TrocaCorpo({ nomeAtual, nomeAlvo, podeSalvar, onCancelar, onDescartar, onSalvar }: Omit<TrocaProps, 'aberto'>) {
  const { ocupado, executar } = useAcao()
  return (
    <>
      <p>
        Você alterou parâmetros de <b>“{nomeAtual}”</b> sem salvar. Ao abrir <b>“{nomeAlvo}”</b> essas alterações serão perdidas, a não ser que você salve.
      </p>
      <div className="modal__acoes modal__acoes--inline">
        <Button variant="ghost" onClick={onCancelar}>Cancelar</Button>
        <Button onClick={onDescartar}>Descartar e trocar</Button>
        <Button variant="primary" loading={ocupado} disabled={!podeSalvar} onClick={() => void executar(onSalvar)}>
          Salvar e trocar
        </Button>
      </div>
    </>
  )
}

export function TrocaDialog({ aberto, ...resto }: TrocaProps) {
  return (
    <Modal aberto={aberto} titulo="Alterações não salvas" onFechar={resto.onCancelar}>
      <TrocaCorpo {...resto} />
    </Modal>
  )
}
