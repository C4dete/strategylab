# Análise da `ghostcandle_v6_10min` (sistema antigo)

Objetivo: entender de onde vem o resultado da estratégia campeã do sistema antigo para **criar algo novo e melhor**, não para reproduzi-la.
Tudo foi medido com o motor antigo (`base_conhecimento/`, só leitura) rodando **apenas nos dados do projeto (até 2025‑12‑30)**.
A base reproduz o número documentado exatamente: **R$ 20.051 · DD −1.717 · 1.644 operações · 36/52 meses positivos · 3.494 / 7.928 / 3.527 / 2.603 / 2.499 por ano**
(1 contrato, custo 5/5/5, penetração 1 tick). Scripts em `lab_grades/v6_antiga/` (resultados brutos em `lab_cache/*.pkl`).

> **Hold-out:** os documentos antigos citam resultados de 2026 de *outras* estratégias (v5, v2_10min, FFV). Nada disso foi usado.

## 1. O que ela é, comparada ao nosso motor

| | v6 antiga | nossas "1" a "10" |
|---|---|---|
| Zona (gatilho) | **5** barras de 10 min (50 min) | 5 a 20 (a maioria 8 a 20) |
| Ordem | só a de continuação (`cont`), a **0,05** × média do gatilho | `cont`/`recuo`/`ambas`, bracket 0,05 a 1,0 |
| Saída | stop **1,0** · alvo **3,0** · trailing 1,6R | stop 1 a 5 · alvo **0,25 a 2** (muitos acertos, perda grande) |
| Ciclos | 1 por dia + **1 reversão** (stop 1,0 / alvo 4,0) | 1 a 5 ops; reversão em 4 das 10 |
| Veto de entrada | **filtro de formação** (3 barras fechadas) | não existe |
| Acerto / payoff | 40% / ganho médio 2× a perda | alvo menor que o stop nas 10 (acerto alto por construção, payoff < 1) |

A v6 vive no lado oposto das nossas: poucos acertos e payoff grande, entrada colada no extremo, uma única tentativa por dia.

**Filtro de formação (`ghost_filtro3 = ambos`):** quando a ordem vai encher, olha as 3 barras **já fechadas** antes da barra do fill; se os fundos estão subindo (`l1>l2>l3`) **ou** os topos descendo
(`h1<h2<h3`), a ordem morre e o motor volta a caçar gatilho **na barra seguinte**. Só lê barra fechada (sem look‑ahead).

## 2. Onde está o resultado (anatomia, 1.644 operações)

- **Horário:** 76% das operações e **89% do lucro** entram entre 09:00 e 10:59 (a hora das 10h sozinha: R$ 15,5 mil, 77%). Entradas depois das 12h somam ≈ R$ −450 (148 operações).
- **Perna:** entrada R$ 14,2 mil (1.027 ops, R$ 13,8/op) · reversão R$ 5,9 mil (617 ops, R$ 9,6/op); mesmo acerto (~40%).
- **Escala (media_op na entrada):** quartil calmo (< 279 pts) R$ **2,8**/op; mediano R$ 11 a 14; volátil (> 460) R$ **20,9**/op. A vantagem cresce com a volatilidade; em dia calmo mal cobre o custo.
- **Zona estreita** (1º quartil de amplitude): R$ 1,3/op, 33% de acerto. O filtro "zona mínima 150 pts" é **inerte** (nunca atua em 10 min).
- **Lado:** compra R$ 14,2/op, venda R$ 10,2/op. Dia da semana: sem padrão confiável (segunda/sexta mais fortes; quinta fraca).
- **Duração:** perdas saem em ~20 min; ganhos demoram ~60 min.
- **O ganho encolhe, ano a ano:**

| | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| R$ por operação | 31 | 21 | 9 | 6,9 | 6,4 |
| resultado médio por operação em múltiplos da media_op (1ª perna) | 0,40 | 0,23 | 0,14 | 0,14 | **0,00** |
| idem, reversão | 0,06 | 0,23 | 0,10 | 0,02 | 0,15 |

Em 2025 a primeira perna ficou em zero; quem pagou o ano foi a reversão. O que sustenta o total é o primeiro biênio, e a volatilidade do mercado caiu desde 2022.

## 3. O que cada peça vale

### 3.1 Uma peça por vez na v6 (descritivo; a v6 foi calibrada com tudo ligado)

| Variante | R$ | DD | Ret/DD | meses + | 2021 / 22 / 23 / 24 / 25 |
|---|---|---|---|---|---|
| **v6** | 20.051 | −1.717 | **11,7** | 36/52 | 3.494 / 7.928 / 3.527 / 2.603 / 2.499 |
| sem filtro de formação | 8.821 | −2.846 | 3,1 | 30/52 | 2.307 / 6.451 / **−1.766** / 365 / 1.464 |
| filtro `contra` (em vez de `ambos`) | 19.445 | −2.247 | 8,7 | 38/52 | 3.127 / 8.949 / 2.945 / 2.488 / 1.936 |
| sem reversão | 14.155 | −2.154 | 6,6 | 34/52 | 3.109 / 5.484 / 2.672 / 2.218 / 672 |
| sem trailing | 21.252 | −2.650 | 8,0 | 33/52 | 5.081 / 9.135 / 1.484 / 1.763 / 3.789 |
| sem trailing e sem reversão | 17.647 | −2.044 | 8,6 | 37/52 | 3.984 / 7.700 / 1.523 / 2.073 / 2.367 |
| bracket k = 0 / 0,1 / 0,25 / 0,5 | 16.484 / 16.038 / 10.039 / −1.085 | | 9,4 / 8,4 / 5,4 / −0,3 | | |
| gatilho 4 / 6 / 8 barras | 15.802 / 11.888 / −5.354 | | 5,7 / 4,2 / −0,8 | | |
| média 4 / 6 / 8 barras | 19.070 / 19.010 / −1.760 | | 10,1 / 10,4 / −0,3 | | |
| penetração 0 / 2 / 3 ticks | 21.019 / 18.217 / 16.402 | | 12,2 / 10,6 / 9,5 | | |
| 2 / 3 / 5 ciclos por dia | 19.345 / 10.918 / 8.315 | | 8,3 / 3,1 / 1,7 | | |
| última entrada 12:00 / 14:00 | 20.604 / 20.403 | | 12,8 / 11,9 | | |

O resultado é **muito sensível ao bracket** (colar no extremo: k ≈ 0,05) **e ao tamanho da zona** (≥ 8 barras quebra). Alvo ≥ 4 empata com 3 (o trailing/saída já limita).

### 3.2 O filtro de formação, por dentro

- Muda **566 dos 1.054 dias** (54%); em 557 deles a primeira entrada acontece **mais tarde**, nunca mais cedo. Nos dias que mudam: com filtro R$ +17,5/dia, sem filtro R$ −2,3/dia. Soma R$ +11,2 mil (284 dias melhoram +47,1 mil, 282 pioram −35,9 mil): **não é "pular dias ruins", é adiar a entrada para um momento melhor.**
- Pico em **n = 3**: n = 2 → R$ 5.608 · n = 4 → 13.683 · n = 5 → 7.439 · n = 6 → 6.549 (sem filtro: 8.821). Versão não estrita (`>=`, n = 3): 19.331 / Ret/DD 12,8. Só "topos descendo" (n = 3): 16.665 e **39/52 meses positivos** (a mais regular de todas); só "fundos subindo": 13.546; usando fechamentos em vez de topos/fundos: 5.511.
- **Operar a favor da tendência** nas entradas que o filtro cancelaria (stop no mesmo nível, custo cheio): **R$ −14** (Ret/DD 0) e variantes entre R$ −2.918 e +5.942. A formação em escada **não** é um sinal de continuação aproveitável; ela só serve como **veto**.

### 3.3 Teste pareado em 100 configurações sorteadas na vizinhança da v6
(stop 0,8–1,5 · alvo 2–5 · k 0–0,15 · zona 4–6 · média 4–6 · trailing 1,0–2,0 · 1–2 reversões · última entrada 14/16h · 1–2 ciclos; cada uma com e sem cada peça; treino ≤ 2023, teste 2024–25.)

| Peça | Δ treino (mediana, % que melhora) | Δ teste (mediana, % que melhora) | por ano (mediana Δ R$, % que melhora) |
|---|---|---|---|
| filtro de formação `ambos` vs off | +190 (52%, p = 0,76) | **+1.516 (82%)** | 2021 +925 (74%) · 2022 **−1.412 (30%)** · 2023 +1.260 (59%) · 2024 +1.978 (90%) · 2025 −308 (40%) |
| `ambos` vs `contra` | −1.694 (10%) | +474 (71%) | 2022 −1.946 (2%), nos outros anos ≈ 0 a +270 |
| trailing vs sem | **−2.428 (23%)** | −634 (34%) | 2022 −2.806 (11%); só 2023 positivo |
| reversão vs sem | −224 (48%) | **+2.062 (88%)** | 2021–2024 ≈ 0 ou negativo; **2025 +2.210 (98%)** |

Leitura honesta: o filtro de formação ajuda em média, mas **não é estável** (positivo em 3 dos 5 anos); a reversão só pagou em **2025**; **o trailing não ajuda** (a v6 o usa por causa do DD de uma célula calibrada).

### 3.4 A v6 entre os vizinhos: é um pico

| | v6 | vizinhos (mediana) | p10 – p90 |
|---|---|---|---|
| R$ treino (≤ 2023) | 14.949 | 5.027 | 1.058 – 10.065 |
| Ret/DD treino | 9,3 | 1,3 | 0,2 – 3,6 |
| R$ teste (2024–25) | 5.102 | 2.444 | −1.159 – 4.579 |
| Ret/DD total | 11,7 | 1,9 | 0,1 – 5,0 |

90% dos vizinhos são positivos no total, 81% no teste: **a família tem vantagem real, mas modesta**. A v6 é o melhor ponto de uma busca grande (mediana dos vizinhos R$ 7,6 mil contra 20 mil); o ritmo do teste sobre o do treino é 0,39 na v6 e 0,55 (mediana) nos vizinhos.
Entre os vizinhos o Ret/DD do treino **prevê** o do teste (correlação de postos 0,50; R$ 0,34): os 10 melhores pelo treino fizeram R$ 3.719 no teste contra R$ 2.444 de todos e R$ 308 dos 20 piores. A família é "aprendível", ao contrário do que o sistema antigo concluiu para a v2 de 10 min.

## 4. Conclusões

1. **O número R$ 20 mil não é o que se deve esperar.** É um pico de calibração: o desempenho típico da família é ~⅓ disso e o ritmo recente (R$ 2,5 mil/ano em 2024–25) já é o que as estimativas por retenção apontam. Em 2025 a primeira perna tinha vantagem zero.
2. **O que parece ser estrutural:** (a) colar a ordem no extremo (k ≈ 0 a 0,1) numa zona curta (4–6 barras); (b) uma tentativa por dia (mais ciclos pioram muito); (c) concentrar nas primeiras ~2 h; (d) o **veto de formação** como peça mais forte (R$ 8,8 → 20 mil) — mas instável por ano e com pico em n = 3.
3. **O que não vale levar:** trailing, zona mínima (inerte), alvo maior que 3, operar a favor da tendência nas entradas vetadas, escalar contratos por volatilidade (o sistema antigo já mediu: piora).
4. **Fragilidades conhecidas:** vantagem proporcional à volatilidade (cai em dias calmos e no regime de 2024–25); depende da fila (penetração 0 → 21 mil, 3 ticks → 16 mil); a reversão é concentrada em um ano.

## 5. Caminhos para "algo novo" (a decidir com o Ricardo)

- **A. Trazer o veto de formação para o nosso motor**, generalizado (nº de barras, topos/fundos/ambos, estrito ou não, "morre e caça na barra seguinte"), e avaliá-lo com o protocolo do laboratório (walk‑forward e teste **pareado** contra o acaso). É a única peça com efeito grande e consistente em vários vizinhos; falta saber se ajuda também as famílias de zona longa e alvo curto das "1" a "10".
- **B. Família "v6" dentro do laboratório** (zona curta, colada, 1 ciclo + reversão, stop 1 / alvo 3), selecionada por platô‑Sharpe/Ret/DD e depois **cesta por contribuição marginal** com as já cadastradas (payoffs opostos devem descorrelacionar).
- **C. Modo a favor da tendência como família própria** (não como veto reaproveitado): o teste de inverter as entradas vetadas deu zero, então só vale como sinal novo.
- **D. Portfólio de regimes:** a reversão valer só em 2025 e a primeira perna ter zerado sugerem um regime em que a falha do fade continua; um detector de regime (sem olhar 2026) poderia ligar/desligar a reversão.
