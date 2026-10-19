import { ChevronRight, Play, RotateCcw, Save } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import type { Estrategia, Meta, Params } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { InfoTip } from '../../components/ui/InfoTip'
import { NumberInput } from '../../components/ui/NumberInput'
import { Segmented } from '../../components/ui/Segmented'
import { Switch } from '../../components/ui/Switch'
import { TimeInput } from '../../components/ui/TimeInput'
import type { Workspace } from '../../hooks/useWorkspace'
import { brl, numero } from '../../lib/format'
import { BOOK_OPCOES, CONTAGEM_OPCOES, ESCADA_ACAO_OPCOES, MODO_ENTRADA_OPCOES } from '../../lib/params'
import { ExcluirDialog, NovaDialog, RenomearDialog, TrocaDialog } from './StrategyDialogs'
import { StrategyList } from './StrategyList'
import './ControlPanel.css'

// ----------------------------------------------------------------------------- peças do formulário
interface CampoProps {
  id: string
  rotulo: string
  dica?: ReactNode
  erro?: string
  desabilitado?: boolean
  cheio?: boolean
  children: ReactNode
}

function Campo({ id, rotulo, dica, erro, desabilitado, cheio, children }: CampoProps) {
  return (
    <div className={`campo ${cheio ? 'campo--cheio' : ''} ${desabilitado ? 'is-off' : ''}`}>
      <div className="campo__rotulo">
        <label id={`${id}-l`} htmlFor={id}>{rotulo}</label>
        {dica && <InfoTip rotulo={`Sobre: ${rotulo}`}>{dica}</InfoTip>}
      </div>
      <div className="campo__controle">{children}</div>
      {erro && (
        <p id={`${id}-erro`} className="campo__erro" role="alert">
          {erro}
        </p>
      )}
    </div>
  )
}

function Secao({ n, titulo, children }: { n: string; titulo: string; children: ReactNode }) {
  return (
    <section className="secao">
      <h3 className="secao__titulo">
        <span className="mono">{n}</span> {titulo}
      </h3>
      <div className="secao__corpo">{children}</div>
    </section>
  )
}

function Faixa({ meta, campo }: { meta: Meta; campo: string }) {
  const f = meta.faixas[campo]
  return f ? <>Faixa: {numero(f.min, f.min % 1 ? 2 : 0)} a {numero(f.max, f.max % 1 ? 2 : 0)}.</> : null
}

// ----------------------------------------------------------------------------- painel
export function ControlPanel({ ws, meta }: { ws: Workspace; meta: Meta }) {
  const uid = useId()
  const p = ws.rascunho
  const set = (parcial: Partial<Params>) => ws.setRascunho((atual) => (atual ? { ...atual, ...parcial } : atual))
  const [dialogo, setDialogo] = useState<'nova' | 'renomear' | null>(null)
  const [excluirAlvo, setExcluirAlvo] = useState<Estrategia | null>(null)

  const f = (nome: string) => `${uid}-${nome}`
  const faixa = (c: string) => meta.faixas[c] ?? { min: 0, max: 100 }
  const alvoTroca = ws.estrategias.find((e) => e.id === ws.pendenteId)
  const ex = meta.execucao

  return (
    <aside className="painel" aria-label="Controles da estratégia">
      <div className="painel__rolagem">
        <StrategyList
          estrategias={ws.estrategias}
          selecionadaId={ws.selecionada?.id ?? null}
          alterado={ws.alterado}
          onSelecionar={ws.selecionar}
          onNova={() => setDialogo('nova')}
          onRenomear={() => setDialogo('renomear')}
          onExcluir={setExcluirAlvo}
        />

        {p ? (
          <form className="painel__form" onSubmit={(e) => { e.preventDefault(); ws.rodar() }} noValidate>
            <Secao n="01" titulo="Básico">
              <div className="campo campo--cheio">
                <div className="campo__rotulo">
                  <span id={f('janela')}>Janela de operação</span>
                  <InfoTip rotulo="Sobre: Janela de operação">
                    O sistema só procura gatilhos a partir do <b>início</b>. No horário de <b>zeragem</b> a posição aberta é encerrada a mercado e o dia termina.
                  </InfoTip>
                </div>
                <div className="janela" role="group" aria-labelledby={f('janela')}>
                  <div>
                    <label className="mini" htmlFor={f('ini')}>Início</label>
                    <TimeInput id={f('ini')} value={p.janela_inicio} onChange={(v) => set({ janela_inicio: v })} invalid={!!ws.erros.janela_inicio} />
                  </div>
                  <div>
                    <label className="mini" htmlFor={f('fim')}>Fim (zera)</label>
                    <TimeInput id={f('fim')} value={p.janela_fim} onChange={(v) => set({ janela_fim: v })} invalid={!!ws.erros.janela_fim} aria-describedby={ws.erros.janela_fim ? `${f('fim')}-erro` : undefined} />
                  </div>
                </div>
                {(ws.erros.janela_inicio || ws.erros.janela_fim) && (
                  <p id={`${f('fim')}-erro`} className="campo__erro" role="alert">{ws.erros.janela_inicio ?? ws.erros.janela_fim}</p>
                )}
              </div>

              <Campo
                id={f('ult')}
                rotulo="Última entrada do dia"
                cheio
                erro={ws.erros.ultima_entrada}
                dica={<>Último horário em que uma <b>entrada</b> pode acontecer. Separa “parar de entrar” de “zerar”: a posição aberta segue até alvo, stop ou zeragem. Sem limite, vale o horário de zeragem.</>}
              >
                <div className="ult">
                  <TimeInput
                    id={f('ult')}
                    value={p.ultima_entrada ?? p.janela_fim}
                    disabled={p.ultima_entrada === null}
                    invalid={!!ws.erros.ultima_entrada}
                    aria-describedby={ws.erros.ultima_entrada ? `${f('ult')}-erro` : undefined}
                    onChange={(v) => set({ ultima_entrada: v })}
                  />
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={p.ultima_entrada === null}
                      onChange={(e) => set({ ultima_entrada: e.target.checked ? null : (meta.padrao.ultima_entrada ?? '16:00') })}
                    />
                    <span>Sem limite</span>
                  </label>
                </div>
              </Campo>
            </Secao>

            <Secao n="02" titulo="Comportamento">
              <Campo id={f('gat')} rotulo="Candles para gatilho MAX/MIN" dica={<>Quantas barras fechadas do dia formam a zona. A máxima e a mínima delas são os gatilhos. Com 1, só a máxima/mínima da barra anterior conta. <Faixa meta={meta} campo="candles_gatilho" /></>}>
                <NumberInput id={f('gat')} value={p.candles_gatilho} min={faixa('candles_gatilho').min} max={faixa('candles_gatilho').max} onChange={(v) => set({ candles_gatilho: v })} />
              </Campo>

              <Campo id={f('med')} rotulo="Qtd de candles para a média" dica={<>Quantas barras fechadas entram na média do tamanho (máx − mín): a <b>media_operacao</b>, que dimensiona bracket, stop e alvo. <Faixa meta={meta} campo="candles_media" /></>}>
                <NumberInput id={f('med')} value={p.candles_media} min={faixa('candles_media').min} max={faixa('candles_media').max} onChange={(v) => set({ candles_media: v })} />
              </Campo>

              <Campo id={f('brk')} rotulo="Bracket: fração da média" dica={<>Distância da ordem ao gatilho, em fração da <b>media_operacao</b>. 0,05 = 5% da média. <Faixa meta={meta} campo="bracket_fracao" /></>}>
                <NumberInput id={f('brk')} value={p.bracket_fracao} casas={2} step={0.05} min={faixa('bracket_fracao').min} max={faixa('bracket_fracao').max} onChange={(v) => set({ bracket_fracao: v })} />
              </Campo>

              <Campo
                id={f('modo')}
                rotulo="Modo de entrada"
                cheio
                dica={<><b>Padrão</b>: a ordem limite executa no nível, no próprio minuto em que o preço o alcança. <b>Próximo candle</b>: quando a ordem seria executada, a entrada só acontece na <b>abertura da barra seguinte</b> ({ex.timeframe_min} min). Entra a mercado, então paga slippage e spread, e stop e alvo contam a partir do preço de abertura. Se a abertura cair na última entrada ou depois, o sinal é descartado.</>}
              >
                <Segmented
                  nome={f('modo')}
                  valor={p.modo_entrada}
                  opcoes={MODO_ENTRADA_OPCOES}
                  onChange={(v) => set({ modo_entrada: v })}
                  aria-labelledby={`${f('modo')}-l`}
                />
                <p className="campo__nota">
                  {p.modo_entrada === 'padrao'
                    ? 'Ordem limite: entra no nível, no minuto em que o preço o alcança.'
                    : `Entra a mercado na abertura da barra seguinte (${ex.timeframe_min} min), com custo.`}
                </p>
              </Campo>

              <Campo
                id={f('book')}
                rotulo="O que fica no book"
                cheio
                dica={<>Com <b>uma</b> ordem no book some o único caso em que o motor precisaria desempatar (as duas tocadas no mesmo minuto): o resultado vem inteiro dos dados.</>}
              >
                <select id={f('book')} className="select" value={p.book} onChange={(e) => set({ book: e.target.value as Params['book'] })}>
                  {BOOK_OPCOES.map((o) => (
                    <option key={o.valor} value={o.valor}>{o.rotulo}</option>
                  ))}
                </select>
                <p className="campo__nota">{BOOK_OPCOES.find((o) => o.valor === p.book)?.descricao}</p>
              </Campo>

              <Campo id={f('pen')} rotulo="Penetração exigida na ordem limite (ticks)" dica={<>A ordem limite só conta como executada se o preço <b>negociar</b> N ticks além do nível (há fila na frente). 0 = basta encostar (otimista); 1 = o realista. O preenchimento continua saindo no nível. <Faixa meta={meta} campo="penetracao_ticks" /></>}>
                <NumberInput id={f('pen')} value={p.penetracao_ticks} min={faixa('penetracao_ticks').min} max={faixa('penetracao_ticks').max} onChange={(v) => set({ penetracao_ticks: v })} />
              </Campo>

              <Campo id={f('par')} rotulo="Parar o dia após N losses (0 = off)" dica={<>Atingido o número, a ordem no book é cancelada e não há mais entradas naquele pregão. 0 desliga. <Faixa meta={meta} campo="parar_apos_losses" /></>}>
                <NumberInput id={f('par')} value={p.parar_apos_losses} min={faixa('parar_apos_losses').min} max={faixa('parar_apos_losses').max} onChange={(v) => set({ parar_apos_losses: v })} />
              </Campo>

              <Campo
                id={f('cnt')}
                rotulo="Como contar os losses"
                cheio
                desabilitado={p.parar_apos_losses === 0}
                dica={<><b>Todos do pregão</b> soma as perdas do dia. <b>Só seguidos</b> conta a sequência atual: um gain zera a conta. Só vale com “Parar o dia” ligado.</>}
              >
                <Segmented
                  nome={f('cnt')}
                  valor={p.contagem_losses}
                  opcoes={CONTAGEM_OPCOES}
                  disabled={p.parar_apos_losses === 0}
                  onChange={(v) => set({ contagem_losses: v })}
                  aria-labelledby={`${f('cnt')}-l`}
                />
              </Campo>

              <Campo id={f('ops')} rotulo="Operações por dia" dica={<>Teto de entradas por pregão. <Faixa meta={meta} campo="operacoes_por_dia" /></>}>
                <NumberInput id={f('ops')} value={p.operacoes_por_dia} min={faixa('operacoes_por_dia').min} max={faixa('operacoes_por_dia').max} onChange={(v) => set({ operacoes_por_dia: v })} />
              </Campo>

              <Campo id={f('stp')} rotulo="Stop (x media_operacao)" dica={<>Distância do stop em múltiplos da <b>media_operacao</b>, recalculada a cada barra. É ordem a mercado: paga slippage e spread. <Faixa meta={meta} campo="stop_x_media" /></>}>
                <NumberInput id={f('stp')} value={p.stop_x_media} casas={2} step={0.05} min={faixa('stop_x_media').min} max={faixa('stop_x_media').max} onChange={(v) => set({ stop_x_media: v })} />
              </Campo>

              <Campo id={f('alv')} rotulo="Alvo (x media_operacao)" dica={<>Distância do alvo em múltiplos da <b>media_operacao</b>. É ordem limite: enche no nível, sem custo. <Faixa meta={meta} campo="alvo_x_media" /></>}>
                <NumberInput id={f('alv')} value={p.alvo_x_media} casas={2} step={0.05} min={faixa('alvo_x_media').min} max={faixa('alvo_x_media').max} onChange={(v) => set({ alvo_x_media: v })} />
              </Campo>

              <Campo id={f('trl')} rotulo="Trailing stop: arma em (x risco, 0 = off)" dica={<>Quando uma barra <b>fecha</b> tendo avançado a favor da posição pelo menos “x” × o <b>risco</b> (stop × media_operacao), o trailing arma; a partir da barra seguinte que fechar, o stop passa a seguir a <b>mínima</b> (compra) ou <b>máxima</b> (venda) dela e só aperta, nunca afrouxa. O alvo não muda. Sai a mercado (com custo). A barra da entrada só conta o que veio depois da entrada. 0 desliga. <Faixa meta={meta} campo="trailing_inicio_r" /></>}>
                <NumberInput id={f('trl')} value={p.trailing_inicio_r} casas={2} step={0.05} min={faixa('trailing_inicio_r').min} max={faixa('trailing_inicio_r').max} onChange={(v) => set({ trailing_inicio_r: v })} />
              </Campo>

              <Campo id={f('pdp')} rotulo="Parar o dia após perder (× media_operacao, 0 = off)" dica={<>Ao fim de cada ciclo, se o resultado <b>já realizado</b> do dia (soma de todas as pernas) estiver em <b>−X × media_operacao</b> ou pior, o dia termina. Também impede novas reversões. Controla a cauda: poucos dias ruins concentram boa parte da perda. 0 desliga. <Faixa meta={meta} campo="parar_dia_perda_x_media" /></>}>
                <NumberInput id={f('pdp')} value={p.parar_dia_perda_x_media} casas={2} step={0.25} min={faixa('parar_dia_perda_x_media').min} max={faixa('parar_dia_perda_x_media').max} onChange={(v) => set({ parar_dia_perda_x_media: v })} />
              </Campo>

              <Campo id={f('tmx')} rotulo="Tempo máximo na posição (min, 0 = off)" dica={<>Cada perna sai <b>a mercado</b> (com custo) no primeiro minuto a N minutos ou mais da entrada, a menos que stop, alvo ou zeragem venham antes. A reversão começa um relógio novo. 0 desliga. <Faixa meta={meta} campo="tempo_max_min" /></>}>
                <NumberInput id={f('tmx')} value={p.tempo_max_min} step={5} min={faixa('tempo_max_min').min} max={faixa('tempo_max_min').max} onChange={(v) => set({ tempo_max_min: v })} />
              </Campo>
            </Secao>

            <Secao n="03" titulo="Reversão e contratos">
              <p className="secao__nota">
                O que acontece quando um stop encerra a operação com perda (<b>reversão</b>) e como o <b>tamanho da posição</b> varia ao longo do dia (<b>escada de contratos</b>).
              </p>

              <Campo id={f('rev')} rotulo="Reversões ao perder (0 = off)" dica={<>Quando um <b>stop</b> encerra a operação com perda, a posição é <b>revertida</b> no preço do stop (lado oposto, a mercado, com custo), até este número de vezes por ciclo. A reversão é continuação do mesmo ciclo: não conta em “Operações por dia”, ignora a última entrada e o Rastrear MM, e o seu primeiro minuto é imune. Só o stop reverte: alvo, saída na MM e zeragem não. <Faixa meta={meta} campo="reversoes" /></>}>
                <NumberInput id={f('rev')} value={p.reversoes} min={faixa('reversoes').min} max={faixa('reversoes').max} onChange={(v) => set({ reversoes: v })} />
              </Campo>

              {p.reversoes > 0 && (
                <div className="rev">
                  <Campo id={f('revs')} rotulo="Stop da reversão (0 = igual ao da entrada)" dica={<>Stop da posição <b>revertida</b>, em múltiplos da <b>media_operacao</b> (a mesma unidade do campo “Stop”). 0 herda o valor da entrada. Vale até o fim do ciclo, inclusive numa 2ª reversão. <Faixa meta={meta} campo="rev_stop_x_media" /></>}>
                    <NumberInput id={f('revs')} value={p.rev_stop_x_media} casas={2} step={0.05} min={faixa('rev_stop_x_media').min} max={faixa('rev_stop_x_media').max} onChange={(v) => set({ rev_stop_x_media: v })} />
                  </Campo>
                  <Campo id={f('reva')} rotulo="Alvo da reversão (0 = igual ao da entrada)" dica={<>Alvo da posição <b>revertida</b>, em múltiplos da <b>media_operacao</b>. 0 herda o valor da entrada. Vale até o fim do ciclo. <Faixa meta={meta} campo="rev_alvo_x_media" /></>}>
                    <NumberInput id={f('reva')} value={p.rev_alvo_x_media} casas={2} step={0.05} min={faixa('rev_alvo_x_media').min} max={faixa('rev_alvo_x_media').max} onChange={(v) => set({ rev_alvo_x_media: v })} />
                  </Campo>
                  <p className="campo__nota">
                    Entrada: stop {numero(p.stop_x_media, 2)} / alvo {numero(p.alvo_x_media, 2)} · <b>Reversão: stop {numero(p.rev_stop_x_media > 0 ? p.rev_stop_x_media : p.stop_x_media, 2)} / alvo {numero(p.rev_alvo_x_media > 0 ? p.rev_alvo_x_media : p.alvo_x_media, 2)}</b>
                    {p.rev_stop_x_media > 0 || p.rev_alvo_x_media > 0 ? '' : ' (herdados)'}.
                  </p>
                </div>
              )}

              <div className={`filtro ${p.escada_contratos > 0 ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('esc-t')} className="filtro__nome">Escada de contratos</span>
                  <InfoTip rotulo="Sobre: Escada de contratos" alinhar="dir">
                    O tamanho da posição <b>começa o pregão</b> no valor inicial e, depois de <b>cada operação</b> (cada perna, reversões incluídas), sobe, desce ou fica conforme ela tenha sido ganho (pontos &gt; 0) ou não (pontos ≤ 0), sempre entre o mínimo e o máximo. Reseta a cada pregão. Não muda os preços nem os stops, só quanto vale cada ponto. Com 0, vale 1 contrato fixo.
                  </InfoTip>
                </div>
                <Campo id={f('esc')} rotulo="Contratos no início do dia (0 = off)" cheio erro={ws.erros.escada_contratos} dica={<>Quantos contratos a <b>primeira</b> operação de cada pregão usa. 0 desliga a escada (1 contrato fixo). Precisa estar entre o mínimo e o máximo. <Faixa meta={meta} campo="escada_contratos" /></>}>
                  <NumberInput id={f('esc')} value={p.escada_contratos} min={faixa('escada_contratos').min} max={faixa('escada_contratos').max} onChange={(v) => set({ escada_contratos: v })} />
                </Campo>
                {p.escada_contratos > 0 && (
                  <>
                    <Campo id={f('escga')} rotulo="Depois de um ganho" cheio dica={<><b>Manter</b> o tamanho, <b>somar</b> ou <b>subtrair</b> contratos depois de uma operação com ganho (pontos &gt; 0).</>}>
                      <Segmented nome={f('escga')} valor={p.escada_ganho_acao} opcoes={ESCADA_ACAO_OPCOES} onChange={(v) => set({ escada_ganho_acao: v })} aria-labelledby={`${f('escga')}-l`} />
                    </Campo>
                    <Campo id={f('escgq')} rotulo="Quantidade (ganho)" cheio desabilitado={p.escada_ganho_acao === 'manter'} dica={<>Quantos contratos somar ou subtrair depois de um ganho. <Faixa meta={meta} campo="escada_ganho_qtd" /></>}>
                      <NumberInput id={f('escgq')} value={p.escada_ganho_qtd} min={faixa('escada_ganho_qtd').min} max={faixa('escada_ganho_qtd').max} disabled={p.escada_ganho_acao === 'manter'} onChange={(v) => set({ escada_ganho_qtd: v })} />
                    </Campo>
                    <Campo id={f('escpa')} rotulo="Depois de uma perda" cheio dica={<><b>Manter</b>, <b>somar</b> ou <b>subtrair</b> contratos depois de uma operação sem ganho (pontos ≤ 0, inclusive zeragem sem ganho).</>}>
                      <Segmented nome={f('escpa')} valor={p.escada_perda_acao} opcoes={ESCADA_ACAO_OPCOES} onChange={(v) => set({ escada_perda_acao: v })} aria-labelledby={`${f('escpa')}-l`} />
                    </Campo>
                    <Campo id={f('escpq')} rotulo="Quantidade (perda)" cheio desabilitado={p.escada_perda_acao === 'manter'} dica={<>Quantos contratos somar ou subtrair depois de uma perda. <Faixa meta={meta} campo="escada_perda_qtd" /></>}>
                      <NumberInput id={f('escpq')} value={p.escada_perda_qtd} min={faixa('escada_perda_qtd').min} max={faixa('escada_perda_qtd').max} disabled={p.escada_perda_acao === 'manter'} onChange={(v) => set({ escada_perda_qtd: v })} />
                    </Campo>
                    <Campo id={f('escmn')} rotulo="Mínimo de contratos" cheio erro={ws.erros.escada_min} dica={<>Piso: a escada nunca desce abaixo disto. <Faixa meta={meta} campo="escada_min" /></>}>
                      <NumberInput id={f('escmn')} value={p.escada_min} min={faixa('escada_min').min} max={faixa('escada_min').max} onChange={(v) => set({ escada_min: v })} />
                    </Campo>
                    <Campo id={f('escmx')} rotulo="Máximo de contratos" cheio dica={<>Teto: a escada nunca sobe acima disto. <Faixa meta={meta} campo="escada_max" /></>}>
                      <NumberInput id={f('escmx')} value={p.escada_max} min={faixa('escada_max').min} max={faixa('escada_max').max} onChange={(v) => set({ escada_max: v })} />
                    </Campo>
                    <p className="campo__nota">
                      Começa o dia com <b>{p.escada_contratos}</b>; depois de ganho: <b>{p.escada_ganho_acao === 'manter' ? 'mantém' : `${p.escada_ganho_acao === 'somar' ? '+' : '−'}${p.escada_ganho_qtd}`}</b>; depois de perda:{' '}
                      <b>{p.escada_perda_acao === 'manter' ? 'mantém' : `${p.escada_perda_acao === 'somar' ? '+' : '−'}${p.escada_perda_qtd}`}</b>; sempre entre {p.escada_min} e {p.escada_max}.
                    </p>
                  </>
                )}
              </div>
            </Secao>

            <Secao n="04" titulo="Indicadores">
              <p className="secao__nota">
                Médias <b>exponenciais</b> (EMA) sobre o fechamento de cada barra de {ex.timeframe_min} min, em série contínua (atravessam os pregões).
                Quem decide na barra atual só lê o valor do candle <b>anterior</b>, já fechado.
              </p>
              <Campo id={f('mm')} rotulo="Média móvel (EMA): período" dica={<>EMA do fechamento. É a média usada pelo filtro “Afastamento da MM”, por “Rastrear MM”, pelo filtro “Inclinação da MM” e pela saída “Sair ao tocar a MM”. <Faixa meta={meta} campo="mm_periodo" /></>}>
                <NumberInput id={f('mm')} value={p.mm_periodo} min={faixa('mm_periodo').min} max={faixa('mm_periodo').max} onChange={(v) => set({ mm_periodo: v })} />
              </Campo>
              <Campo id={f('bbp')} rotulo="Bandas de Bollinger (EMA): período" dica={<>Linha central = EMA do período; bandas = central ± k × desvio-padrão (populacional) do fechamento nesse mesmo período. <Faixa meta={meta} campo="bb_periodo" /></>}>
                <NumberInput id={f('bbp')} value={p.bb_periodo} min={faixa('bb_periodo').min} max={faixa('bb_periodo').max} onChange={(v) => set({ bb_periodo: v })} />
              </Campo>
              <Campo id={f('bbk')} rotulo="Bandas de Bollinger: desvio (k)" dica={<>Quantos desvios-padrão separam cada banda da linha central. Padrão 2. <Faixa meta={meta} campo="bb_desvio" /></>}>
                <NumberInput id={f('bbk')} value={p.bb_desvio} casas={2} step={0.1} min={faixa('bb_desvio').min} max={faixa('bb_desvio').max} onChange={(v) => set({ bb_desvio: v })} />
              </Campo>
            </Secao>

            <Secao n="05" titulo="Filtros">
              <p className="secao__nota">
                Cada item liga e desliga. Os <b>filtros</b> são verificados antes de a ordem entrar no book, só com dado já fechado: os de <b>barra</b> no gatilho (candle anterior), os de <b>dia</b> na abertura (dias anteriores + a abertura de hoje).
                O <b>Rastrear MM</b> também decide no gatilho. A <b>saída na MM</b> vale com a posição aberta e <b>não substitui</b> o stop e o alvo: o que vier primeiro encerra a operação.
              </p>
              <div className={`filtro ${p.filtro_afast_mm_ativo ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('faf')} className="filtro__nome">Afastamento da MM</span>
                  <InfoTip rotulo="Sobre: Afastamento da MM" alinhar="dir">
                    O candle de referência (o último fechado antes da barra do gatilho) precisa estar afastado da média móvel em pelo menos “x” vezes a <b>media_operacao</b>. Candle acima da MM: conta do <b>fundo</b> até a MM. Abaixo: do <b>topo</b> até a MM. Se cruza ou encosta na MM, reprova. A MM lida é a do <b>fechamento desse mesmo candle</b>.
                  </InfoTip>
                  <Switch checked={p.filtro_afast_mm_ativo} onChange={(v) => set({ filtro_afast_mm_ativo: v })} aria-labelledby={f('faf')} />
                </div>
                <p className="filtro__regra">
                  Candle acima da MM: <b>mínima − MM</b> · abaixo: <b>MM − máxima</b> · cruzando a MM: reprovado.
                </p>
                {p.filtro_afast_mm_ativo && (
                  <Campo id={f('fax')} rotulo="Afastamento mínimo (x media_operacao)" cheio dica={<>Distância mínima entre o candle de referência e a MM, em múltiplos da <b>media_operacao</b> (que se adapta à volatilidade do dia). Passa se a distância for <b>maior ou igual</b>. <Faixa meta={meta} campo="filtro_afast_mm_x_media" /></>}>
                    <div className="filtro__valor">
                      <NumberInput id={f('fax')} value={p.filtro_afast_mm_x_media} casas={2} step={0.05} min={faixa('filtro_afast_mm_x_media').min} max={faixa('filtro_afast_mm_x_media').max} onChange={(v) => set({ filtro_afast_mm_x_media: v })} />
                      <span className="filtro__usa mono">MM {p.mm_periodo}</span>
                    </div>
                  </Campo>
                )}
              </div>
              <div className={`filtro ${p.filtro_gap_ativo ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('fgp')} className="filtro__nome">Gap do dia</span>
                  <InfoTip rotulo="Sobre: Gap do dia" alinhar="dir">
                    Bloqueia o <b>dia inteiro</b> se a abertura de hoje se afastou do fechamento de ontem em pelo menos “x” vezes a <b>amplitude média dos 20 pregões anteriores</b>. Decidido na abertura, só com dados já fechados. Sem 20 pregões de história, o dia fica de fora.
                  </InfoTip>
                  <Switch checked={p.filtro_gap_ativo} onChange={(v) => set({ filtro_gap_ativo: v })} aria-labelledby={f('fgp')} />
                </div>
                <p className="filtro__regra">Abertura longe do fechamento de ontem: <b>o dia não opera</b>.</p>
                {p.filtro_gap_ativo && (
                  <Campo id={f('fgpv')} rotulo="Gap máximo (× amplitude média de 20 dias)" cheio dica={<>O dia é bloqueado se |abertura − fechamento de ontem| ÷ amplitude média for <b>maior ou igual</b> a este valor. <Faixa meta={meta} campo="filtro_gap_max_x_media" /></>}>
                    <NumberInput id={f('fgpv')} value={p.filtro_gap_max_x_media} casas={2} step={0.05} min={faixa('filtro_gap_max_x_media').min} max={faixa('filtro_gap_max_x_media').max} onChange={(v) => set({ filtro_gap_max_x_media: v })} />
                  </Campo>
                )}
              </div>
              <div className={`filtro ${p.filtro_vol_ontem_ativo ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('fvo')} className="filtro__nome">Volatilidade de ontem</span>
                  <InfoTip rotulo="Sobre: Volatilidade de ontem" alinhar="dir">
                    Bloqueia o <b>dia</b> se a amplitude (máxima − mínima) de ontem foi pelo menos “x” vezes a média das <b>20 amplitudes anteriores a ontem</b>: o dia seguinte a um choque de volatilidade. Decidido na abertura.
                  </InfoTip>
                  <Switch checked={p.filtro_vol_ontem_ativo} onChange={(v) => set({ filtro_vol_ontem_ativo: v })} aria-labelledby={f('fvo')} />
                </div>
                <p className="filtro__regra">Ontem muito mais amplo que o normal: <b>o dia não opera</b>.</p>
                {p.filtro_vol_ontem_ativo && (
                  <Campo id={f('fvov')} rotulo="Amplitude de ontem máxima (× média)" cheio dica={<>Bloqueia se amplitude de ontem ÷ média das 20 anteriores for <b>maior ou igual</b> a este valor. <Faixa meta={meta} campo="filtro_vol_ontem_max" /></>}>
                    <NumberInput id={f('fvov')} value={p.filtro_vol_ontem_max} casas={2} step={0.1} min={faixa('filtro_vol_ontem_max').min} max={faixa('filtro_vol_ontem_max').max} onChange={(v) => set({ filtro_vol_ontem_max: v })} />
                  </Campo>
                )}
              </div>
              <div className={`filtro ${p.filtro_bb_ativo ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('fbb')} className="filtro__nome">Largura das Bandas de Bollinger</span>
                  <InfoTip rotulo="Sobre: Largura das Bandas de Bollinger" alinhar="dir">
                    No gatilho, olha a barra <b>fechada anterior</b>: largura = (banda superior − inferior) ÷ linha central, em %. Reprova se ficar <b>acima do máximo</b> ou <b>abaixo do mínimo</b> (0 = sem mínimo). Usa o período e o desvio da seção 04. Bandas largas = volatilidade alta; estreitas = mercado parado.
                  </InfoTip>
                  <Switch checked={p.filtro_bb_ativo} onChange={(v) => set({ filtro_bb_ativo: v })} aria-labelledby={f('fbb')} />
                </div>
                <p className="filtro__regra">Bandas {p.bb_periodo} / {numero(p.bb_desvio, 1)}σ largas ou estreitas demais: <b>reprova a barra</b>.</p>
                {p.filtro_bb_ativo && (
                  <>
                    <Campo id={f('fbbn')} rotulo="Largura mínima (% da linha central, 0 = sem)" cheio erro={ws.erros.filtro_bb_largura_min_pct} dica={<>Reprova se a largura for <b>menor</b> que este valor. 0 desliga o mínimo. <Faixa meta={meta} campo="filtro_bb_largura_min_pct" /></>}>
                      <NumberInput id={f('fbbn')} value={p.filtro_bb_largura_min_pct} casas={2} step={0.05} min={faixa('filtro_bb_largura_min_pct').min} max={faixa('filtro_bb_largura_min_pct').max} onChange={(v) => set({ filtro_bb_largura_min_pct: v })} />
                    </Campo>
                    <Campo id={f('fbbx')} rotulo="Largura máxima (% da linha central)" cheio dica={<>Reprova se a largura for <b>maior</b> que este valor. <Faixa meta={meta} campo="filtro_bb_largura_max_pct" /></>}>
                      <NumberInput id={f('fbbx')} value={p.filtro_bb_largura_max_pct} casas={2} step={0.05} min={faixa('filtro_bb_largura_max_pct').min} max={faixa('filtro_bb_largura_max_pct').max} onChange={(v) => set({ filtro_bb_largura_max_pct: v })} />
                    </Campo>
                  </>
                )}
              </div>
              <div className={`filtro ${p.filtro_inclinacao_ativo ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('fin')} className="filtro__nome">Inclinação da MM</span>
                  <InfoTip rotulo="Sobre: Inclinação da MM" alinhar="dir">
                    No gatilho, mede quanto a MM subiu ou caiu nas últimas N barras fechadas (MM[i−1] − MM[i−1−N], em pontos). Reprova se |inclinação| ≥ “x” × <b>media_operacao</b>: mercado direcional demais para operar o fade. Usa o período da MM da seção 04.
                  </InfoTip>
                  <Switch checked={p.filtro_inclinacao_ativo} onChange={(v) => set({ filtro_inclinacao_ativo: v })} aria-labelledby={f('fin')} />
                </div>
                <p className="filtro__regra">MM {p.mm_periodo} muito inclinada: <b>reprova a barra</b> (mercado direcional).</p>
                {p.filtro_inclinacao_ativo && (
                  <>
                    <Campo id={f('finb')} rotulo="Barras para medir a inclinação (N)" cheio dica={<>Janela da inclinação: MM de agora menos a MM de N barras antes. <Faixa meta={meta} campo="filtro_inclinacao_barras" /></>}>
                      <NumberInput id={f('finb')} value={p.filtro_inclinacao_barras} min={faixa('filtro_inclinacao_barras').min} max={faixa('filtro_inclinacao_barras').max} onChange={(v) => set({ filtro_inclinacao_barras: v })} />
                    </Campo>
                    <Campo id={f('finx')} rotulo="Inclinação máxima (× media_operacao)" cheio dica={<>Reprova se |inclinação| for <b>maior ou igual</b> a este valor × media_operacao. <Faixa meta={meta} campo="filtro_inclinacao_max_x_media" /></>}>
                      <NumberInput id={f('finx')} value={p.filtro_inclinacao_max_x_media} casas={2} step={0.05} min={faixa('filtro_inclinacao_max_x_media').min} max={faixa('filtro_inclinacao_max_x_media').max} onChange={(v) => set({ filtro_inclinacao_max_x_media: v })} />
                    </Campo>
                  </>
                )}
              </div>
              <div className={`filtro ${p.filtro_candle_discrepante_ativo ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('fcd')} className="filtro__nome">Candle discrepante</span>
                  <InfoTip rotulo="Sobre: Candle discrepante" alinhar="dir">
                    Na janela das barras da <b>media_operacao</b>, se o <b>maior</b> candle (máx − mín) for mais de “x” vezes o <b>2º maior</b>, ele é eliminado do cálculo da média (que passa a dividir por n − 1). Evita que um candle de notícia infle o bracket, o stop e o alvo. Elimina no máximo um candle por barra e só olha barras fechadas. A zona de gatilho (máx/mín) continua usando todas as barras.
                  </InfoTip>
                  <Switch checked={p.filtro_candle_discrepante_ativo} onChange={(v) => set({ filtro_candle_discrepante_ativo: v })} aria-labelledby={f('fcd')} />
                </div>
                <p className="filtro__regra">Candle com mais de <b>{numero(p.filtro_candle_discrepante_x, 1)}×</b> o 2º maior: <b>fora da media_operacao</b>.</p>
                {p.filtro_candle_discrepante_ativo && (
                  <Campo id={f('fcdx')} rotulo="Tamanho do discrepante (× o 2º maior)" cheio dica={<>O candle é eliminado se for <b>maior</b> que este valor × o 2º maior da janela (igual não elimina). <Faixa meta={meta} campo="filtro_candle_discrepante_x" /></>}>
                    <NumberInput id={f('fcdx')} value={p.filtro_candle_discrepante_x} casas={1} step={0.1} min={faixa('filtro_candle_discrepante_x').min} max={faixa('filtro_candle_discrepante_x').max} onChange={(v) => set({ filtro_candle_discrepante_x: v })} />
                  </Campo>
                )}
              </div>
              <div className={`filtro ${p.rastrear_mm ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('rmm')} className="filtro__nome">Rastrear MM</span>
                  <InfoTip rotulo="Sobre: Rastrear MM" alinhar="dir">
                    Só opera a favor do lado da média móvel: com o preço <b>acima</b> da MM só acontecem <b>vendas</b>; <b>abaixo</b>, só <b>compras</b>. O lado é decidido no gatilho, pelo <b>fechamento do candle anterior</b> contra a MM do fechamento desse mesmo candle (nada da barra em formação). Fechamento igual à MM não opera. Com “As duas pontas” no book, só a ordem do lado permitido é armada.
                  </InfoTip>
                  <Switch checked={p.rastrear_mm} onChange={(v) => set({ rastrear_mm: v })} aria-labelledby={f('rmm')} />
                </div>
                <p className="filtro__regra">
                  Fechamento anterior <b>acima</b> da MM {p.mm_periodo}: só vende · <b>abaixo</b>: só compra.
                </p>
              </div>
              <div className={`filtro ${p.sair_ao_tocar_mm ? 'is-on' : ''}`}>
                <div className="filtro__topo">
                  <span id={f('smm')} className="filtro__nome">Sair ao tocar a MM</span>
                  <InfoTip rotulo="Sobre: Sair ao tocar a MM" alinhar="dir">
                    Com a posição aberta, a operação é encerrada quando o preço <b>toca</b> a média móvel, a menos que o stop ou o alvo aconteçam antes (a saída normal continua valendo). A MM lida é a do <b>fechamento da barra anterior</b>, fixa durante a barra atual: nada da barra em formação entra na conta. Sai a <b>mercado</b>, no nível da MM, pagando slippage e spread; se o minuto já abrir além da MM contra a posição, sai na abertura. No modo Padrão, o minuto da entrada ainda não é gerido.
                  </InfoTip>
                  <Switch checked={p.sair_ao_tocar_mm} onChange={(v) => set({ sair_ao_tocar_mm: v })} aria-labelledby={f('smm')} />
                </div>
                <p className="filtro__regra">
                  Tocou a <b>MM {p.mm_periodo}</b> (fechamento da barra anterior): encerra a operação a mercado.
                </p>
              </div>
            </Secao>

            <details className="fixo">
              <summary>
                <ChevronRight size={14} aria-hidden /> <span>Execução fixa ({ex.ativo})</span>
              </summary>
              <dl>
                <div><dt>Ativo</dt><dd>{ex.ativo} · {ex.descricao_ativo}</dd></div>
                <div><dt>Perfil</dt><dd>{ex.perfil}</dd></div>
                <div><dt>Contratos</dt><dd className="mono">{ex.contratos}</dd></div>
                <div><dt>Valor do ponto</dt><dd className="mono">{brl(ex.valor_ponto)}</dd></div>
                <div><dt>Barras</dt><dd className="mono">{ex.timeframe_min} min (leitura em {ex.leitura_min} min)</dd></div>
                <div><dt>Custos a mercado</dt><dd className="mono">slippage {numero(ex.slippage_pts)} · spread {numero(ex.spread_pts)} · tick {numero(ex.tick_pts)} pts</dd></div>
                <div><dt>Entrada</dt><dd>{ex.entrada}</dd></div>
                <div><dt>Gestão</dt><dd>Sem trailing ou breakeven</dd></div>
              </dl>
            </details>
          </form>
        ) : (
          <p className="painel__vazio">Selecione ou crie uma estratégia para editar os parâmetros.</p>
        )}
      </div>

      <footer className="painel__rodape">
        <Button
          variant="primary"
          className="painel__rodar"
          icon={<Play size={15} aria-hidden />}
          loading={ws.executando}
          disabled={!p || !ws.valido}
          onClick={ws.rodar}
        >
          {ws.executando ? 'Executando…' : 'Executar backtest'}
          {!ws.executando && <kbd>Ctrl ↵</kbd>}
        </Button>
        <div className="painel__salvar">
          <span className={`painel__status ${ws.alterado ? 'is-alterado' : ''}`}>
            {!p ? '' : !ws.valido ? 'Corrija os campos destacados' : ws.alterado ? 'Alterações não salvas' : 'Salva no projeto'}
          </span>
          <Button size="sm" variant="ghost" icon={<RotateCcw size={14} aria-hidden />} disabled={!ws.alterado} onClick={ws.descartar}>
            Descartar
          </Button>
          <Button size="sm" icon={<Save size={14} aria-hidden />} disabled={!ws.alterado || !ws.valido} onClick={() => void ws.salvar()}>
            Salvar
          </Button>
        </div>
      </footer>

      <NovaDialog
        aberto={dialogo === 'nova'}
        podeCopiar={!!p}
        nomeAtual={ws.selecionada?.nome ?? null}
        alterado={ws.alterado}
        onFechar={() => setDialogo(null)}
        onCriar={ws.criar}
      />
      {ws.selecionada && (
        <RenomearDialog
          aberto={dialogo === 'renomear'}
          nomeAtual={ws.selecionada.nome}
          onFechar={() => setDialogo(null)}
          onRenomear={ws.renomear}
        />
      )}
      <ExcluirDialog
        aberto={excluirAlvo !== null}
        nome={excluirAlvo?.nome ?? ''}
        onFechar={() => setExcluirAlvo(null)}
        onExcluir={async () => { if (excluirAlvo) await ws.excluir(excluirAlvo.id) }}
      />
      {ws.selecionada && alvoTroca && (
        <TrocaDialog
          aberto
          nomeAtual={ws.selecionada.nome}
          nomeAlvo={alvoTroca.nome}
          podeSalvar={ws.valido}
          onCancelar={ws.cancelarTroca}
          onDescartar={ws.confirmarTroca}
          onSalvar={async () => { if (await ws.salvar()) ws.confirmarTroca() }}
        />
      )}
    </aside>
  )
}
