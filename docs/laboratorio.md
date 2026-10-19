# Laboratório de combinações

Roda **grades de parâmetros** (produto de várias opções do painel) no **mesmo motor do app**, em paralelo, e devolve uma tabela com
resultado, drawdown, Ret/DD, win rate, IS × OOS etc. É o que a IA usa quando o Ricardo pede "teste estas combinações".
Código: `backend/strategylab/lab/`. Atalho: `lab.bat` (Windows) ou `python -m strategylab.lab` com `PYTHONPATH=backend`.

> **Regra de ouro: o laboratório não tem motor próprio.** Cada combinação passa por `engine.runner.rodar_trades` e por
> `resumo_diario`/`metricas_globais` — as mesmas funções do botão "Executar backtest". Se o app mostra R$ X para uma estratégia,
> a grade mostra R$ X para a mesma estratégia. Ver "Fidelidade" abaixo.

## Como usar

```bash
lab.bat lab_grades\exemplo.json                                   # roda uma grade descrita em JSON
lab.bat --eixo reversoes=0,1,2 --eixo book=cont,ambas --nome teste  # grade rápida na linha de comando
lab.bat lab_grades\exemplo.json --dry-run                          # só conta as combinações e estima o tempo
```

Opções: `--workers N` (padrão: núcleos − 1) · `--saida PASTA` (padrão `lab_resultados/`) · `--top N` · `--ordenar-por COLUNA` ·
`--corte-oos AAAA-MM-DD` · `--min-operacoes N` · `--bd ARQUIVO.csv` · `--trades N` (grava os trades das N melhores) ·
`--verificar K` (padrão 3; 0 desliga) · `--cache-dir PASTA`. Códigos de saída: 0 ok · 2 grade inválida · 3 **falha de fidelidade**.

### Formato da grade (JSON)

```json
{
  "nome": "reversoes x stop",
  "base": "inicial_default",
  "variantes": [{}, {"sair_ao_tocar_mm": true}],
  "eixos": {
    "reversoes": [0, 1, 2],
    "stop_x_media": {"de": 0.5, "ate": 2.0, "passo": 0.25},
    "book": ["cont", "ambas"]
  },
  "corte_oos": "2025-01-01",
  "janelas": {"trainA": ["2021-09-01", "2023-12-31"], "testA": ["2024-01-01", "2024-12-31"]},
  "ordenar_por": "ret_dd",
  "top": 20,
  "min_operacoes": 30
}
```

- **`base`**: estratégia salva (id ou nome, de `estrategias/`) ou um objeto `{campo: valor}`. Omitido = os padrões de `Params`.
- **`eixos`**: produto cartesiano. Cada eixo é uma lista de valores ou `{"de", "ate", "passo"}` (sem deriva de ponto flutuante).
- **`variantes`**: cenários explícitos (blocos de campos fixos). As combinações são **cada variante × produto dos eixos**.
  Um campo não pode estar em `eixos` e numa variante ao mesmo tempo.
- Os nomes são os campos de `Params` (tabela em [motor.md](motor.md); inclui os da Etapa 6: `parar_dia_perda_x_media`, `tempo_max_min`, `filtro_gap_ativo`, `filtro_gap_max_x_media`, `filtro_vol_ontem_ativo`, `filtro_vol_ontem_max`, `filtro_bb_ativo`, `filtro_bb_largura_min_pct`, `filtro_bb_largura_max_pct`, `filtro_inclinacao_ativo`, `filtro_inclinacao_barras`, `filtro_inclinacao_max_x_media`, `filtro_candle_discrepante_ativo`, `filtro_candle_discrepante_x`, `trailing_inicio_r`, `escada_contratos`, `escada_ganho_acao`, `escada_ganho_qtd`, `escada_perda_acao`, `escada_perda_qtd`, `escada_min`, `escada_max`): `janela_inicio`, `candles_gatilho`, `bracket_fracao`,
  `modo_entrada`, `reversoes`, `rev_stop_x_media`, `rev_alvo_x_media`, `book`, `penetracao_ticks`, `parar_apos_losses`,
  `contagem_losses`, `operacoes_por_dia`, `stop_x_media`, `alvo_x_media`, `mm_periodo`, `filtro_afast_mm_ativo`,
  `filtro_afast_mm_x_media`, `rastrear_mm`, `sair_ao_tocar_mm`, etc. **Campo desconhecido é erro** (o app ignoraria em silêncio).
  Todo campo novo de `Params` já vira eixo possível, sem mexer no laboratório.
- Combinações **inválidas** (ex.: última entrada antes do início, reversões > 5) são listadas e puladas; não derrubam a grade.
- **`corte_oos`**: IS = antes da data, OOS = a partir dela (padrão `2025-01-01`; `null` desliga).
- **`janelas`**: janelas de tempo nomeadas `{nome: [inicio, fim]}` (inclusive). Geram colunas `<nome>_total_rs`, `_dd_rs`, `_ret_dd`, `_operacoes`, `_meses_pos`, `_pior_mes`... na MESMA rodada. É a base da busca walk-forward: escolher usando só o treino e medir no teste. Como cada pregão é independente e a EMA só usa o passado, o resultado de uma janela não depende do que vem depois (há teste que destrói os dados após a janela). O CSV também traz o resultado de cada mês (`m_AAAA-MM`).

### O que sai (pasta `lab_resultados/AAAAMMDD-HHMMSS_nome/`)

| Arquivo | Conteúdo |
|---|---|
| `resumo.md` | cabeçalho (BD, combinações, tempo, **fidelidade**), diagnósticos, top N e pior 5 |
| `resultados.csv` | uma linha por combinação, com TODAS as métricas (separador `;`, decimal `,`, UTF-8: abre direto no Excel pt-BR) |
| `grade.json` | a grade que gerou o resultado (reprodutível) |
| `trades_<id>.csv` | trades das N melhores (com `--trades N`) |

Colunas: as variáveis da grade (valor **efetivo**, base + variável) e `operacoes` (pernas), `ciclos`, `pregoes`, `total_rs`, `total_pts`,
`dd_rs` (maior queda da curva diária), `dd_pregoes`, `ret_dd` (= total ÷ |DD|), `win_rate`, `ganhos`, `perdas`, `zeradas`, `melhor_dia`,
`pior_dia`, `soma_20_piores` (soma dos 20 piores dias), `meses_pos_pct`, `anos_pos`/`anos`, `is_rs`, `oos_rs`, `oos_dd`, `oos_ret_dd`,
`oos_operacoes`, `rs_<ano>` e `motor_unico` (combinações com o mesmo número aqui tiveram o mesmo motor calculado uma vez).

## Fidelidade (por que o número da grade é o do app)

1. **Mesmo código:** `rodar_trades` + `metricas` (que chama `resumo_diario`/`metricas_globais`). Nada é reimplementado.
2. **Preparo único, sem mudar contas:** o motor separa o que depende dos parâmetros (`run_day_prep`) do que não depende (`preparar_dia`: vetores
   dos pregões e dos sub-candles) e da memória de `media_operacao` por janela. O `Mercado` (pregões preparados + EMAs por período em cache) é feito
   uma vez por BD. O app usa o mesmo `Mercado`. Testes provam que o caminho preparado dá **os mesmos trades** do caminho por DataFrame
   e que reaproveitar o `Mercado` entre execuções (inclusive com janelas e períodos de MM diferentes) não vaza estado.
3. **Deduplicação por `chave_motor`:** combinações que diferem só em algo que não muda o resultado (ex.: período de Bollinger) são calculadas uma vez.
4. **Verificação automática a cada execução** (`--verificar`, padrão 3): K combinações da grade são recalculadas pelo **caminho do app**
   (`executar`, com um `Mercado` novo feito do CSV, sem cache em disco e sem processos) e comparadas (operações, R$, pontos, DD, win rate).
   Se o BD é o padrão do projeto, o cenário base também precisa dar o número-âncora (1.054 operações / R$ 7.391). Divergência = a execução **aborta com código 3**.
5. **Testes** (`backend/tests/test_lab.py`): grade, métricas = app, preparado = DataFrame, sem vazamento de estado, cache invalidado quando o código do motor muda,
   paralelo = serial = app, verificação detecta adulteração, CLI de ponta a ponta e, no BD real, os números-âncora (`pytest -m lento`).
   O motor em si continua coberto pela paridade com o motor antigo, pelo simulador independente e pelos testes de look-ahead.

## Desempenho (medido nesta máquina: 8 núcleos)

| | por combinação |
|---|---|
| antes do preparo único (`rodar_trades` relendo as barras) | ≈ 3,5 s (cenário base) |
| agora, cenário base | **≈ 0,16 s** |
| agora, tudo ligado (reversões, MM, filtro, Próximo candle, 3 operações/dia) | ≈ 0,8 s |

Grade de 210 combinações (com reversões): **32 s** com 7 processos (≈ 6,5 motores/s; estimado em ~4 min no serial e ~12 min antes do preparo único).
A primeira execução num BD novo gasta ~12 s preparando o cache (`lab_cache/`); depois ele é lido em ~0,1 s. O cache é indexado pelo conteúdo do CSV **e** pelo código do
motor: mexeu no motor, o cache se refaz sozinho. Os processos rodam com prioridade abaixo do normal: o computador continua utilizável.
Para grades muito grandes, rode `--dry-run` antes (estima o tempo) e avise o Ricardo da duração.

## Protocolo para a IA (metodologia dos "testes internos", adaptada)

Quando o Ricardo pedir combinações:

1. **Declare a grade e conte as variantes** antes de rodar (e o limiar de Bonferroni 5% ÷ nº de combinações, que o `resumo.md` já traz).
2. Escreva o JSON em `lab_grades/` (ou use `--eixo`), rode, e **confira a linha "Fidelidade"** do resumo. Sem "OK", o resultado não vale.
3. Reporte sempre: **R$, DD, Ret/DD, win rate, nº de operações, IS e OOS** (não só o total) e quantas combinações têm OOS positivo. Procure **platô, não pico**: um valor bom
   cercado de vizinhos ruins é ruído. Compare com a base (a combinação sem as mudanças) e escale a comparação por Ret/DD, não pelo total.
4. **Selecione como o experimento walk-forward mostrou que funciona.** Em 8.000 combinações (treino 2021–23 → teste 2024 e treino 2021–24 → teste 2025), só ~30% das combinações elegíveis (≥150 operações) ganham no teste e a mediana é negativa. Escolher pelas 20 melhores do treino por **Ret/DD** ou por **Sharpe mensal** deu teste positivo nos dois folds (65–70% das escolhidas com lucro, R$ mediano +216 a +554) e superou o sorteio com p < 0,01; **meses positivos** foi instável (+299 num fold, +13 no outro), **total em R$** perdeu no fold A e um **composto de ranks** foi o pior (escolhe quem opera demais). O ritmo no teste fica em ~30–50% do ritmo do treino: espere isso. Não ranqueie só por meses positivos nem por total.
5. **Platô e cesta:** exigir platô (mediana da vizinhança, um parâmetro por vez) melhorou a escolha num fold (80% das 10 melhores ganharam no teste contra 70%) e ficou igual ao sorteio entre as candidatas no outro: ajuda pouco, porque o filtro de treino (Ret/DD ou Sharpe mensal) já faz a maior parte do trabalho. Já uma **cesta** das 10 melhores somadas deu 8 de 12 meses positivos nos dois anos de teste e pior mês, por estratégia, ~3x menor que o das individuais. Prefira reportar e operar um conjunto diverso a apostar numa única configuração.
6. **Controles novos pedem teste pareado, não só ranking.** Na Etapa 6, comparar ligado x desligado em combinações sorteadas sugeriu ganho; o teste **pareado** nas candidatas já escolhidas pelo treino (mesma candidata com e sem o controle, contra o nulo de remover operações ao acaso) mostrou que os filtros de regime pioram o teste. Sempre rode o pareado antes de acreditar que um filtro ajuda.
7. **Honestidade:** não promova nada ao projeto por causa de uma grade; resultado bom demais pede busca do artefato (look-ahead, imunidade, fila). Correlação de postos IS × OOS ≈ 0
   significa que escolher a melhor célula do IS não prevê o OOS.
8. **Não altere o projeto** (`Params`, estratégias salvas, motor) ao testar. Para salvar uma combinação como estratégia, só se o Ricardo pedir.
9. Se o Ricardo pediu uma combinação que o motor não expõe, **pergunte**: o laboratório só varre campos de `Params`.

## Scripts de pesquisa (`lab_grades/`)

Geradores e análises usados nas buscas (cada um tem a explicação no cabeçalho): `gerar_busca_meses.py` / `gerar_refino.py` (busca por meses positivos), `gerar_walkforward.py` + `analisar_walkforward.py`
(compara critérios de seleção treino → teste), `gerar_plato.py` + `analisar_plato.py` (vizinhança/platô), `gerar_final.py` (seleção final, treino 2021–2025), `gerar_walkforward_regime.py` + `analisar_regime.py`
(experimento randomizado dos controles da Etapa 6), `gerar_pareado.py` + `analisar_pareado.py` (teste pareado: mesma candidata com e sem o controle). Os `.json` gerados ficam ao lado; resultados em `lab_resultados/` (fora do git).
`lab_grades/v6_antiga/` roda o motor ANTIGO (somente leitura, dados até 2025) para a análise da v6: ver [analise_v6_antiga.md](analise_v6_antiga.md).
Caminhos temporários (`lab_cache/_*.csv|json|log`) são rascunho. Atenção no Windows: `/tmp` do bash e do Python são pastas diferentes; use `lab_cache/` ou a pasta de rascunho.

## Trava do hold-out (2026)

`carregar_bd` recusa (`BDAlemDoLimite`, mensagem em português) qualquer CSV com datas depois de `paths.DATA_LIMITE_PESQUISA` (2025-12-31), olhando só os anos das datas, sem interpretar valores. Não há opção para desligar. O motivo é metodológico: o 2026 é a validação final do Ricardo; usar esses dados em pesquisa o torna viciado. O servidor do app, em compensação, aceita qualquer BD (é a ferramenta dele): por isso as conferências da pesquisa nunca usam a API sem checar que o BD ativo é o padrão.

## Limites

- Só varre os campos expostos em `Params` (execução WIN, custos e timeframe são fixos; ver [motor.md](motor.md)).
- Um BD por execução (`--bd`/`"bd"`); o BD precisa estar no formato do app.
- Resultados sob demanda: nada fica salvo no app (as grades ficam em `lab_resultados/`, fora do git).
