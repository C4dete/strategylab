# Decisões

Registro curto do "por que é assim". Datas em 2026.

## 08/10 — Etapa 1

- **Reescrita do zero, base antiga só como referência.** O sistema antigo (Streamlit, um bloco de controles por estratégia) ficou grande
  e desorganizado. `base_conhecimento/` não é alterada nem importada pelo produto (só pelo script de paridade).
- **Só os parâmetros pedidos.** O v6_10min completo tem reversão, trailing, freio de formação e amplitude mínima; nenhum foi pedido,
  então ficam fora e o resultado difere do v6 (R$ 7.391 contra R$ 20.051). Cada próxima etapa expõe mais parâmetros como **campos novos**
  em `Params` (com padrão neutro), sem quebrar os JSON salvos.
- **WIN fixo, perfil "Ao vivo (candle fechado)" fixo.** Sem seletor de ativo nem de perfil; ver `engine/params.py::EXECUCAO`.
- **Stack:** FastAPI (reaproveita o motor Python validado) + React/TypeScript/Vite com CSS próprio (sem biblioteca de componentes) +
  ECharts. Um servidor só em `127.0.0.1:8765`. Fontes Fira self-hosted (funciona offline).
- **Estratégias em JSON no projeto** (`estrategias/`), id estável ao renomear, escrita atômica, semente `inicial_default` uma única vez.
  Abre na **última estratégia usada** (guardada em `estrategias/_estado.json`).
- **BD alternativo vale só até recarregar a página** (igual ao sistema antigo): ao abrir, o frontend pede ao servidor para voltar ao padrão.
  Evita ler resultado de um BD achando que é do padrão. O chip do topo sempre mostra qual BD está ativo.
- **Backtest sob demanda:** ~4 s por execução. O painel edita um rascunho; "Executar" (Ctrl+Enter) roda; "Salvar" grava. O resultado
  mostra "Parâmetros alterados — execute para atualizar" enquanto o rascunho difere do que foi executado.
- **Resultados em cache** no servidor por (hash do BD, parâmetros). Execução pesada serializada por lock.
- **Interface:** tema escuro "mesa de operações" (padrão) e claro "papel", cantos de 2 px, verde/vermelho só para resultado, âmbar como
  destaque de interação. Gráfico de candles do dia mantido dentro de "Operações do dia" (ajuda a conferir o motor).
- **Fora desta etapa:** motores de simulações internas, conversor Profit/MT5, comparação entre estratégias, direção (fade) editável.

## Verificação do motor

Camadas (`python -m pytest backend`): (1) casos sintéticos das regras, do filtro e das saídas (`tests/test_engine_unit.py`) e dos indicadores
(`tests/test_indicators.py`); (2) paridade trade a trade com o motor antigo em 12 cenários + números-âncora fixos (`tests/test_golden.py`,
`scripts/paridade_motor_antigo.py`); (3) simulador independente do sistema antigo, estendido com o filtro e com os controles da Etapa 3
(`tests/oraculo_ref_simulador.py`, `tests/test_modos_vs_oraculo.py`); (4) look-ahead: futuro destruído e perturbação cirúrgica (`tests/test_sem_lookahead.py`);
(5) **matriz de combinações** dos controles com invariantes (`tests/test_combinacoes.py`); (6) armazenamento, API e dados (`test_store`, `test_api`, `test_data`).

## 08/10 — Etapa 2: Indicadores e Filtros

- **03 Indicadores:** média móvel e Bandas de Bollinger, ambas EMA, períodos independentes (padrão 15). Incluí o desvio (k = 2) das bandas porque
  sem ele Bollinger não existe; é o único campo além dos pedidos. As bandas só aparecem no gráfico por enquanto.
- **04 Filtros:** cada filtro liga/desliga e vem **desligado** (a `inicial_default` continua dando R$ 7.391). Primeiro filtro: **Afastamento da MM**.
- **Afastamento em × `media_operacao`** (como no setup da base), não em pontos: acompanha a volatilidade do dia. Mínimo, inclusivo.
- **Decidido no gatilho** (resposta do Ricardo): o candle de referência é o fechado anterior à barra do gatilho, olhado uma vez antes de a ordem entrar no
  book. Alternativa descartada: checar no preenchimento (só difere quando a ordem executa em barra posterior à do gatilho).
- **Sem look-ahead, medido:** os indicadores não são deslocados; o motor lê `i − 1` de forma explícita; testes com o futuro destruído e perturbação cirúrgica
  (ver `docs/motor.md`). Corrigi uma inconsistência do sistema antigo (candle `i − 1` contra a EMA de `i − 2`).
- **Cache por o que importa:** Bollinger (só gráfico) e MM sem filtro não invalidam o resultado em cache; mudar só isso e executar é instantâneo.
- **Fora desta etapa:** filtro das bandas (a próxima), direção (fade/momentum) do afastamento, teto de afastamento (`op_mm_max`).

## 09/10 — Etapa 3: Modo de entrada e Sair ao tocar a MM

- **Modo de entrada** (antes de "O que fica no book"): `padrao` (o de sempre) e `proximo_candle`. O sinal é o mesmo; a entrada só acontece na **abertura da barra de 10 min seguinte**
  ao minuto em que a ordem teria executado. Segui a entrada `next_open` do Malibu no sistema antigo: **a mercado com custo cheio**, **stop/alvo contados a partir do preço de abertura**
  e **minuto da abertura não imune** (a entrada é no início dele, então não há o que esconder). Se a abertura cair na última entrada ou depois, ou não houver barra seguinte, o sinal morre
  (coerente com "a ordem não executou até a última entrada").
- **Efeito medido (BD padrão):** R$ 7.391 → R$ 625. Rodando sem nenhum custo: ≈ R$ 5.000 vêm do preço (abertura em vez do nível da ordem) e ≈ R$ 1.760 do custo da entrada a mercado.
  O fade com ordem limite captura o preço do extremo; esperar a abertura seguinte devolve parte disso.
- **Sair ao tocar a MM** fica na seção "04 Filtros", como pedido, embora aja com a posição aberta (e não no gatilho). A MM é a EMA do **fechamento da barra anterior**, congelada durante a barra
  atual (nada da barra em formação). "Tocar" é o caminho do preço alcançar a MM, inclusive um gap que a pule.
- **Preço da saída na MM** (resposta do Ricardo): **a mercado, custo cheio**, no nível da MM; toque contra a posição com o minuto já aberto além da MM sai na abertura (gap), como o stop.
  Alternativas descartadas: limite no nível sem custo (otimista) e "depende do lado do toque".
- **Mais de um evento no mesmo minuto:** ordem pessimista (lado adverso antes do a favor; no mesmo lado, o mais próximo). É a mesma ideia do "stop primeiro", estendida à MM.
- **`saida_por` por operação** (`stop`, `alvo`, `mm`, `zeragem`, `fim_dados`): não foi pedido, mas é o que permite conferir na tabela se uma saída veio da MM. O desfecho segue sendo gain/loss pelo sinal dos pontos.
- **Cache:** com a saída na MM ligada, o período da MM passa a valer no resultado mesmo com o filtro desligado.
- **Rotina de combinações:** todo controle novo entra na matriz de `test_combinacoes.py` (hoje 9.600 combinações, amostra rápida + produto completo) e, se possível, no simulador independente.

## 09/10 — Etapa 4: Rastrear MM e revisão da saída na MM

- **Rastrear MM** (seção 04 Filtros): acima da MM só vendas, abaixo só compras. Referência escolhida pelo Ricardo: o **fechamento da barra anterior** contra a MM do fechamento dela, decidido no gatilho
  (alternativas descartadas: o preço da ordem; o candle inteiro acima/abaixo). Igual à MM não opera. Com o book `ambas` só a ordem permitida é armada.
- **Efeito medido (BD padrão):** R$ 7.391 → −R$ 909 (1.058 trades). Operar só em direção à MM, no fade, piorou o resultado nesta amostra.
- **Saída na MM revisada:** o Ricardo lembrou que ela é só uma condição a mais e não exclui a saída normal. O motor já fazia isso; agora há testes explícitos (stop e alvo antes do toque sai neles; propriedade
  "a saída com MM nunca é posterior e, se não foi a MM, é igual à normal") e a dica da interface diz isso.

## 09/10 — Etapa 5: Reversões

- **Porte fiel do stop-and-reverse do sistema antigo**, com 0–5 reversões por ciclo e stop/alvo próprios da reversão (0 = herda). Como a lógica é a antiga, o teste forte é a **paridade trade a trade com o motor
  antigo** (3 cenários no BD inteiro, até 5.526 operações), além do simulador independente.
- **Decisões do Ricardo nas interações com os controles novos** (todas as opções recomendadas): reverte **só no stop** (não na saída na MM); a reversão é **imediata no preço do stop** mesmo no Próximo candle;
  **vale depois da última entrada** (é do mesmo ciclo); **ignora o Rastrear MM**.
- **Contagem:** `operacoes_por_dia` conta ciclos; cada perna revertida é uma operação no resumo, na tabela (selo "↺n") e no limite de losses.
- **Efeito medido (BD padrão):** 1 reversão: R$ 7.391 → R$ 6.318 (1.817 operações). O sistema antigo já tinha medido que a reversão piora.

## 09/10 — Laboratório de combinações

- **Não existia um motor de testes oficial** (só o script de paridade, a matriz de invariantes e a API, que roda uma combinação por vez). O sistema antigo chamava de "testes internos" scripts avulsos num scratchpad.
  Agora há o laboratório (`strategylab.lab`), documentado em [laboratorio.md](laboratorio.md): a IA escreve uma grade (JSON ou `--eixo`), roda em paralelo e reporta uma tabela.
- **Fidelidade por construção:** o laboratório não tem motor próprio; chama `rodar_trades` e as funções de resumo do app. Além disso, cada execução se verifica contra o caminho do app (e contra o número-âncora no BD padrão) e aborta se divergir.
- **Desempenho sem mudar nenhum número:** o motor foi dividido em `preparar_dia` (independente dos parâmetros) e `run_day_prep`; `media_operacao` é memorizada por janela; o BD vira um `Mercado` reaproveitado.
  Resultado: cenário base de ~3,5 s para ~0,16 s por execução, e processos em paralelo (núcleos − 1, prioridade baixa). O app também ficou mais rápido (usa o mesmo `Mercado`).
- **Cache em disco** do BD preparado, indexado pelo conteúdo do CSV e pelo código do motor (se o motor muda, refaz). Resultados e cache ficam fora do git.
- **Campo desconhecido em grade é erro**: `Params` ignora campos extras em silêncio, e um eixo digitado errado não faria nada.

## 09/10 — Etapa 6: controle de cauda e filtros de regime

- **Motivo (medido com dados até 2025):** o critério "meses positivos" selecionava mal; a perda se concentra em poucos dias (34–42% da perda bruta em 20 dias); o resultado cai com volatilidade e tendência relativas
  e a Retorno vinha perdendo força desde 2022. Duas frentes: controlar a cauda e filtrar regime.
- **Cauda:** parar o dia por perda **realizada** em × `media_operacao` (a unidade das demais regras; adapta à volatilidade) e tempo máximo por perna. Escolhi a unidade em × `media_operacao`, e não em R$, por coerência com stop/alvo;
  um limite em R$ é trivial de acrescentar se ele preferir. O limite também barra a reversão (senão a reversão furaria o controle).
- **Filtros de regime** só com dado fechado: do dia (gap de abertura e amplitude de ontem, contra as 20 amplitudes anteriores; sem história = bloqueia, como o Afastamento sem EMA) e da barra (largura das bandas e inclinação da MM, em `i − 1`).
  A largura das bandas atende, como filtro de volatilidade, ao "filtro das bandas" que estava pendente.
- **Rito completo:** campos neutros, simulador independente (inclusive das medidas de regime), unitários de fronteira, look-ahead (futuro destruído, perturbação cirúrgica, controle com espiada) e matriz própria.
  Mutantes sobreviventes encontrados no caminho (base errada da "amplitude de ontem"; `media_operacao` da barra errada no limite) viraram testes.

## 09/10 — Resultado do experimento da Etapa 6 (os controles melhoram o teste?)

Medido só com dados até 2025, em dois folds walk-forward (A: treino 2021–23 → teste 2024; B: treino 2021–24 → teste 2025). Scripts em `lab_grades/` (`gerar_walkforward_regime`, `analisar_regime`, `gerar_pareado`, `analisar_pareado`).

- **Experimento randomizado** (8.000 combinações, cada controle ligado ao acaso): na combinação **média**, parar o dia por perda ajudou nos dois folds (mediana do teste −R$ 300 contra −R$ 436 em 2024; −R$ 448 contra −R$ 573 em 2025),
  a inclinação da MM ajudou nos dois (significativa em 2025), o gap só em 2025, a largura das bandas **mudou de sinal** entre os folds e o tempo máximo não fez diferença. Todos continuam com mediana negativa: o efeito é de **reduzir exposição**.
- **Escolher as 20 melhores num espaço maior** (com os controles novos) **não** deu teste melhor que antes (A: −R$ 84, 45% positivas; B: +R$ 244, 70%), contra +R$ 216 / +R$ 555 sem os controles: mais graus de liberdade, mais sorte.
- **Teste pareado** (as 32 candidatas de cada fold, escolhidas só pelo treino, com e sem cada controle): **parar o dia por perda é neutro** (mediana 0, média ≈ 0 a +50) e os **filtros de regime pioram o teste** (gap, volatilidade de ontem, bandas, inclinação: −R$ 70 a −R$ 275 de mediana).
  Contra o nulo de remover a mesma fração de operações **ao acaso**, os filtros ficam **abaixo do acaso**: tiram operações melhores que a média. As candidatas rendem **mais** com volatilidade alta (largura das bandas, nas 4 janelas).
- **Lado oposto** (operar só com bandas largas, `filtro_bb_largura_min_pct`): a qualidade por operação melhora um pouco acima do acaso, mas o volume cai tanto (×0,2 a ×0,9) que o R$ líquido do teste também cai.
- **Conclusão:** estes filtros não acrescentam vantagem robusta; ficam disponíveis (documentados, testados), mas **não** entram nas 10 estratégias. A falha provável não é "volatilidade demais": o caminho com mais chance é **diversificar a família de sinal** (modo a favor da tendência) e montar a cesta por contribuição marginal.

## 09/10 — Análise da `ghostcandle_v6_10min` (sistema antigo)

Pedido: entender a campeã antiga para criar algo novo (não reproduzi-la). Detalhes e números em [analise_v6_antiga.md](analise_v6_antiga.md); scripts em `lab_grades/v6_antiga/` (motor antigo só leitura, só dados até 2025).

- A v6 reproduz exatamente (R$ 20.051 / DD −1.717 / 1.644 ops), mas é **um pico**: 100 vizinhos sorteados têm mediana de R$ 7,6 mil e Ret/DD 1,9 (a família tem vantagem real e modesta, 90% positivos).
- Peça mais forte: o **veto de formação** de 3 barras (sem ele R$ 8,8 mil), porém instável por ano (ajuda 3 de 5) e com pico em n = 3. **Trailing não ajuda** nos vizinhos; a **reversão** só pagou em 2025; operar a favor da tendência nas entradas vetadas dá zero.
- A vantagem por operação caiu de R$ 31 (2021) para R$ 6 (2025); em 2025 a 1ª perna ficou em zero. 89% do lucro entra entre 09:00 e 10:59.
- Nada foi implementado no motor: a decisão de trazer o veto de formação (ou outro caminho de `analise_v6_antiga.md` §5) fica com o Ricardo.

## 14/10 — Candle discrepante e trailing stop (portes do sistema antigo)

- **Filtro "não op. se media_operacao > X pontos" removido** (valor fixo em pontos envelhece com a escala do mercado). No lugar entrou o **candle discrepante** (`malibu_vol_discard_mult` do sistema antigo): o maior candle da janela da media_operacao
  sai da média se for > X × o 2º maior. Validado trade a trade contra o motor antigo.
- **Trailing stop** (`trailing_inicio_r`, do `ghost_trail_start_r`). Verificação antes de portar: o motor antigo e o simulador independente (`oraculo_ref_simulador.py`) deram trades idênticos em 6 configurações no BD até 2025
  (`lab_grades/v6_antiga/v6_trailing_verifica.py`). Regras e decisões em [motor.md](motor.md) ("Trailing stop"). Escolhas nossas, onde o antigo não definia: (1) no Próximo candle o sub-candle da abertura conta para o avanço
  da barra da entrada; (2) saída pelo trailing com perda reverte como qualquer stop (como no antigo); (3) breakeven **não** foi trazido (não foi pedido); (4) rótulo `saida_por = "trailing"` quando o nível protegido era o mais apertado.
- O robô NTSL do sistema antigo não implementa o trailing: a reprodução ao vivo do backtest é suposição (reposicionar o stop na abertura de cada barra).

## 14/10 — Escada de contratos e painel reorganizado

- **Escada de contratos** trazida do sistema antigo (`ghost_escada_*`): regras em [motor.md](motor.md). Validada contra o motor antigo (paridade, inclui contratos e R$) e contra o oráculo independente (contratos e R$ por operação).
  Decisão nossa: com a escada ligada o inicial precisa estar entre o mínimo e o máximo (o antigo cortava em silêncio).
- **Painel:** nova seção **03 Reversão e contratos** com todos os controles de reversão (quantidade, stop e alvo da reversão) mais a escada. Indicadores passou a 04 e Filtros a 05. O resto da seção 02 ficou como estava.

## 20/10 — Meses sem operação e "Correlacionar" (resultado conjunto)

- **Meses sem operação:** o `mensal` agora traz **todos os meses que o BD cobre**; o que não teve operação vem zerado e com `operado: false`, e o gráfico "Resultado por mês" mostra uma barra baixa e cinza com o mesmo tooltip (zerado).
  Os totais não mudam (só entram linhas zeradas). Vale só para meses, não para dias.
- **Correlacionar:** marque quantas estratégias quiser (lista no painel esquerdo, abaixo das estratégias) para somar à **principal** (a selecionada). O servidor (`POST /api/portfolio`, `engine/portfolio.py`) soma, **pregão a pregão, backtests independentes**:
  cada estratégia roda como se estivesse sozinha (limites e custo cheio próprios). Os números do conjunto (drawdown, sequências, melhor/pior dia, mensal) saem das mesmas funções do backtest sobre o diário somado;
  um conjunto de **uma** estratégia é idêntico ao backtest, e dois cenários das âncoras somam as âncoras (R$ 7.391 + (−2.071) = 5.320), em teste.
- **Fidelidade (importante):** o backtest **não** modela netting nem margem compartilhada. Na conta real, uma compra de A e uma venda de B no mesmo ativo se compensam. O conjunto serve para ver complementaridade, não para dimensionar risco da conta.
- **Correlação** exibida: Pearson do R$ diário de cada estratégia contra a principal (A), sobre **todos os pregões do BD** (zero onde não operou); `—` quando indefinida. O painel também compara o drawdown do conjunto com a soma dos drawdowns isolados.
- **Memória:** a lista marcada é lembrada **por estratégia** em `estrategias/_estado.json` (`correlacionar`), inclusive vazia: se desmarcou tudo, na próxima vez a estratégia abre sem correlacionadas. Excluir uma estratégia a remove das listas.
  Cada correlacionada entra com a **versão salva**; a principal usa o rascunho da tela.
- **Identidade visual:** selo (letra A, B, C… — A é sempre a principal) + cor (`--e1…--e6` em `styles/tokens.css`, só tons quentes/neutros; verde/vermelho seguem exclusivos de ganho/perda). A cor nunca é o único sinal.
  Paleta validada por contraste (≥ 3:1 nos dois temas) e por separação sob protanopia/deuteranopia/tritanopia (ΔE ≥ 12). Acima de 6 estratégias as cores repetem (selo tracejado) e a letra segue única. Limite: 12 estratégias no conjunto.
- **Operações do dia no conjunto:** candles compartilhados, entrada na cor/letra da estratégia, saída com contorno da estratégia e preenchimento gain/loss; chips por estratégia filtram gráfico e tabela; a tabela vem em seções por estratégia.
  Indicadores (MM/Bollinger), janela e candle de referência no gráfico são da principal (A).

