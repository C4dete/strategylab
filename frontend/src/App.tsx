import { Moon, SlidersHorizontal, Sun, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from './components/ui/Button'
import { DatasetBar } from './features/dataset/DatasetBar'
import { ResultsView } from './features/results/ResultsView'
import { ControlPanel } from './features/strategies/ControlPanel'
import { camposAusentesNoServidor } from './lib/params'
import { useTheme } from './hooks/useTheme'
import { useWorkspace } from './hooks/useWorkspace'
import './App.css'

function Marca() {
  return (
    <div className="marca" aria-label="StrategyLab">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="2" fill="var(--accent-fill)" />
        <path d="M11 5v6M11 21v6M21 9v4M21 25v-4" stroke="var(--accent-ink)" strokeWidth="2" strokeLinecap="square" />
        <rect x="7.5" y="11" width="7" height="10" fill="var(--accent-ink)" />
        <rect x="17.5" y="13" width="7" height="8" fill="none" stroke="var(--accent-ink)" strokeWidth="2" />
      </svg>
      <span className="marca__nome">
        Strategy<b>Lab</b>
      </span>
    </div>
  )
}

export default function App() {
  const ws = useWorkspace()
  const { tema, alternar } = useTheme()
  const [gaveta, setGaveta] = useState(false)

  // fecha a gaveta ao executar (mobile) — o usuário quer ver o resultado
  const executando = ws.executando
  useEffect(() => {
    if (executando) setGaveta(false)
  }, [executando])

  if (ws.metaErro) {
    return (
      <div className="falha-geral" role="alert">
        <Marca />
        <h1>Não foi possível iniciar</h1>
        <p>{ws.metaErro}</p>
        <Button variant="primary" onClick={() => window.location.reload()}>Tentar de novo</Button>
      </div>
    )
  }

  const ausentes = ws.meta ? camposAusentesNoServidor(ws.meta.padrao) : []
  if (ausentes.length > 0) {
    return (
      <div className="falha-geral" role="alert">
        <Marca />
        <h1>Servidor desatualizado</h1>
        <p>
          O servidor em execução não conhece {ausentes.length === 1 ? 'o campo' : 'os campos'} <b>{ausentes.join(', ')}</b> e ignoraria esse controle em silêncio.
          Feche o StrategyLab (<code>encerrar.bat</code>) e abra de novo (<code>iniciar.bat</code>).
        </p>
        <Button variant="primary" onClick={() => window.location.reload()}>Tentar de novo</Button>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="topo">
        <Marca />
        <div className="topo__bd">
          <DatasetBar bd={ws.bd} onTrocou={ws.trocouBD} />
        </div>
        <div className="topo__acoes">
          <Button className="topo__gaveta" size="sm" icon={<SlidersHorizontal size={14} aria-hidden />} aria-label="Abrir controles da estratégia" onClick={() => setGaveta(true)}>
            <span className="rot-md">Controles</span>
          </Button>
          <button
            type="button"
            className="tema"
            onClick={alternar}
            aria-label={tema === 'dark' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'}
            title={tema === 'dark' ? 'Tema claro' : 'Tema escuro'}
          >
            {tema === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      <div className="corpo">
        <div className={`corpo__painel ${gaveta ? 'is-aberta' : ''}`}>
          <div className="corpo__cabeca">
            <span className="label">Controles</span>
            <button type="button" className="corpo__fechar" aria-label="Fechar controles" onClick={() => setGaveta(false)}>
              <X size={18} />
            </button>
          </div>
          {ws.meta ? <ControlPanel ws={ws} meta={ws.meta} /> : <div className="skel" style={{ height: '100%' }} />}
        </div>
        {gaveta && <button type="button" className="corpo__vela" aria-label="Fechar controles" onClick={() => setGaveta(false)} />}
        <main className="corpo__principal">
          {ws.listaErro ? (
            <div className="erro-exec" role="alert">
              <div><b>Não foi possível ler as estratégias.</b><p>{ws.listaErro}</p></div>
            </div>
          ) : (
            <ResultsView ws={ws} />
          )}
        </main>
      </div>
    </div>
  )
}
