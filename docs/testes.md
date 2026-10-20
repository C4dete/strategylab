# Testes: quanto rodar, de acordo com o que foi pedido

Regra de ouro: **o teste acompanha o risco da mudança**. Mudança pequena e sem efeito sobre as regras do motor não precisa da bateria inteira (45 min); mudança na regra de trades precisa.
Nunca se pula o teste que cobre *exatamente* o que mudou; o que se escolhe é quanto do **resto** rodar para provar que nada quebrou.

## Quanto custa cada parte (neste PC; total serial medido: rápida 4 min + lenta 45 min)

| Parte | Tempo | O que protege |
|---|---|---|
| Validação, API, persistência, dados, indicadores (`fronteira`, 118 testes) | **~15 s** | faixas, mensagens, JSON salvo, cache da API, leitura do CSV |
| Bateria rápida inteira (`-m "not lento"`, 469 testes) | **~4 min** | regras do motor em cenários à mão, oráculo independente e look-ahead em dados sintéticos, amostra de 96 combinações |
| Paridade com o motor antigo (`paridade_motor_antigo.py`) | **~1,5 min** | trades idênticos ao sistema antigo em 17 cenários no BD inteiro |
| Oráculo no BD real (7 testes) | ~13 min (estim.) | o mesmo que o sintético, só que em 1.073 pregões reais |
| Golden / âncoras (`test_golden`, ~30 testes) | ~6 min (estim.) | números-âncora (R$ e nº de trades) de cada modo no BD inteiro |
| Look-ahead no BD real + laboratório (4 testes) | ~2 min (estim.) | futuro destruído em dados reais; o laboratório reproduz as âncoras |
| **Produto cartesiano das matrizes** (9.600 + 324 combinações) | **~30 min** (estim.; 8 + 4 pedaços) | "nenhuma combinação de controles quebra"; é a maior fatia da bateria lenta |

Paralelizar ajuda pouco aqui: com vários processos o PC satura em **~2,5×** (1 processo = 9 s, 3 = 15,6 s, 6 = 22,4 s para o mesmo trabalho). O ganho grande está em **escolher o perfil**, não em mais processos.

As linhas "estim." repartem os 45 min seriais na proporção medida em uma rodada paralela (as durações individuais daquela rodada estavam inflacionadas pela concorrência). O `parametro` e o `regra` medidos em paralelo (6 processos, com ruído) deram 21 e 13 min; o `fronteira` deu 15 s.

## Qual perfil para qual pedido

| O que foi pedido | Perfil | Tempo | Por que basta |
|---|---|---|---|
| Só interface: texto, dica, layout, estilo, tema | frontend (lint, `tsc -b`, vitest, build) + conferir no navegador | ~1 min | o backend não mudou |
| Documentação, memória, scripts de pesquisa (`lab_grades/`) | nenhum teste do backend (se usou o laboratório: conferir a linha de **Fidelidade**) | 0 | não alteram o motor |
| **Faixa/limite/padrão de um campo, validação, mensagem de erro** (ex.: mínimo do gatilho 2 → 1) | `fronteira` + 1 teste unitário do valor novo + cenário no oráculo/look-ahead sintéticos + paridade | **~3 min** | a regra de trades é a mesma; só se prova que o valor novo percorre o motor igual ao antigo e ao oráculo |
| Persistência, API, cache, leitura de CSV, formato de JSON | `fronteira` (+ frontend se o tipo mudou) | ~15 s a 1 min | nada de motor |
| **Controle novo ou regra alterada** em `ghost.py` / `fills.py` | `regra --afeta <temas>`: rápida + paridade + **no BD real só os cenários dos temas tocados** + 5 canários (sem o produto cartesiano) | estimado: `zona` ~8 min serial (~3 min com 3 processos), `reversoes,rastrear` ~14 (~6), `todos` ~28 (~11) | a regra mudou: o oráculo e as âncoras reais rodam onde a mudança pode aparecer; o resto do BD real repete o que o sintético já cobre |
| **Mudança estrutural**: `preparar_dia`, `Mercado`, `chave_motor`, `runner`, métricas do motor, cache | `completo` (tudo, inclusive as matrizes inteiras) | ~35 a 45 min | afeta qualquer combinação |
| Fim de etapa / antes de entregar algo grande | `completo` **em segundo plano**, sem bloquear a conversa | | último portão |

Em todos os casos o **teste novo da própria mudança** é obrigatório (unitário; look-ahead se lê indicador/candle; oráculo se couber; entrada na matriz de combinações). Isso é o que dá confiança; o perfil só confere o resto.

### A mudança de 13/10 (mínimo do gatilho = 1) como exemplo
Era "faixa de campo": o motor já calculava a zona por fatia (`h[i-n:i]`), então nada de regra mudou. O suficiente era: teste unitário (1 candle usa só a barra anterior) + cenários de 1 candle no oráculo e no look-ahead sintéticos + paridade com o motor antigo + `fronteira` ≈ **3 a 5 min**. Foi rodada a bateria lenta inteira (45 min) sem necessidade; a decisão certa teria sido o perfil `parametro`.

## Cenários afetados no BD real (`regra --afeta`)

O oráculo no BD real, as âncoras (`test_golden`) e o look-ahead real repetem, em 1.073 pregões, cenários que o sintético já cobre. Por isso o perfil `regra` **exige dizer o que foi tocado**:

| Tema (`--afeta`) | Cenários do BD real que entram |
|---|---|
| `proximo_candle` | os que têm "candle" no nome (próximo candle, combinações com ele) |
| `sair_mm` | "sair na MM", "os dois", combinações |
| `rastrear` | "rastrear MM", combinações |
| `reversoes` | "reversão/reversões", combinações |
| `escada` | "escada" / "contratos" |
| `filtro_afast` | "filtro", e as 3 âncoras do filtro de afastamento |
| `book` · `penetracao` | cenários com "book" / "penetração" |
| `gestao` | ops por dia, stop, alvo, parar por losses |
| `janela` · `zona` | janela, última entrada, gatilho/zona |
| `laboratorio` | teste do laboratório |
| `todos` | **todo** o BD real (sem as matrizes): usar se a mudança é transversal |

Além do tema, **5 canários rodam sempre** (um por camada): âncora do `inicial_default`, "controles novos desligados não mudam o cenário base", paridade `base` com o motor antigo, âncora do laboratório e look-ahead real (filtro, book cont). Se o canário passar e o tema passar, o BD real está coberto para aquela mudança.

Se o tema não está na tabela, use `-k "<expressão do pytest>"` ou `todos`. `--listar` mostra o que rodaria e o tempo estimado, sem executar. O produto cartesiano das matrizes fica **só** no `completo`.

## Como rodar

```bash
python backend/scripts/testes.py --lista                   # perfis
python backend/scripts/testes.py fronteira                 # ~15 s
python backend/scripts/testes.py parametro                 # rápida inteira + paridade
python backend/scripts/testes.py regra --afeta reversoes,rastrear   # BD real só nesses temas + canários
python backend/scripts/testes.py regra --afeta zona --listar         # só mostra o que rodaria e o tempo
python backend/scripts/testes.py regra --afeta todos                  # todo o BD real, sem matrizes
python backend/scripts/testes.py completo                  # tudo
python backend/scripts/testes.py parametro -k "zona"          # só o que casa com a expressão do pytest (sem paridade)
python -m pytest backend -m "not lento" -k "gatilho or zona"   # direto no pytest, para o teste da própria mudança
```

Os logs de cada processo ficam em `lab_cache/_testes/`. Os pesos usados para dividir o trabalho estão em `PESOS` no script (atualize se um teste ficar bem mais pesado).

## Regras de conduta (para o agente)

1. **Antes de rodar algo longo, diga qual perfil e quanto vai demorar.** Nada acima de ~10 min sem avisar; nada que dispare "para ver" (foi o erro de 13/10: medir o suite inteiro três vezes em vez de responder).
2. Comece sempre pelo teste da própria mudança (`-k`), depois o perfil. Se o primeiro falha, não gaste o resto.
3. Bateria longa (`regra`/`completo`) roda **em segundo plano** e a conversa segue; se o pedido não precisa dela, não rode.
4. Não rode duas baterias ao mesmo tempo (a concorrência multiplica a duração e distorce a medição; ver abaixo).
5. Se a mudança tocar mais de uma categoria da tabela, vale o perfil **mais pesado** entre elas.
6. Não encurte um teste por "parecer demais": se um teste custa caro e só repete outro, a decisão de cortá-lo é do Ricardo (propor aqui e documentar).

## Observações técnicas (para não repetir)

- Pipe cheio trava o processo filho: o executor em paralelo grava a saída de cada processo **em arquivo** (`lab_cache/_testes/`), nunca em `PIPE` lido depois.
- `PYTHONIOENCODING=utf-8` nos filhos (os acentos de "TODOS IDÊNTICOS" quebravam a comparação no Windows).
- Duas baterias ao mesmo tempo no PC deixaram testes de 9 s com 170 s: as medições "rápidas" com processos antigos vivos ficaram inválidas. Sempre confirme que não sobrou processo (`Get-Process python*`).
- Corte aplicado em 13/10 (decisão do Ricardo): oráculo/âncoras/look-ahead no BD real rodam só nos cenários afetados (+ canários) fora do `completo`. O `completo` continua rodando tudo antes de entregas grandes.

## Portão automático (git) e conjunto

- **Hooks versionados** em `.githooks/` (ativar uma vez por clone: `git config core.hooksPath .githooks`):
  - `pre-commit`: **trava de hold-out/segredos** (recusa `dados/`, `base_conhecimento/`, `*.csv`, `*.pkl`, `WINM26*`, `.env`); se o backend mudou, roda `testes.py fronteira` (~20 s de testes, ~45 s com a partida); se o frontend mudou, lint + `tsc -b` + vitest (~17 s).
  - `pre-push`: só se o **motor** (`backend/strategylab/engine/`) mudou, roda `testes.py parametro` (~5 min).
  - Contorno consciente (só quando o Ricardo pedir): `--no-verify`.
- **Conjunto ("Correlacionar")** — `backend/tests/test_portfolio.py`: um componente ≡ backtest; soma de R$/ops/dias; `rs_por` soma o dia e o mês; drawdown do conjunto recalculado de forma independente; correlação (consigo = 1, constante = nula, simétrica);
  ordem das não-principais não muda os totais; resultado de entrada não é mutado (o cache da API guarda esses dicionários); API (formato, limites 1–12, memória da seleção, exclusão); BD real (lento): dois cenários das âncoras somam as âncoras. Este último é **canário** do perfil `regra`.
- **Perfil usado** quando só a montagem do resultado muda (o motor de trades, não): `regra --afeta laboratorio` (~4 min no relógio) + testes novos; sem `completo`. Prova de que o motor não mudou: `git diff` vazio em `ghost.py`, `fills.py`, `params.py`.
- **Interface:** sem teste de componente (não há testing-library); a lógica pura vai para o vitest (`identidade.test.ts`) e o resto é conferido no navegador (claro/escuro, 375/768/1440, teclado, console). Uma instância isolada de verificação (`strategylab-verif`, porta 8766, em `.claude/launch.json`) evita mexer no servidor do Ricardo.
  Antes de clicar no Correlacionar durante a verificação, faça backup de `estrategias/_estado.json` (a seleção grava ali) e restaure no fim.

### Próximos passos (não feitos)
Cenários-ouro conferidos pelo Ricardo (fichas em `lab_resultados/ouro_fichas/`), testes de propriedade (hypothesis), mutação periódica (mutmut), Playwright (3 fluxos) e diff de trades nas âncoras.

