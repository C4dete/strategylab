# StrategyLab

Laboratório local para testar estratégias intraday do **WIN** (mini índice) com backtest honesto e reprodutível.
Reescrita do sistema antigo (`base_conhecimento/`, Streamlit): **um único painel de controle para todas as estratégias**,
estratégias **salvas em disco**, BD padrão já carregado.

> **Etapa 6** (atual): + **controle de cauda** (parar o dia por perda, tempo máximo na posição) e **filtros de regime** (gap, volatilidade de ontem, largura das Bandas de Bollinger, inclinação da MM).
> **Etapa 5**: + **Reversões** (stop-and-reverse, até 5, com stop e alvo próprios), idênticas ao motor antigo.
> **Etapa 4**: + **Rastrear MM** (acima da MM só vendas, abaixo só compras) e testes explícitos de que a saída na MM não exclui stop/alvo.
> **Etapa 3**: + **Modo de entrada** (Padrão ou Próximo candle) e **Sair ao tocar a MM**, ambos sem look-ahead e testados em todas as combinações com os outros controles.
> **Etapa 2**: Indicadores (MM e Bandas de Bollinger, EMA) e o filtro **Afastamento da MM**, sem look-ahead.
> **Etapa 1**: motor `ghostcandle_v6_10min` com os 12 parâmetros do painel. Trailing, freio de formação,
> amplitude mínima da zona e demais recursos do v6 **não** estão implementados — por isso o resultado é diferente do v6 completo
> (ver [docs/motor.md](docs/motor.md)).

## Como rodar

```bash
pip install -r backend/requirements.txt      # uma vez
iniciar.bat                                    # abre http://127.0.0.1:8765  (encerrar.bat para parar)
```

Na primeira execução o `iniciar.bat` compila a interface (precisa de Node/npm). O BD padrão (`dados/WIN_1M_21_25.csv`,
594 mil candles de 1 min) leva ~6 s para carregar; o backtest completo leva ~4 s.

### Desenvolvimento

```bash
python -m uvicorn strategylab.main:create_app --factory --app-dir backend --port 8765 --reload   # API
npm --prefix frontend run dev                                                                    # interface com HMR em :5173
```

### Testes

Para não rodar a bateria inteira à toa, escolha o perfil pelo tipo de mudança: [docs/testes.md](docs/testes.md) (`python backend/scripts/testes.py fronteira|parametro|regra|completo`).

```bash
python -m pytest backend -m "not lento"      # ~3,5 min (462 testes): motor (casos sintéticos), indicadores, look-ahead, simulador independente (sintético),
                                              #         amostra de 96 combinações dos controles, dados, métricas, estratégias, API
python -m pytest backend                      # + números-âncora no BD inteiro, simulador independente e look-ahead no BD real,
                                              #   as 9.600 combinações dos controles (532 testes, ~35 min)
python backend/scripts/paridade_motor_antigo.py   # motor novo × motor antigo, trade a trade, 12 cenários
npm --prefix frontend run lint && npm --prefix frontend test && (cd frontend && npx tsc -b)
```

### Laboratório de combinações

```bash
lab.bat lab_grades\exemplo.json            # roda uma grade de parâmetros (produto de opções) em paralelo, no MESMO motor do app
```

Pede-se a combinação, a IA escreve a grade e roda; sai uma tabela (R$, DD, Ret/DD, IS × OOS...) em `lab_resultados/`. Cada execução se auto-verifica
contra o caminho do app. Detalhes em [docs/laboratorio.md](docs/laboratorio.md).

## Estrutura

```
backend/strategylab/
  lab/        grade.py · executor.py (paralelo + verificação) · metricas.py · relatorio.py · cli.py   (laboratório de combinações)
  engine/     params.py (campos + perfil fixo) · ghost.py (motor) · indicators.py (EMA, Bollinger) · fills.py · data.py · metrics.py · runner.py
  services/   strategies.py (JSON em estrategias/) · dataset.py (BD ativo, cache de resultados)
  api/        routes.py · schemas.py          main.py (FastAPI + serve frontend/dist)
frontend/src/ features/{strategies,dataset,results,day} · components/ui · hooks · lib · styles
dados/        BD padrão
estrategias/  uma estratégia = um .json (+ _estado.json); é aqui que "salvar" realmente grava
scripts/      scripts NTSL (Profit) das estratégias salvas; hoje: New_winner_B.md (setup "short + stop longo - B", modo contínuo, não compilado: validar no replay)
docs/         motor.md (regras e parâmetros) · laboratorio.md (grades de combinações) · decisoes.md (por que é assim)
lab_grades/   grades (JSON) do laboratório · lab_resultados/ e lab_cache/ (gerados, fora do git)
base_conhecimento/   o sistema antigo e sua documentação — só leitura, referência
```

## Estratégias

Cada estratégia é `estrategias/<id>.json` (`schema`, `id`, `name`, `params`). O `id` nasce do nome e **não muda ao renomear**.
A `inicial_default` é criada na primeira execução e pode ser renomeada ou excluída (não volta). Campos ausentes assumem o
padrão, então novos parâmetros nas próximas etapas não quebram arquivos antigos.

## BD

Formato (o mesmo do padrão): `CANDLE;OPEN;HIGH;LOW;CLOSE;VFIN;VNEG`, separador `;`, data `dd/mm/aaaa hh:mm`. Recomendado: candles de
**1 minuto** (o motor lê a ordem dos eventos dentro de cada barra de 10 min). Aceita 2 e 5 min com aviso. **Selecionar outro BD**
vale só até recarregar a página — ao abrir, o sistema volta ao padrão.
