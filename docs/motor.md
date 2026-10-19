# Motor (Etapas 1 a 6)

Porte do `ghostcandle/strategy_ghost_v6.py` do sistema antigo (`base_conhecimento/`), reduzido ao que o painel controla.
Código: `backend/strategylab/engine/ghost.py` (`preparar_dia` guarda o que não depende dos parâmetros; `run_day_prep` é o motor; `run_day` junta os dois para um DataFrame) e `runner.py` (`Mercado` = BD preparado, usado pelo app e pelo [laboratório](laboratorio.md)). **Trades idênticos** aos do motor antigo nos 12 cenários de
`backend/scripts/paridade_motor_antigo.py` (1054–3117 trades cada, BD inteiro) e idênticos ao simulador independente
(`backend/tests/oraculo_ref_simulador.py`, escrito do zero) no cenário base, com o filtro de afastamento ligado (3 configurações) e com os
controles das Etapas 3 e 4 (modo "próximo candle", "sair ao tocar a MM" e "Rastrear MM"; ver `backend/tests/test_modos_vs_oraculo.py`).

## A primeira entrada do dia, em resumo (o que NÃO depende dos controles)

1. **Zona:** a cada barra de 10 min, o motor olha as últimas N barras **já fechadas do mesmo dia** (a barra em formação e o dia anterior não entram)
   e guarda a **máxima** e a **mínima** delas. Só começa depois de `max(candles_gatilho, candles_media)` barras do dia (09:50 no padrão).
2. **Gatilho:** durante a barra atual, lida minuto a minuto, basta **tocar** a máxima ou a mínima da zona (`>=` / `<=`; não precisa fechar além).
   Se os dois lados forem tocados no mesmo minuto, a abertura do minuto decide qual veio primeiro.
3. **Gatilho não é entrada.** Cruzar só **arma a ordem**: ela fica congelada em `gatilho ± bracket_fracao × media_operacao` (a `media_operacao` da barra do cruzamento)
   e é **limite**. O **lado é fade**: tocou a máxima → ordem de **venda** acima dela; tocou a mínima → ordem de **compra** abaixo dela
   (com `book` = `cont`, só essa, a que fica além do gatilho).
4. **Execução:** a ordem só conta como executada quando o preço **negocia** `penetracao_ticks × 5 pts` além do nível (fila no book). Pode acontecer no
   mesmo minuto do cruzamento ou bem depois: a ordem não expira até a última entrada, e a zona fica congelada. O preço da entrada é o **nível** da ordem
   (arredondado ao tick), sem custo. Se nunca executar até a última entrada, o dia não tem operação.
5. **Depois de entrar:** o minuto da entrada é imune; stop e alvo passam a valer a partir do minuto seguinte.
6. Com o filtro **Afastamento da MM** ligado, entre os passos 2 e 3 há uma checagem (ver abaixo); reprovou, a ordem nem é armada e a busca recomeça na barra seguinte.
7. No modo **Próximo candle** (Etapa 3) os passos 4 e 5 mudam: o passo 4 continua definindo o **sinal**, mas a entrada só acontece na **abertura da barra seguinte**,
   a mercado e com custo, e o minuto dessa abertura **não** é imune (ver "Modo de entrada" abaixo).

## Regras (por pregão; barras de 10 min lidas em sub-candles de 1 min)

1. **Zona** = máxima/mínima das últimas `candles_gatilho` barras **já fechadas do dia**. O gatilho é a própria zona.
   A primeira entrada possível ocorre depois de `max(candles_gatilho, candles_media)` barras (09:50 no padrão).
2. **Gatilho cruzado** (algum sub-candle toca a máxima ou a mínima da zona): congela as pontas a
   `bracket_fracao × media_operacao` do gatilho. **Fade**: acima vende, abaixo compra.
   `media_operacao` = média de (máx − mín) das últimas `candles_media` barras fechadas (sem descarte de candle atípico, a menos que o filtro **Candle discrepante** esteja ligado).
3. **`book`** escolhe as ordens que ficam: `cont` (só além do gatilho), `recuo` (só dentro da zona), `ambas`, `acima`, `abaixo`.
   Com uma só ordem nunca há as "duas tocadas no mesmo minuto". Todas são **ordens limite**: enchem no nível, sem custo, e não expiram até a última entrada.
4. **Penetração**: a ordem só conta como executada se o preço **negociar** `penetracao_ticks × 5 pts` além do nível (fila no book).
   Na ponta de recuo, o sub-candle do cruzamento que já abriu além do nível não vale (o nível foi tocado antes de a ordem existir).
5. **Gestão**: stop = `stop_x_media × media_operacao`, alvo = `alvo_x_media × media_operacao`, recalculados a cada barra.
   O minuto da entrada é imune (no modo Padrão). Dentro de um minuto, **stop primeiro**. Stop é ordem a mercado (slippage + spread/2, arredonda contra,
   gap: se o minuto abre além do stop, sai na abertura); alvo é limite (enche no nível).
6. **Zeragem** a mercado na abertura do primeiro minuto em/após `janela_fim`; posição aberta no fim dos dados sai no fechamento.
7. **Parar o dia** após N losses (`dia`: todos do pregão; `seguidos`: um gain zera a conta) e teto de `operacoes_por_dia`.
   Um loss = trade com resultado ≤ 0 em pontos.

## Indicadores (Etapa 2) — `engine/indicators.py`

- **Média móvel (EMA)** e **Bandas de Bollinger (EMA)**, ambas com período padrão 15 e independentes entre si (`mm_periodo`, `bb_periodo`).
  Bollinger: linha central = EMA(`bb_periodo`); bandas = central ± `bb_desvio` (k, padrão 2) × desvio-padrão **populacional** do fechamento
  nos últimos `bb_periodo` candles.
- EMA com α = 2/(N+1), semeada no primeiro fechamento (`adjust=False`), sobre os **fechamentos das barras de 10 min em série contínua**
  (atravessa os pregões, como no gráfico do Profit). Só os primeiros N−1 candles do BD ficam sem valor. Pode diferir de uma plataforma
  pela semente e pela série contínua ajustada por rolagem.
- Cada função devolve, para a barra `t`, o valor **no fechamento de `t`** (usa o close de `t`). **Nada é deslocado**: quem decide na
  barra `i` lê explicitamente a posição `i − 1`. O gráfico do dia mostra os valores assim (como as plataformas).
- A média móvel é usada pelo filtro de afastamento e pela saída ao tocar a MM. Hoje as Bandas só aparecem no gráfico; o filtro das bandas virá numa etapa seguinte.

## Escada de contratos — `escada_*`

Porte do `ghost_escada_*` do sistema antigo (v6). **`escada_contratos` = 0 desliga** (padrão): 1 contrato fixo. O contrato só multiplica o ponto, não muda o caminho do preço: a escada é aplicada **ao fim de cada
pregão sobre as operações já resolvidas** (o resultado é exato) e **reseta a cada pregão**.

1. A **primeira** operação do pregão usa `escada_contratos`; **cada operação seguinte** usa o tamanho corrente. Cada **perna** conta como uma operação (as reversões entram na sequência).
2. Depois de cada operação o tamanho **sobe** (`somar`), **desce** (`subtrair`) ou **fica** (`manter`) em `escada_ganho_qtd` / `escada_perda_qtd` contratos: **ganho = pontos > 0**; pontos ≤ 0 (inclusive 0 e zeragem sem ganho) = perda.
3. Sempre entre `escada_min` e `escada_max` (piso e teto). Validação nossa: com a escada ligada, o inicial precisa estar entre o mínimo e o máximo (o sistema antigo cortava o inicial em silêncio) e o mínimo ≤ máximo.
4. `rs = pontos × contratos × R$ 0,20`. As **taxas** não entram (o backtest é antes de taxa). O custo de execução (slippage/spread) já está nos pontos, então escala com os contratos.
5. Não afeta o stop, o alvo, o trailing nem as regras de parar o dia (contam **pontos**, não R$).

## Trailing stop — `trailing_inicio_r`

Porte do `ghost_trail_start_r` do sistema antigo (v6). **0 = desligado** (padrão). Regras, verificadas contra o código antigo e contra o simulador independente:

1. **Só atualiza quando uma barra FECHA**, antes do primeiro sub-candle da barra seguinte (nada da barra em formação; sem look-ahead).
2. **Arma:** no fechamento da barra `b`, o **avanço a favor** dela (máxima − entrada numa compra; entrada − mínima numa venda) `≥ trailing_inicio_r × stop_x_media × media_operacao(b)`
   (o "risco" da perna: o mesmo stop em pontos). A `media_operacao(b)` respeita o filtro de candle discrepante.
3. **Segue:** depois de armado, a cada barra que fecha o stop protegido vai para a **mínima** (compra) / **máxima** (venda) dessa barra e **só aperta**. No fechamento que arma ele **ainda não se move**
   (o primeiro nível vem do fechamento seguinte).
4. **Stop efetivo** = o mais apertado entre `stop_x_media × media_operacao` e o nível protegido. O **alvo não muda**.
5. **Barra da entrada:** só conta o que veio **depois** da entrada. Ordem limite: a partir do sub-candle **seguinte** ao do fill (o do fill é imune). **Próximo candle:** a entrada é na abertura, então o
   sub-candle da abertura **já conta** (decisão nossa; o sistema antigo só tinha ordem limite). Reversão: a partir do sub-candle seguinte ao do stop.
6. **Saída:** a mercado, **custo cheio**; se o sub-candle abre além do nível protegido, sai na abertura (gap), como qualquer stop. Marcada como **`trailing`** quando o nível protegido era mais apertado que o stop
   normal (badge "Trail"); senão `stop`.
7. **Reversão:** saída pelo trailing com perda (pts ≤ 0, por exemplo gap ou nível acima da entrada) **também reverte**, como qualquer stop (regra do sistema antigo); com ganho não reverte. A reversão
   **zera** a proteção e reaplica o mesmo `trailing_inicio_r` ao risco da nova perna (com o stop da reversão, se houver).
8. Convive com Próximo candle, Sair ao tocar a MM (a ordem dos eventos no sub-candle usa o stop efetivo), tempo máximo, Rastrear MM e o candle discrepante.

Não há breakeven (o sistema antigo tinha, não foi pedido). O sistema antigo **não** tem o trailing no robô NTSL, então a reprodução ao vivo é suposição (reposicionar o stop na abertura de cada barra).

## Reversões (Etapa 5) — `reversoes`, `rev_stop_x_media`, `rev_alvo_x_media`

Porte exato do **stop-and-reverse** do sistema antigo (`ff2_max_reversals`, `ghost_rev_stop_mult`, `ghost_rev_gain_mult`): trades **idênticos** ao motor antigo em 3 cenários no BD inteiro
(`scripts/paridade_motor_antigo.py`) e idênticos ao simulador independente. Desligado por padrão (`reversoes` = 0); máximo **5** por ciclo.

1. **Gatilho:** só um **stop** que encerra a posição com perda (pontos ≤ 0). O **alvo, a saída ao tocar a MM e a zeragem não revertem**.
2. **Preço:** a reversão entra **no preço do stop** (já com o gap, se o minuto abriu além do stop), no **lado oposto**, **a mercado com custo cheio**. Vale também no modo Próximo candle:
   a reversão é imediata (o Próximo candle só adia a entrada inicial do ciclo).
3. **Mesmo ciclo:** as pernas revertidas têm o mesmo `ciclo` (campo `reversao` = 0 para a entrada, 1, 2, ... para as reversões). **`operacoes_por_dia` conta ciclos**, não pernas; o resumo, o win rate
   e o "parar após N losses" contam **pernas** (cada perna é uma operação, com resultado próprio). A parada por losses só é checada ao começar um ciclo novo.
4. **Stop e alvo próprios:** `rev_stop_x_media` e `rev_alvo_x_media`, em × `media_operacao` (0 = herda os da entrada). Valem até o fim do ciclo (inclusive numa 2ª reversão) e contam a
   partir do **preço do stop** (como a entrada a mercado do Próximo candle, o custo só entra no preço executado).
5. **Minuto da reversão imune** (a perna nasce no meio do minuto do stop): stop e alvo dela só valem a partir do minuto seguinte.
6. **Ignora a última entrada e o Rastrear MM:** a reversão é continuação do ciclo, não um sinal novo; só a zeragem a encerra. A **saída ao tocar a MM vale** para a perna revertida.
7. Se o stop acontece no último minuto dos dados, a perna revertida fecha no fechamento dele (`fim_dados`), como no sistema antigo.
8. O stop com resultado > 0 não existe neste motor (o stop está sempre do lado ruim e o custo só piora), então a condição "pontos ≤ 0" do sistema antigo nunca exclui um stop na prática.

## Controle de cauda (Etapa 6) — `parar_dia_perda_x_media`, `tempo_max_min`

Os dados mostraram que poucos dias concentram a perda (os 20 piores dias respondem por 34 a 42% da perda bruta). Dois controles, desligados por padrão (0 = off):

1. **Parar o dia após perder X × `media_operacao`:** ao fim de cada ciclo (todas as pernas fechadas), se o resultado **já realizado** do dia (soma das pernas, em pontos, já com custos)
   for **≤ −X × `media_operacao`**, o dia termina. A `media_operacao` é a da barra em que o próximo ciclo começaria (barras já fechadas). Igualdade encerra o dia. **Também barra a reversão**:
   se o stop que revertia já levou o dia ao limite, não reverte. Conta só o realizado (posição aberta não entra: o stop dela ainda decide).
2. **Tempo máximo na posição (minutos):** cada perna sai **a mercado, com custo cheio**, na **abertura do primeiro sub-candle** que esteja a `tempo_max_min` minutos ou mais da entrada
   (`saida_por` = `tempo`; desfecho gain/loss pelo sinal dos pontos). A entrada conta do sub-candle do preenchimento (padrão) ou da abertura (próximo candle); a perna revertida
   começa um **relógio novo**. A zeragem tem prioridade. Não reverte (só o stop reverte).

## Filtros de regime (Etapa 6) — só dado fechado, desligados por padrão

Decididos **antes de operar**, sem look-ahead. **Do dia** (conhecidos na abertura: só pregões anteriores + a abertura de hoje; sem 20 pregões de história o dia **não opera**):

- **Gap do dia** (`filtro_gap_ativo`, `filtro_gap_max_x_media`): `|abertura de hoje − fechamento de ontem| ÷ amplitude média dos 20 pregões anteriores`. Bloqueia o dia se **≥** o limite.
- **Volatilidade de ontem** (`filtro_vol_ontem_ativo`, `filtro_vol_ontem_max`): `amplitude de ontem ÷ média das 20 amplitudes anteriores a ontem`. Bloqueia o dia se **≥** o limite.
  (amplitude = máxima − mínima do pregão inteiro.)

**Da barra** (no gatilho, olhando só a barra **fechada** `i − 1`, como o Afastamento; reprovou: a busca segue na barra seguinte):

- **Largura das Bandas de Bollinger** (`filtro_bb_ativo`, `filtro_bb_largura_min_pct`, `filtro_bb_largura_max_pct`): `(banda superior − inferior) ÷ linha central × 100` no fechamento de `i − 1`
  (usa `bb_periodo` e `bb_desvio`). Reprova se **> máximo** ou **< mínimo** (mínimo 0 = sem mínimo). É o filtro das bandas que estava pendente: aqui como filtro de **volatilidade**, não de preço contra a banda.
- **Inclinação da MM** (`filtro_inclinacao_ativo`, `filtro_inclinacao_barras` N, `filtro_inclinacao_max_x_media`): `MM[i−1] − MM[i−1−N]` em pontos. Reprova se `|inclinação| ≥ X × media_operacao` (mercado direcional
  demais para o fade). Usa `mm_periodo`.
- **Candle discrepante** (`filtro_candle_discrepante_ativo`, `filtro_candle_discrepante_x`): porte do `malibu_vol_discard_mult` do sistema antigo. Na janela das `candles_media` barras fechadas, se o **maior** tamanho
  (máx − mín) for **estritamente maior** que X × o **2º maior**, esse candle (só ele) fica fora da `media_operacao`, que divide por n − 1. Vale para tudo que usa a media_operacao (bracket, stop, alvo, filtros × media, parar o dia);
  a **zona** do gatilho continua com todas as barras. Olha só barras fechadas. Validado trade a trade contra o motor antigo (parâmetro dele: `malibu_vol_discard_mult`).
| Campo (UI) | JSON | Motor antigo | Padrão | Faixa |
|---|---|---|---|---|
| Janela de operação — início / fim (zera) | `janela_inicio`, `janela_fim` | `start_hhmm`, `end_hhmm` | 09:00 / 17:30 | início < fim |
| Última entrada do dia | `ultima_entrada` (`null` = usa a zeragem) | `ghost_ult_entrada_hhmm` | 16:00 | > início, ≤ fim |
| Candles para gatilho MAX/MIN | `candles_gatilho` | `ff2_maxmin_n` | 5 | 1–30 (1 = só a máxima/mínima da barra anterior) |
| Qtd de candles para a média | `candles_media` | `ff2_media_op_n` | 5 | 2–30 |
| Bracket: fração da média | `bracket_fracao` | `ghost_k` | 0,05 | 0,05–3 |
| Modo de entrada | `modo_entrada` | — (como o `next_open` do Malibu) | padrao | padrao·proximo_candle |
| O que fica no book | `book` | `ghost_armar` | cont | ambas·cont·recuo·acima·abaixo |
| Penetração exigida (ticks) | `penetracao_ticks` | `ghost_penetra_ticks` | 1 | 0–5 |
| Parar o dia após N losses (0 = off) | `parar_apos_losses` | `ghost_parar_losses` | 0 | 0–20 |
| Como contar os losses | `contagem_losses` | `ghost_parar_modo` | dia | dia·seguidos |
| Operações por dia | `operacoes_por_dia` | `ff2_max_trades` | 1 | 1–50 |
| Stop (x media_operacao) | `stop_x_media` | `ff2_stop_mult` | 1,0 | 0,1–5 |
| Alvo (x media_operacao) | `alvo_x_media` | `ff2_gain_mult` | 3,0 | 0,1–8 |
| Média móvel (EMA): período | `mm_periodo` | — | 15 | 2–200 |
| Bollinger (EMA): período | `bb_periodo` | — | 15 | 2–200 |
| Bollinger: desvio (k) | `bb_desvio` | `bb_k` | 2,0 | 0,5–5 |
| Filtro Afastamento da MM: ligado | `filtro_afast_mm_ativo` | `op_mm_dist` (> 0) | desligado | — |
| Afastamento mínimo (x media_operacao) | `filtro_afast_mm_x_media` | `op_mm_dist` (medida diferente) | 0,7 | 0,05–10 |
| Trailing stop: arma em (× risco, 0 = off) | `trailing_inicio_r` | `ghost_trail_start_r` | 0 | 0–10 |
| Escada de contratos: início / ganho / perda / mín / máx | `escada_contratos`, `escada_ganho_acao`, `escada_ganho_qtd`, `escada_perda_acao`, `escada_perda_qtd`, `escada_min`, `escada_max` | `ghost_escada_*` | 0 (off) / manter 1 / manter 1 / 1 / 5 | 0–100 · manter\|somar\|subtrair · 1–20 · 1–100 |
| Reversões ao perder (0 = off) | `reversoes` | `ff2_max_reversals` | 0 | 0–5 |
| Stop da reversão (0 = igual ao da entrada) | `rev_stop_x_media` | `ghost_rev_stop_mult` | 0 | 0–10 |
| Alvo da reversão (0 = igual ao da entrada) | `rev_alvo_x_media` | `ghost_rev_gain_mult` | 0 | 0–10 |
| Parar o dia após perder (× media_operacao, 0 = off) | `parar_dia_perda_x_media` | — | 0 | 0–20 |
| Tempo máximo na posição (min, 0 = off) | `tempo_max_min` | — | 0 | 0–480 |
| Filtro Gap do dia: ligado / máximo (× amplitude média de 20 dias) | `filtro_gap_ativo`, `filtro_gap_max_x_media` | — | desligado / 0,5 | 0,05–5 |
| Filtro Volatilidade de ontem: ligado / máximo | `filtro_vol_ontem_ativo`, `filtro_vol_ontem_max` | — | desligado / 1,5 | 0,5–5 |
| Filtro Largura das Bandas: ligado / mínimo / máximo (% da linha central) | `filtro_bb_ativo`, `filtro_bb_largura_min_pct`, `filtro_bb_largura_max_pct` | — | desligado / 0 / 1,0 | 0–5 / 0,05–10 |
| Filtro Inclinação da MM: ligado / barras / máximo (× media_operacao) | `filtro_inclinacao_ativo`, `filtro_inclinacao_barras`, `filtro_inclinacao_max_x_media` | — | desligado / 5 / 0,5 | 2–30 / 0,05–10 |
| Filtro Candle discrepante: ligado / tamanho (× o 2º maior) | `filtro_candle_discrepante_ativo`, `filtro_candle_discrepante_x` | `malibu_vol_discard_mult` | desligado / 2,0 | 1–10 |
| Rastrear MM | `rastrear_mm` | — | desligado | — |
| Sair ao tocar a MM | `sair_ao_tocar_mm` | — | desligado | — |

## Números-âncora (BD padrão, 1.073 pregões, 2021-09-14 → 2025-12-30)

`inicial_default`: **1.054 trades em 1.054 pregões · R$ 7.391,00 · DD −4.730 (453 pregões, 30/11/2022 → 04/10/2024) · win rate 27,33%
(287 gains / 763 losses / 4 zeradas) · melhor dia +544 (18/11/2022) · pior dia −191 (31/10/2022)**.
Os outros 11 cenários estão em `backend/tests/test_golden.py`. Com o filtro de afastamento ligado (EMA 15, BD padrão): 0,7× → 926 trades / R$ 2.220; 1,5× → 486 / R$ 2.228; 0,3× com MM 30 → 1.044 / R$ 5.800 (todos iguais ao simulador independente).

Etapa 3 (BD padrão, tudo o mais no padrão; iguais ao simulador independente): **próximo candle** → 1.054 trades / R$ 625 (DD −7.256); **sair ao tocar a MM** → 1.054 / R$ 4.365 (616 saídas pela MM, DD −2.837);
**os dois** → 1.054 / −R$ 1.152 (636 saídas pela MM); os dois + filtro 0,3× → 1.033 / −R$ 3.043; sair na MM + filtro 0,2× com 4 operações por dia → 3.459 / −R$ 4.714.
Etapa 4 (iguais ao simulador independente): **Rastrear MM** → 1.058 trades / −R$ 909 (529 vendas, 529 compras); com `book` ambas → 1.057 / R$ 376; rastrear + próximo candle + sair na MM com 3 operações por dia → 3.103 / −R$ 10.966.
Etapa 5 (reversões; idênticas ao motor antigo): **1 reversão** (herda stop/alvo) → 1.817 trades / R$ 6.318 (1.054 ciclos); **2 reversões** com stop 0,5× e alvo 2× e 2 operações por dia → 4.693 / R$ 3.188;
**5 reversões**, stop 1,5×, 3 operações, book ambas, parar 2 seguidos → 5.526 / −R$ 20.869. Neste BD a reversão piora o resultado do cenário base, como o sistema antigo já tinha medido.
Com os controles novos desligados vale o cenário base (R$ 7.391).
De onde vem a queda de R$ 7.391 para R$ 625 no próximo candle (R$ 6.766), medido rodando o mesmo cenário sem nenhum custo: ≈ **R$ 5.000** são do **preço** (a abertura da barra seguinte em vez do nível da ordem:
R$ 8.535 → R$ 3.528 sem custo) e ≈ **R$ 1.760** são do **custo da entrada a mercado** (o custo total passa de R$ 1.144 para R$ 2.903). A ordem limite no nível pega o preço do extremo que o fade quer; esperar a abertura
seguinte devolve parte desse movimento.

Para comparação, o v6_10min **completo** (com reversão, trailing, filtro3 e amplitude mínima de 150 pts) dava R$ 20.051 / DD −1.717 —
a diferença é a escolha de implementar só os parâmetros pedidos.

## Honestidade do backtest

Só vale o que é reprodutível ao vivo: zona e média vêm de barras fechadas; o sub-candle só informa a **ordem** dos toques; custo cheio nas
ordens a mercado; stop primeiro quando stop e alvo caem no mesmo minuto. A maior incerteza do número é a **fila das ordens limite**
(`penetracao_ticks`): 0 tick supõe sempre ser o primeiro da fila. Detalhes e histórico no sistema antigo:
`base_conhecimento/docs/02-motores.md` e `base_conhecimento/docs/estrategias/ghostcandle_v6_10min.md`.
