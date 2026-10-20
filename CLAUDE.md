# StrategyLab — guia para o agente

Laboratório local de backtest do **WIN**. Leia o [README](README.md) (como rodar, estrutura) e [docs/motor.md](docs/motor.md) (regras).

## REGRA INVIOLÁVEL: hold-out do Ricardo (2026)

- **Dados depois de 2025-12-31 são a validação final do Ricardo e NUNCA podem ser usados, lidos, procurados ou inferidos.** Só o BD do projeto (`dados/WIN_1M_21_25.csv`, até 2025-12-30).
- Não procure CSVs fora da pasta do projeto, não abra arquivos tipo `WIN_1M_completo*`, não rode nada contra um BD que passe de 2025. Se ele mostrar prints/resultados de 2026, trate só como relato dele; **não ajuste nada em cima disso**.
- **Cuidado com o servidor do app:** o BD ativo pode ser um arquivo que o Ricardo carregou (com 2026). **Nunca use `/api/backtest` ou `/api/dia` para conferir números sem antes checar `/api/dataset`** (`padrao: true` e `fim` ≤ 2025-12-31); na dúvida, confira só pelo laboratório.
- Os docs/chat antigos citam resultados de 2026 de OUTRAS estratégias: ignore-os. Não abra `base_conhecimento/chat/chat_ia.md` nem `base_conhecimento/atualizacao/exemplo/WINM26*`.
- Trava técnica: `strategylab.paths.DATA_LIMITE_PESQUISA` + `lab/executor.py::carregar_bd` recusam CSV com datas posteriores. Não remova nem contorne. Permissões em `.claude/settings.json` negam a leitura desses arquivos.

## Princípios

- **Honestidade do backtest acima de tudo**: só vale o que é reprodutível ao vivo. Sem look-ahead, custo cheio a mercado, stop primeiro,
  fila no book (penetração). Se um resultado parece bom demais, procure o artefato antes de comemorar.
- **Implemente só o que foi pedido.** O Ricardo libera parâmetros por etapa; recursos do v6 não pedidos (trailing, filtro3...)
  ficam de fora, e o resultado diferente do v6 completo é esperado.
- **Look-ahead é a regra nº 1.** Indicadores devolvem o valor NO FECHAMENTO de cada barra e não são deslocados; quem decide na barra `i` lê `i − 1`
  explicitamente. Toda regra nova que leia indicador ou candle ganha: teste unitário com `mm` fabricada (só `i − 1` decide), entrada em
  `test_sem_lookahead.py` (futuro destruído) e, se possível, uma versão no simulador independente (`oraculo_ref_simulador.py`).
- **Todo controle novo passa pela rotina de combinações.** Adicione-o às `DIMENSOES` de `backend/tests/test_combinacoes.py` (invariantes valem para qualquer mistura de
  controles) e, se a regra couber no simulador independente, em `oraculo_ref_simulador.py` + `test_modos_vs_oraculo.py`. O Ricardo testa combinações no painel: nenhuma pode quebrar.
- **Combinações pedidas pelo Ricardo → laboratório** (`python -m strategylab.lab`, ver [docs/laboratorio.md](docs/laboratorio.md)): escreva a grade em `lab_grades/`, rode, confira a linha de
  **Fidelidade** e reporte R$, DD, Ret/DD, IS × OOS (platô, não pico). O laboratório usa o motor do app (nenhum motor paralelo): nunca reimplemente a lógica de trades fora de `engine/`.
- **Quanto testar depende do pedido** ([docs/testes.md](docs/testes.md)): só interface/doc/pesquisa não pede bateria de backend; faixa/limite/validação de campo = `python backend/scripts/testes.py parametro` (minutos);
  regra nova no motor = `regra --afeta <temas>` (BD real só nos cenários afetados + canários); mudança estrutural = `completo` (45 min, em segundo plano). **Diga o perfil e o tempo ANTES de rodar; nada acima de ~10 min sem avisar.** O teste novo da própria mudança é sempre obrigatório.
- **Reprodução em NTSL (Profit):** o que o Ricardo testa tem de ser reproduzível em NTSL. Scripts em [`scripts/`](scripts/) (hoje `New_winner_B.md`, setup "short + stop longo – B", modo contínuo); fidelidade, divergências e números de referência em
  [docs/fidelidade_ntsl.md](docs/fidelidade_ntsl.md). Ao escrever/alterar script, consulte `base_conhecimento/atualizacao/script_win/` (v1–v4, `importante.md`, `new_ghost_v2_15min.md`) e o manual `base_conhecimento/exemplo/ManualNTSL.pdf`, e
  **confira como os scripts do Ricardo realmente funcionaram antes de afirmar limitação da plataforma**. Mudou uma regra que afeta uma estratégia com script? Atualize o script e o mapa dele. NTSL não compila aqui: marque o que depende do replay.
- **Fidelidade do backtest:** `book recuo`/`ambas` dependem de o recuo existir no minuto do cruzamento (o motor é otimista: trate o resultado como limite superior; teste de latência em `docs/fidelidade_ntsl.md`). Rastrear MM com `cont` descarta a barra
  se o 1º cruzamento é do lado proibido (diverge do ao vivo).
- **Mexeu no motor? Rode a paridade.** `python backend/scripts/paridade_motor_antigo.py` precisa terminar em "TODOS IDÊNTICOS" e
  `python -m pytest backend` passar (os números-âncora estão em `backend/tests/test_golden.py`).
- `base_conhecimento/` é só leitura (sistema antigo + docs). Não edite; consulte `docs/` dela para o histórico de pesquisa.

## Convenções

- Idioma: **português do Brasil** em interface, mensagens de erro, docs e comentários. Identificadores de domínio em português
  (`estrategias`, `operacoes`, `bracket_fracao`); nomes técnicos genéricos em inglês só onde o ecossistema pede (`engine`, `fills`).
- Números/datas pt-BR na interface (`frontend/src/lib/format.ts`; datas ISO nunca passam por `Date`).
- Novo parâmetro de estratégia = campo novo em `engine/params.py::Params` **com padrão neutro** + faixa em `/api/meta` + campo no
  `ControlPanel` + linha em `docs/motor.md` + teste. Arquivos JSON antigos têm de continuar válidos.
- Frontend: CSS próprio sobre os tokens de `styles/tokens.css` (sem biblioteca de componentes, sem azul/roxo, cantos de 2 px);
  animações só `transform/opacity` e respeitando `prefers-reduced-motion`. Estado de servidor com TanStack Query;
  regras de rascunho/execução ficam em `hooks/useWorkspace.ts`.
- Dados do usuário (`estrategias/*.json`, `dados/`) **não** vão para testes: os testes usam `tmp_path` e CSV sintético.
- **Estratégias no conjunto (Correlacionar):** identidade = selo (letra A, B, C…; A é a principal) + cor `--e1…--e6` (`styles/tokens.css`, só tons quentes/neutros). **Verde/vermelho são só para ganho/perda**; a cor nunca é o único sinal.
  O conjunto é soma de backtests independentes (sem netting). Verificação no navegador: use a instância isolada `strategylab-verif` (porta 8766) e **restaure `estrategias/_estado.json`** depois (a seleção do Correlacionar grava nele).

## Verificação antes de dizer "pronto"

(Escolha o perfil pela tabela de [docs/testes.md](docs/testes.md); a lista abaixo é o máximo, não o mínimo.)

`python -m pytest backend -m "not lento"` · `npm --prefix frontend run lint` · `(cd frontend && npx tsc -b)` · `npm --prefix frontend test` ·
`npm --prefix frontend run build` e, para mudanças de interface, abrir `http://127.0.0.1:8765` (config `strategylab` em `.claude/launch.json`)
e conferir no navegador: console sem erros, tema claro/escuro, 375 / 768 / 1440 px.
