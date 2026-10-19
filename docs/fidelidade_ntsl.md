# Fidelidade backtest × NTSL (Profit) — setup "short + stop longo – B"

Registro da avaliação feita em 14–19/10/2026 (dados **só até 2025**; nada de 2026 foi usado). Script: [`scripts/New_winner_B.md`](../scripts/New_winner_B.md). Os scripts de análise ficaram em pasta temporária
(copiam `ghost.py` em memória e mudam uma regra; não alteram o projeto).

## O setup e de onde vem o resultado
`book` = ambas · Rastrear MM · afastamento 2,0 × `media_op` · zona de 1 candle · k 0,3 · stop 2,0 / alvo 0,5 · 1 reversão (stop 3,5 / alvo 2,2) · 2 ciclos · última entrada 11:30 · tempo máximo 240 min.
- Com `book cont`: 105 operações em 4 anos, **R$ 2.325** (DD −200). As 89 entradas originais dão só R$ 219; as **16 pernas de reversão dão R$ 2.106 (91%)**; as 3 maiores somam R$ 1.012.
  Cada 100 pts piores na entrada da reversão custam R$ 320 (≈ 14%). Amostra pequena e setup vindo de busca com várias variantes: não é prova de robustez.
- Com `book ambas` (default salvo em 19/10): 177 operações, 28 reversões, **R$ 3.420**, DD −384.

## Sensibilidades medidas (motor, setup B com `cont`)
| Teste | Resultado |
|---|---|
| Penetração 0 / 1 / 2 / 3 ticks | R$ 2.325 / 2.325 / 2.182 / 2.182 |
| MM com erro de +10 pts | 96% das operações em comum, −3% |
| MM com ruído de σ 25 pts | 95% em comum, −2% |
| Semente da EMA = SMA dos 15 primeiros | idêntico |
| EMA **sem as barras depois de 17:30** | **−34%** (85% em comum): a sessão do gráfico importa |
| EMA período 14 / 16 em vez de 15 | −41% / −10% |

A EMA do motor: α = 2/(N+1), sobre o fechamento das barras de 10 min em série contínua; o BD é do MT5 (série contínua ajustada por rolagem). Diferenças com o Profit vêm de dados (rolagem, sessão, OHLC), não da fórmula.

## Rastrear MM com `book cont`: o motor "consome" a barra
Primeiro cruzamento da barra no lado proibido pelo Rastrear → o motor descarta a barra (mesmo que o outro lado seja alcançado depois). Ao vivo, a ordem do lado permitido já estaria no book.
Simulando a regra "literal ao vivo": B `cont` passa de 105 para 124 operações e de R$ 2.325 para **R$ 1.947** (DD −200 → −456). Outras estratégias salvas com Rastrear + `cont`: "1" igual; "short + stop longo" +28%; "C" −9%.
Com `book ambas` o motor e o script **coincidem** (o primeiro cruzamento define a ordem; o lado proibido arma o recuo), então a divergência não se aplica.

## Ponta de recuo: o motor é otimista
O recuo só existe depois de o código ver o cruzamento (segundos; intervalo mínimo de 10 s entre envios no modo contínuo); o motor tem resolução de 1 min e aceita o fill no minuto do cruzamento.
Teste de latência (recuo só passa a existir 0/1/2 sub-candles depois do cruzamento):

| Estratégia | Motor | Lat. 0 | Lat. 1 | Lat. 2 |
|---|---|---|---|---|
| B `cont` | 2.325 | igual | igual | igual |
| **B `ambas`** | **3.420** (DD −384) | 3.175 | 3.096 | **2.803** (DD −406) |
| B só recuo | 1.149 (DD −906) | 839 | 781 | 488 |
| "2" (recuo) | 9.770 | 9.615 | 9.615 | 9.554 |
| "Retorno alto" (recuo) | 7.477 | 5.945 | 4.965 | 4.444 |

Referência realista do B `ambas`: **R$ 2.800–3.100**, não 3.420. Como o laboratório escolhe por ranking, estratégias que dependem de recuo tendem a estar infladas. Com Rastrear só há uma ordem por barra (não existe o risco de as duas executarem).

## O que aprendemos do NTSL (manual + `base_conhecimento/atualizacao/script_win`)
- Dois modos de execução (manual §11.4): "fechamento do candle" (backtestável) e "quando a condição for satisfeita" (contínuo, só replay). O setup B usa o **contínuo** (decisão do Ricardo: o recuo precisa ver o cruzamento dentro da barra).
- Ordem pendente: no contínuo, reemitir a mesma ordem a cada avaliação (modelo "reconcilia"); `CancelPendingOrders` cancela o que foi enviado até então no fluxo atual (chamar **antes** de enviar a nova).
- Stop: `...ToCoverStop(stop, limite, qtd)`; sem limite o Profit usa 30 ticks nos futuros BMF (manual p. 52). Os scripts v3+ passam folga explícita de 30 ticks + quantidade.
- Reversão: no manual (§11.11) o reprocessamento pós-execução só envia coberturas, mas os scripts v1–v3 (stop em repouso + `LastTradeResult < 0` + ordem a mercado) **funcionaram** para o Ricardo; `ReversePosition` (§15.25) é a alternativa por preço (v4). O script tem `ModoRev` 1/2 para comparar no replay.
- `Time` = hora de abertura da barra (HHMM); `CurrentTime` = hora do sistema, só HHMM (no replay pode não acompanhar o relógio simulado). Não existe função de "hora da posição": guardar na entrada.
- EMA: usar **série** (`mmF := mmF[1] + α·(Close[1] − mmF[1])`), nunca variável escalar (reprocessamento). O código-fonte da `MediaExp` está no editor do Profit (menu abrir > exemplos) para conferir.
- `Round2Fraction(valor)` arredonda ao tick (1 argumento). `ConsoleLog` aceita número concatenado a texto.
- Bugs e lições herdados (`atualizacao/script_win/importante.md`): look-ahead na banda, "abre e fecha na mesma barra", pulo de ordem, OCO do menu anula coberturas, série contínua ≠ contrato real.
- Manual: `base_conhecimento/exemplo/ManualNTSL.pdf` (extrair texto com PyMuPDF; página impressa + 10 = página do PDF).
