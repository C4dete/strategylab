# New_winner_B — Script NTSL (WIN · gráfico 10 min · modo contínuo)

Reprodução do setup **"short + stop longo – B"** do StrategyLab (`estrategias/short_stop_longo_b.json`) com o **book "as duas pontas"** e **Rastrear MM** ligado.
Motor de referência: [`backend/strategylab/engine/ghost.py`](../backend/strategylab/engine/ghost.py) · regras em [`docs/motor.md`](../docs/motor.md).

> ## Estado deste script
> Escrito aqui **sem compilador** (não há como compilar NTSL neste ambiente). **Os testes iniciais no Profit passaram** (relato do Ricardo, 19/10/2026).
> Ainda valem o **replay tick a tick** e a **conta simulada** com o checklist do §8 antes de conta real; o que depende do comportamento da plataforma está marcado como **[REPLAY]** e no §9.
> Análise de fidelidade (o que o backtest não reproduz): [`docs/fidelidade_ntsl.md`](../docs/fidelidade_ntsl.md).

---

## 1. A regra em poucas linhas (o que o script faz)

1. **Zona** = máxima/mínima da **barra anterior fechada** (`MaxminN = 1`), só do próprio dia. **`media_op`** = média de (máx − mín) das **5 barras fechadas do dia**.
   Primeira entrada possível: a 6ª barra do dia (**09:50**), e nunca antes de `HoraIni` (09:30).
2. **Rastrear MM:** `Close[1]` **acima** da EMA(15) → só **VENDE**; **abaixo** → só **COMPRA**; igual → não opera a barra.
3. **Afastamento da MM:** o candle anterior precisa estar a **≥ 2,0 × `media_op`** da EMA (candle inteiro acima: `Low[1] − EMA`; inteiro abaixo: `EMA − High[1]`; tocando/cruzando a EMA: reprova).
4. **As duas pontas, com um lado só (Rastrear):** por barra existe **uma única ordem limite**, sempre a do lado permitido:
   - **Continuação** (pré-armada na abertura da barra): venda em `topo + 0,3 × media_op` (ou compra em `fundo − 0,3 × media_op`).
   - **Recuo** (só depois de o código ver o cruzamento): se o **primeiro** extremo rompido na barra for o do outro lado, a ordem passa a ser a do recuo — venda em `fundo + 0,3 × media_op`
     (ou compra em `topo − 0,3 × media_op`). O nível fica **congelado** no cruzamento e a ordem **não expira** até a última entrada (11:30) ou até encher.
5. **Saídas:** alvo **0,5 × media_op** (limite) e stop **2,0 × media_op** (stop-limite largo), recalculados a cada barra com a `media_op` corrente.
6. **Reversão (1 por ciclo):** stop com perda → abre o **lado oposto a mercado** ancorado no **preço do stop**, com **stop 3,5 × / alvo 2,2 ×** próprios (valem até o fim do ciclo). A reversão ignora a última entrada.
7. **Tempo máximo 240 min** por perna (a reversão recomeça o relógio): sai a mercado, **sem reverter**.
8. **Até 2 ciclos/dia**, sem re-entrada na barra em que o ciclo terminou. **Última entrada 11:30** (cancela o que estiver no book); **zeragem 17:30**.

---

## 2. Mapa: setup salvo → inputs do script

| Setup (`short_stop_longo_b.json`) | Script |
|---|---|
| `candles_gatilho` 1 | `MaxminN(1)` |
| `candles_media` 5 | `MediaN(5)` |
| `bracket_fracao` 0,3 | `KFrac(0.3)` |
| `book` ambas + `rastrear_mm` ligado | **estrutura fixa do código** (itens 2 e 4 acima) |
| `filtro_afast_mm_x_media` 2,0 | `AfastMult(2.0)` (0 desliga) |
| `mm_periodo` 15 | `MMPeriodo(15)` |
| `stop_x_media` 2,0 · `alvo_x_media` 0,5 | `StopMult(2.0)` · `GainMult(0.5)` |
| `reversoes` 1 · `rev_stop_x_media` 3,5 · `rev_alvo_x_media` 2,2 | `MaxRev(1)` · `RevStopMult(3.5)` · `RevGainMult(2.2)` |
| `operacoes_por_dia` 2 | `MaxCiclos(2)` |
| `janela_inicio` 09:30 · `ultima_entrada` 11:30 · `janela_fim` 17:30 | `HoraIni(930)` · `HoraUltEntrada(1130)` · `HoraFim(1730)` |
| `tempo_max_min` 240 | `TempoMaxMin(240)` |
| `penetracao_ticks` 1 | **sem equivalente** (a fila é a da bolsa) |
| (execução) 1 contrato | `Contratos(1)` |

Outros controles do StrategyLab **não implementados** (desligados no setup B): trailing, escada de contratos, candle discrepante (o `VolDiscard` existe no código, desligado), parar o dia por perdas,
filtros de gap/volatilidade/bandas/inclinação, modo "Próximo candle", saída ao tocar a MM. **Rastrear MM = 0 não é suportado** (a estrutura de uma ordem por barra depende dele).

---

## 3. Configuração no menu "Criar automação"

| Seção | Ajuste | Por quê |
|---|---|---|
| **Gráfico** | **WIN, 10 minutos**, contrato vigente. Role o histórico para trás **≥ 5 pregões** antes de ligar | a EMA e o contador de barras do dia dependem do histórico; veja §6 (rolagem) |
| **Modo de execução (§11.4)** | ✅ **"Realizar envio de ordens quando a condição for satisfeita"** + ✅ **"Permitir múltiplos envios e alterações de ordens para a mesma barra"**; ⬜ **NÃO** marque "Esperar o fechamento do candle" | o cruzamento do gatilho precisa ser visto **dentro** da barra (recuo e descarte de continuação) |
| **Opções de entrada (§11.3)** | permitir **compra E venda**; **Confirmar cada ordem = desligado** | — |
| **Saídas / OCO (§11.6)** | **NÃO configure OCO** | §11.11: OCO do menu faz o Profit **ignorar** as coberturas do código |
| **Quantidade por ordem** | 1 | o código passa `Contratos` em **todas** as ordens |
| **Horários (§11.5)** | 09:00 → 17:30 + **Zerar Posição** | redundância (o código também zera às 17:30) |
| **Risco (§11.7)** | **stop catastrófico bem largo** | rede da bolsa para gap/queda de conexão |
| **Segurança (§11.8)** | pausar e alertar em erro de execução | — |

---

## 4. Código

```pascal
//======================================================================
//  New_winner_B  -  WIN  -  grafico 10 min  -  MODO CONTINUO
//----------------------------------------------------------------------
//  Setup "short + stop longo - B" do StrategyLab (book AS DUAS PONTAS + Rastrear MM).
//  Referencia: backend/strategylab/engine/ghost.py. NAO COMPILADO: validar no REPLAY.
//
//  ZONA      = max/min das MaxminN barras JA FECHADAS do dia (aqui 1 = barra anterior).
//  MEDIA_OP  = media de (max-min) das MediaN barras JA FECHADAS do dia.
//  MM        = EMA(MMPeriodo) do fechamento, calculada AQUI em SERIE (alfa = 2/(N+1)),
//              valor no fechamento da barra ANTERIOR (mmF). Nada do candle em formacao.
//  RASTREAR  : Close[1] > mmF so VENDE ; Close[1] < mmF so COMPRA ; igual nao opera.
//  AFASTAMENTO: candle [1] a >= AfastMult x media_op da MM (inteiro acima: Low[1]-mm ;
//              inteiro abaixo: mm-High[1] ; tocando/cruzando: reprova).
//  ORDENS    : uma ordem LIMITE por barra (a do lado permitido).
//              - antes do cruzamento: CONTINUACAO pre-armada (venda em topo+K / compra em fundo-K);
//              - cruzou o extremo do LADO CONTRARIO primeiro: troca pela de RECUO
//                (venda em fundo+K / compra em topo-K). Nivel CONGELADO ate encher ou ate
//                HoraUltEntrada (gArm). Enquanto ARMADA nao procura outro gatilho (ordem nao resolvida ate 11:30 = sem entrada no dia).
//  SAIDAS    : alvo limite e stop-limite (folga de FolgaStopTicks) recalculados a cada barra.
//  REVERSAO  : stop com perda -> abre o lado oposto a mercado, ancorado no preco do stop,
//              com RevStopMult/RevGainMult. ModoRev=1: stop em repouso + mercado ao detectar a
//              saida (padrao v1-v3 / v5). ModoRev=2: ReversePosition por PRECO (padrao v4).
//  TEMPO MAX : TempoMaxMin por perna; sai a mercado e NAO reverte (gSaidaManual).
//  MENU      : modo "quando a condicao for satisfeita" + "multiplos envios" + OCO DESLIGADO.
//======================================================================

input
  MaxminN(1);            // barras da zona (max/min): 1 = so a barra anterior
  MediaN(5);             // barras da media_op (do proprio dia)
  VolDiscard(0.0);       // candle discrepante: 0 = desligado (o setup B nao usa)
  KFrac(0.3);            // bracket: nivel = gatilho -+ KFrac x media_op
  StopMult(2.0);         // stop da entrada = StopMult x media_op
  GainMult(0.5);         // alvo da entrada = GainMult x media_op
  MaxRev(1);             // reversoes por ciclo
  RevStopMult(3.5);      // stop da perna revertida
  RevGainMult(2.2);      // alvo da perna revertida
  MaxCiclos(2);          // entradas (ciclos) por pregao
  MMPeriodo(15);         // periodo da EMA (Rastrear + afastamento)
  AfastMult(2.0);        // afastamento minimo da MM em x media_op (0 = desligado)
  TempoMaxMin(240);      // tempo maximo por perna, em minutos (0 = desligado)
  UsarRelogio(0);        // 0 = hora de ABERTURA da barra (Time) ; 1 = CurrentTime (hora do sistema)
  HoraIni(930);          // HHMM - inicio das entradas
  HoraUltEntrada(1130);  // HHMM - ultima entrada (cancela ordens pendentes)
  HoraFim(1730);         // HHMM - zeragem
  Contratos(1);          // quantidade de TODAS as ordens
  ModoRev(1);            // 1 = stop em repouso + reversao a mercado ; 2 = ReversePosition por preco
  FolgaStopTicks(30);    // banda do stop-limite (30 ticks = padrao BMF)
  LogAtivo(1);           // 1 = eventos ; 2 = eventos + resumo de CADA barra (conferir contra o Python)

var
  i         : Integer;
  hora      : Integer;     // Time = hora de abertura da barra (HHMM)
  warm      : Integer;     // max(MediaN, MaxminN)
  nLado     : Integer;     // lado da posicao segundo a plataforma: 1 comprado, -1 vendido
  minAgora  : Integer;     // minutos desde 00:00 (relogio da barra ou do sistema)
  ladoPerm  : Integer;     // Rastrear MM: -1 so VENDE, 1 so COMPRA, 0 nao opera
  permOK    : Integer;     // 1 = a barra passou nos filtros (Rastrear + afastamento)
  cCima     : Integer;     // 1 = rompeu o topo da zona
  cBaixo    : Integer;     // 1 = rompeu o fundo da zona
  podeArmar : Integer;
  r         : Float;
  soma      : Float;
  rmax      : Float;
  rmax2     : Float;
  mediaOp   : Float;       // media_op da barra corrente (barras fechadas)
  zMax      : Float;       // maxima da zona
  zMin      : Float;       // minima da zona
  tUp       : Float;       // gatilho de cima = topo da zona
  tDn       : Float;       // gatilho de baixo = fundo da zona
  gat       : Float;       // gatilho cruzado
  dist      : Float;       // distancia do candle [1] ate a MM
  alpha     : Float;
  mmF       : Float;       // SERIE: EMA no fechamento da barra anterior (usa mmF[1])
  alvo      : Float;
  stopLvl   : Float;
  smult     : Float;
  gmult     : Float;
  folga     : Float;
  mmOK      : Integer;     // 1 = EMA com historico suficiente
  gLastBar  : Integer;     // ultima barra processada no Bloco A
  gDia      : Integer;     // data do pregao (reset diario)
  gBarDia   : Integer;     // barras do dia ate agora (1 = primeira)
  gCiclos   : Integer;     // entradas (ciclos) do dia
  gFimBar   : Integer;     // barra em que o ultimo ciclo terminou
  gArm      : Integer;     // 1 = ordem ARMADA (nivel congelado no cruzamento)
  gOrdLado  : Integer;     // lado da ordem armada: -1 venda, 1 compra
  gOrdPreco : Float;       // preco da ordem armada
  gLado     : Integer;     // estado do ciclo: 0 zerado, 1 comprado, -1 vendido
  gNivel    : Integer;     // 1 = entrada original ; 2 = perna revertida
  gRev      : Integer;     // reversoes ja feitas no ciclo
  gEntrada  : Float;       // preco de ancoragem do stop/alvo da perna
  gEntOrig  : Float;       // ancora da perna ANTES de pedir a reversao por preco (para desfazer no failsafe)
  precoPre  : Float;       // preco da ordem de continuacao pre-armada da barra
  gStopTeo  : Float;       // ultimo nivel de stop calculado (ancora da reversao)
  gEntMin   : Integer;     // minuto em que a perna abriu (tempo maximo)
  gSaidaMan : Integer;     // 1 = saida por tempo/zeragem (NAO reverte)
  gPend     : Integer;     // 1 = reversao pedida, aguardando confirmar o novo lado
  gEsperaRev: Integer;     // lado da reversao pedida: 1 compra, -1 venda
  gRevBar   : Integer;     // barra em que a reversao foi pedida (failsafe)

begin
  // ============================================================
  //  BLOCO 0 - MEDIA MOVEL em SERIE (toda execucao, sem condicao)
  //  mmF[0] = EMA ate o fechamento da barra ANTERIOR (= mm[i-1] do motor).
  //  So usa Close[1] e mmF[1] (ambos FINAIS): nao oscila com o candle em formacao
  //  e nao depende de variavel escalar (seguro contra reprocessamento).
  // ============================================================
  alpha := 2.0 / (MMPeriodo + 1);
  if (CurrentBar <= 1) then
    mmF := Close
  else
    mmF := mmF[1] + alpha * (Close[1] - mmF[1]);

  // reprocessamento do historico (pausa/retomada): zera o estado do script
  if (CurrentBar < gLastBar - 2) then
  begin
    gLastBar := 0;  gDia := 0;  gBarDia := 0;  gCiclos := 0;  gFimBar := 0;
    gArm := 0;  gPend := 0;  gEsperaRev := 0;  gSaidaMan := 0;
    gLado := 0;  gNivel := 0;  gRev := 0;
    mediaOp := 0;
  end;

  // ============================================================
  //  BLOCO A - 1x POR BARRA NOVA: zona, media_op e filtros (barras FECHADAS)
  // ============================================================
  if (CurrentBar > gLastBar) then
  begin
    gLastBar := CurrentBar;

    if (Date <> gDia) then
    begin
      gDia     := Date;
      gBarDia  := 1;
      gCiclos  := 0;
      gFimBar  := 0;
      gArm     := 0;              // a zona nunca enxerga barras de ontem
    end
    else
      gBarDia := gBarDia + 1;

    if (MediaN > MaxminN) then warm := MediaN else warm := MaxminN;
    if (CurrentBar > MMPeriodo + 2) then mmOK := 1 else mmOK := 0;

    mediaOp  := 0;
    permOK   := 0;
    ladoPerm := 0;

    if (gBarDia > warm) then
    begin
      // ---- media_op das MediaN barras fechadas (descarte opcional do maior) ----
      soma := 0;  rmax := 0;  rmax2 := 0;
      for i := 1 to MediaN do
      begin
        r := High[i] - Low[i];
        soma := soma + r;
        if (r > rmax) then
        begin
          rmax2 := rmax;
          rmax  := r;
        end
        else if (r > rmax2) then
          rmax2 := r;
      end;
      if (VolDiscard > 0) and (rmax > VolDiscard * rmax2) then
        mediaOp := (soma - rmax) / (MediaN - 1)
      else
        mediaOp := soma / MediaN;

      // ---- zona = max/min das MaxminN barras fechadas ----
      zMax := High[1];  zMin := Low[1];
      for i := 2 to MaxminN do
      begin
        if (High[i] > zMax) then zMax := High[i];
        if (Low[i]  < zMin) then zMin := Low[i];
      end;
      tUp   := zMax;
      tDn   := zMin;
      folga := FolgaStopTicks * MinPriceIncrement;

      // ---- filtros da BARRA (so leem a barra [1] e a EMA do fechamento dela) ----
      if (mmOK = 1) and (mediaOp > 0) then
      begin
        // Rastrear MM: fechamento anterior x EMA
        if (Close[1] > mmF) then
          ladoPerm := -1
        else if (Close[1] < mmF) then
          ladoPerm := 1
        else
          ladoPerm := 0;

        if (ladoPerm <> 0) then permOK := 1;

        // Afastamento da MM: candle [1] inteiro de um lado da EMA, a >= AfastMult x media_op
        if (permOK = 1) and (AfastMult > 0) then
        begin
          if (Low[1] > mmF) then
            dist := Low[1] - mmF
          else if (High[1] < mmF) then
            dist := mmF - High[1]
          else
            dist := 0;
          if (dist <= 0) or (dist < AfastMult * mediaOp) then permOK := 0;
        end;
      end;

      if (LogAtivo >= 2) then
        ConsoleLog("BARRA " + Time + " mm=" + mmF + " media_op=" + mediaOp + " zona=" + zMin + "/" + zMax
                   + " lado=" + ladoPerm + " perm=" + permOK + " dist=" + dist);
    end;
  end;

  // ============================================================
  //  BLOCO B - A CADA AVALIACAO (modo continuo)
  // ============================================================
  if (mediaOp > 0) then
  begin
    hora := Time;                                   // hora de ABERTURA da barra corrente
    if (UsarRelogio = 1) then
      minAgora := TimeToMinutes(CurrentTime)
    else
      minAgora := TimeToMinutes(Time);

    // ---------- ZERAGEM (>= HoraFim) ----------
    if (hora >= HoraFim) then
    begin
      if HasPosition then
      begin
        gSaidaMan := 1;                             // zeragem NAO reverte
        ClosePosition;
      end
      else
      begin
        if HasPendingOrders then CancelPendingOrders;
        gLado := 0;  gNivel := 0;  gRev := 0;
        gArm := 0;  gPend := 0;  gEsperaRev := 0;  gSaidaMan := 0;
      end;
    end

    // ---------- EM POSICAO ----------
    else if HasPosition then
    begin
      if IsBought then nLado := 1 else nLado := -1;

      // --- reversao pedida: espera o lado novo aparecer (ou desiste ao fim da barra seguinte) ---
      if (gPend = 1) then
      begin
        if (nLado = gLado) then
        begin
          gPend := 0;  gEsperaRev := 0;
          gEntMin := minAgora;                      // a reversao recomeca o relogio
          if (LogAtivo >= 1) then
            ConsoleLog("REVERSAO CONFIRMADA lado=" + gLado + " ancora=" + gEntrada);
        end
        else if (CurrentBar > gRevBar + 1) then
        begin
          // ainda na posicao ANTIGA e a reversao nao saiu: volta ao estado da perna original
          gLado := nLado;  gPend := 0;  gEsperaRev := 0;
          gRev := gRev - 1;  gNivel := 1;  gEntrada := gEntOrig;
          if (LogAtivo >= 1) then ConsoleLog("REVERSAO NAO EXECUTOU - segue na perna original");
        end;
      end
      // --- posicao nova (entrada) ou estado perdido: assume perna 1 ---
      else if (gLado <> nLado) then
      begin
        gLado    := nLado;
        gNivel   := 1;
        gRev     := 0;
        if IsBought then gEntrada := BuyPrice else gEntrada := SellPrice;
        gEntMin  := minAgora;
        gCiclos  := gCiclos + 1;
        gArm     := 0;
        gSaidaMan := 0;
        if HasPendingOrders then CancelPendingOrders;   // sobra de ordem de entrada (as coberturas sao enviadas DEPOIS, abaixo)
        if (LogAtivo >= 1) then
          ConsoleLog("ENTRADA lado=" + gLado + " preco=" + gEntrada + " media_op=" + mediaOp);
      end;

      // --- gestao da perna (so com o lado confirmado) ---
      if (gPend = 0) and (gLado = nLado) then
      begin
        if (gNivel >= 2) then
        begin
          smult := RevStopMult;
          gmult := RevGainMult;
        end
        else
        begin
          smult := StopMult;
          gmult := GainMult;
        end;

        // tempo maximo da perna: sai a mercado, NAO reverte
        if (TempoMaxMin > 0) and ((minAgora - gEntMin) >= TempoMaxMin) then
        begin
          if (gSaidaMan = 0) and (LogAtivo >= 1) then
            ConsoleLog("TEMPO MAXIMO " + TempoMaxMin + " min - saindo a mercado");
          gSaidaMan := 1;
          ClosePosition;
        end
        else if (gLado = 1) then
        begin
          // ----- COMPRADO -----
          alvo    := Round2Fraction(gEntrada + gmult * mediaOp);
          stopLvl := Round2Fraction(gEntrada - smult * mediaOp);
          gStopTeo := stopLvl;
          SellToCoverLimit(alvo, Contratos);
          if (ModoRev = 2) and (gNivel = 1) and (gRev < MaxRev) then
          begin
            // reversao por PRECO: sem stop em repouso na perna 1
            if (Close <= stopLvl) then
            begin
              gRev := gRev + 1;  gNivel := 2;
              gEntOrig := gEntrada;
              gEntrada := stopLvl;                  // ancora no preco do stop (igual simulacao)
              gEsperaRev := -1;  gLado := -1;
              gPend := 1;  gRevBar := CurrentBar;
              if (LogAtivo >= 1) then ConsoleLog("STOP COMPRA em " + stopLvl + " -> ReversePosition");
              ReversePosition;
            end;
          end
          else
            SellToCoverStop(stopLvl, stopLvl - folga, Contratos);
        end
        else
        begin
          // ----- VENDIDO -----
          alvo    := Round2Fraction(gEntrada - gmult * mediaOp);
          stopLvl := Round2Fraction(gEntrada + smult * mediaOp);
          gStopTeo := stopLvl;
          BuyToCoverLimit(alvo, Contratos);
          if (ModoRev = 2) and (gNivel = 1) and (gRev < MaxRev) then
          begin
            if (Close >= stopLvl) then
            begin
              gRev := gRev + 1;  gNivel := 2;
              gEntOrig := gEntrada;
              gEntrada := stopLvl;
              gEsperaRev := 1;  gLado := 1;
              gPend := 1;  gRevBar := CurrentBar;
              if (LogAtivo >= 1) then ConsoleLog("STOP VENDA em " + stopLvl + " -> ReversePosition");
              ReversePosition;
            end;
          end
          else
            BuyToCoverStop(stopLvl, stopLvl + folga, Contratos);
        end;
      end;
    end

    // ---------- ZERADO ----------
    else
    begin
      // --- reversao pedida a mercado (modo 1): reemite ate o lado novo aparecer ---
      if (gPend = 1) then
      begin
        if (CurrentBar > gRevBar + 1) then
        begin
          gPend := 0;  gEsperaRev := 0;
          gLado := 0;  gNivel := 0;  gRev := 0;
          gFimBar := CurrentBar;
          if (LogAtivo >= 1) then ConsoleLog("REVERSAO NAO EXECUTOU - ciclo encerrado");
        end
        else if (ModoRev = 1) then
        begin
          if (gEsperaRev = 1) then
            BuyAtMarket(Contratos)
          else
            SellShortAtMarket(Contratos);
        end;
      end

      // --- acabei de sair de uma posicao: stop com perda reverte; alvo/tempo/zeragem encerram ---
      else if (gLado <> 0) then
      begin
        if (gSaidaMan = 0) and (ModoRev = 1) and (gRev < MaxRev) and (LastTradeResult < 0) then
        begin
          gRev := gRev + 1;
          gNivel := 2;
          gEntrada := gStopTeo;                     // ancora a nova perna no preco do stop (igual simulacao)
          gEsperaRev := -gLado;                     // lado oposto
          gLado := gEsperaRev;
          gPend := 1;
          gRevBar := CurrentBar;
          if (LogAtivo >= 1) then
            ConsoleLog("STOP COM PERDA - reversao a mercado lado=" + gLado + " ancora=" + gEntrada);
          if (gEsperaRev = 1) then
            BuyAtMarket(Contratos)
          else
            SellShortAtMarket(Contratos);
        end
        else
        begin
          if (LogAtivo >= 1) then
            ConsoleLog("CICLO ENCERRADO (ciclos no dia: " + gCiclos + ") resultado=" + LastTradeResult);
          gLado := 0;  gNivel := 0;  gRev := 0;  gSaidaMan := 0;  gEsperaRev := 0;
          gFimBar := CurrentBar;                    // sem re-entrada nesta barra
        end;
      end

      // --- sem posicao e sem ciclo aberto: gerencia a ORDEM DE ENTRADA ---
      else
      begin
        if (hora >= HoraUltEntrada) then
        begin
          // fim das entradas: nada no book e nada novo
          if HasPendingOrders then CancelPendingOrders;
          gArm := 0;
        end
        else
        begin
          if (gBarDia > warm) and (gCiclos < MaxCiclos) and (CurrentBar > gFimBar) and (hora >= HoraIni) then
            podeArmar := 1
          else
            podeArmar := 0;

          if (podeArmar = 1) then
          begin
            if (gArm = 1) then
            begin
              // ordem JA ARMADA: nivel congelado, fica no book ate encher ou ate HoraUltEntrada
              if (gOrdLado = -1) then
                SellShortLimit(gOrdPreco, Contratos)
              else
                BuyLimit(gOrdPreco, Contratos);
            end
            else if (permOK = 1) then
            begin
              // nivel da CONTINUACAO do lado permitido (pre-arme)
              if (ladoPerm = -1) then
                precoPre := Round2Fraction(tUp + KFrac * mediaOp)
              else
                precoPre := Round2Fraction(tDn - KFrac * mediaOp);

              // cruzamento do gatilho DENTRO da barra (barra em formacao)
              if (High >= tUp) then cCima := 1 else cCima := 0;
              if (Low  <= tDn) then cBaixo := 1 else cBaixo := 0;
              if (cCima = 1) and (cBaixo = 1) then        // os dois no mesmo instante: a abertura desempata
              begin
                if (ABS(High - Open) <= ABS(Open - Low)) then
                begin
                  cCima := 1;  cBaixo := 0;
                end
                else
                begin
                  cCima := 0;  cBaixo := 1;
                end;
              end;

              if (cCima = 1) or (cBaixo = 1) then
              begin
                if (cCima = 1) then gat := tUp else gat := tDn;
                gOrdLado  := ladoPerm;                     // so o lado permitido pelo Rastrear
                // venda (-1): gatilho + K x media_op ; compra (1): gatilho - K x media_op
                gOrdPreco := Round2Fraction(gat - gOrdLado * KFrac * mediaOp);
                gArm := 1;
                // so cancela se o nivel MUDOU (cruzou o lado contrario: pre-armada -> recuo); cancelar e reenviar
                // o mesmo nivel perderia a prioridade na fila a toa. O cancelamento vem ANTES do envio da nova.
                if (gOrdPreco <> precoPre) and HasPendingOrders then CancelPendingOrders;
                if (gOrdLado = -1) then
                  SellShortLimit(gOrdPreco, Contratos)
                else
                  BuyLimit(gOrdPreco, Contratos);
                if (LogAtivo >= 1) then
                  ConsoleLog("GATILHO " + gat + " topo=" + cCima + " -> ordem lado=" + gOrdLado + " em " + gOrdPreco);
              end
              else
              begin
                // PRE-ARME da CONTINUACAO do lado permitido: so enche depois de o preco passar pelo gatilho
                if (ladoPerm = -1) then
                  SellShortLimit(precoPre, Contratos)
                else
                  BuyLimit(precoPre, Contratos);
              end;
            end
            else
            begin
              // barra reprovada nos filtros: nada no book
              if HasPendingOrders then CancelPendingOrders;
            end;
          end
          else
          begin
            // fora da janela / sem ciclos / barra do fim do ciclo: nada no book
            if HasPendingOrders then CancelPendingOrders;
          end;
        end;
      end;
    end;
  end;
end;
```

---

## 5. O que foi reproduzido, e como (motor × script)

| Regra do motor | No NTSL |
|---|---|
| Zona/`media_op` só com barras **fechadas do dia** (`warm = max(MediaN, MaxminN)`) | `High[i]/Low[i]`, `gBarDia > warm`, reset por `Date` (Bloco A) |
| Indicadores sem look-ahead: decide na barra `i` lendo `i − 1` | tudo no Bloco A lê `[1]`; a EMA usa só `Close[1]` e `mmF[1]` (**série**, ver §6) |
| EMA(15), α = 2/(N+1), série contínua | Bloco 0, em **série**, calculada à mão (não usa `MediaExp`) |
| Rastrear MM (igual à EMA → não opera) | `ladoPerm` (Bloco A) |
| Afastamento ≥ 2 × `media_op` (candle inteiro de um lado; tocar/cruzar reprova) | `dist` (Bloco A) |
| Ordem de continuação só existe além da zona | pré-arme: venda em `topo + K·media_op` / compra em `fundo − K·media_op` |
| **Primeiro** cruzamento define a ordem; recuo = `gatilho cruzado ± K` do lado permitido; nível **congelado** e sem expirar | `gArm`, `gOrdLado`, `gOrdPreco`; reemitida a cada avaliação |
| Última entrada 11:30 ≠ zeragem 17:30; a reversão ignora a última entrada | `HoraUltEntrada` só cancela **entradas**; `HoraFim` zera; o fluxo de reversão não olha a hora |
| Alvo/stop recalculados a cada barra com a `media_op` corrente | `SellToCoverLimit/Stop` e `BuyToCoverLimit/Stop` reemitidos a cada avaliação |
| Stop = mercado com custo; garantia de saída | `...ToCoverStop(stop, stop ∓ folga, Contratos)` com folga **explícita** de 30 ticks (padrão BMF) |
| Reversão no **preço do stop**, lado oposto, com stop/alvo próprios; 1 por ciclo; só stop com perda | `gEntrada := gStopTeo`; `RevStopMult/RevGainMult` pelo `gNivel` |
| Tempo máximo: a mercado, **não reverte** | `gSaidaMan` (também vale para a zeragem) |
| 2 ciclos/dia; sem re-entrada na barra da saída | `gCiclos`, `gFimBar` |

---

## 6. Lições da base de conhecimento aplicadas (e onde estão)

| Problema já resolvido na base | Como este script evita |
|---|---|
| **Look-ahead na banda** (`importante.md` §9): usar o fechamento da barra corrente inflou o backtest | EMA e filtros só com `Close[1]`/`High[1]`/`Low[1]`; `mmF` é a EMA **até a barra anterior** |
| **EMA com variável escalar** (`xEMA` do v4) quebra se o Profit reprocessar candles (manual §3) | EMA em **série** (`mmF := mmF[1] + α·(Close[1] − mmF[1])`), recalculada em toda execução; sem estado a guardar |
| **EMA calculada à mão** em vez de função pronta (`importante.md` §4; v1–v4) | idem; compare com `MediaExp(15, Close)[1]` no replay (§8) |
| **Stop com limite justo não executa em gap** (`importante.md` §1; v2→v3) | stop-limite com folga explícita de **30 ticks** e `Contratos` (padrão do v3) |
| **OCO do menu anula as coberturas do código** (manual §11.6/§11.11) | OCO desligado; coberturas no código |
| **Abre e fecha na mesma barra** / ordem duplicada (`importante.md` §2) | guardas `HasPosition`/`gLado`/`gPend` e `CurrentBar > gFimBar` |
| **Modo contínuo cancela o que não é reemitido** (`importante.md` §3) | entradas e coberturas **reemitidas a cada avaliação** com o mesmo preço |
| **Reversão a mercado no reprocessamento pós-execução pode ser bloqueada** (manual §11.11; `importante.md` §3) | `ModoRev=1` envia a mercado e **reenvia a cada avaliação** até o lado novo aparecer (failsafe de 1 barra); `ModoRev=2` usa `ReversePosition` por preço (v4) |
| **Candle de entrada sem imunidade** ao vivo (`importante.md` §10) | sem tratamento: ao vivo a ordem já nasce no book e o resto da barra conta (o motor dá imunidade ao minuto do fill — diferença **a favor do motor**) |
| **Hora do sistema vs. replay** (manual §16.14: `CurrentTime` é a hora do sistema) | `UsarRelogio(0)` usa `Time` (hora de abertura da barra) por padrão |

---

## 7. Divergências conhecidas: simulação × ao vivo

| # | Divergência | Efeito esperado |
|---|---|---|
| 1 | **Ordem de recuo**: só existe depois de o código ver o cruzamento (segundos, intervalo mínimo de 10 s entre envios). O motor tem resolução de 1 min e aceita o fill no minuto do cruzamento | **ao vivo pior.** Referência do **B com as duas pontas**: motor R$ 3.420; com o recuo atrasado 1–2 sub-candles, **R$ 2.800–3.100**. Use essa faixa, não os R$ 3.420 |
| 2 | **Fila / penetração**: o motor exige 1 tick além do nível; ao vivo vale a fila da bolsa | incerto (pouco sensível no B: 2–3 ticks custam ~6% no `cont`) |
| 3 | **Reversão a mercado** não é no preço exato do stop (latência, slippage; em spikes pode ser bem pior). O resultado do B vem **quase todo das pernas de reversão** | **ao vivo pior**; cada 100 pts piores nas pernas revertidas custam ≈ 14% do resultado (no setup com `cont`) |
| 4 | **Tempo máximo** com `Time` sai até 10 min cedo/tarde (granularidade de barra); com `CurrentTime` só vale se o replay acompanhar o relógio simulado **[REPLAY]** | pequeno (poucas saídas por tempo) |
| 5 | **Empate** de cruzamento no mesmo instante: o script usa a abertura (como o motor) | raro |
| 6 | **Dados**: o BD do backtest é do MT5, série contínua ajustada por rolagem; o Profit pode diferir em OHLC, sessão e rolagem. **A EMA depende das barras depois de 17:30**: sem elas o resultado do B caiu ~34% em teste de sensibilidade | **[REPLAY]** conferir MM, zona e sessão |
| 7 | **Rolagem de contrato**: no dia da virada o salto de preço contamina a EMA por ~1 pregão | evite operar o dia da rolagem; carregue histórico do contrato vigente |
| 8 | **Recuperação de estado**: se o Profit reprocessar com posição aberta, o script assume perna 1 | operar sem pausar/reiniciar com posição |

---

## 8. Checklist de replay (tick a tick, contrato vigente)

Ligue `LogAtivo(2)` e confira pelo console, **comparando com o Python** (mesmas barras de 10 min, pelos tempos e pontos relativos; o nível absoluto do MT5 é outro):

1. **Primeira entrada nunca antes das 09:50** e sempre ≥ `HoraIni` (09:30).
2. **EMA**: compare `mm` do log (`BARRA ...`) com `MediaExp(15, Close)[1]` plotada no mesmo gráfico (dif. ≈ 0 depois do aquecimento) e com o `mm` do StrategyLab (`/api/dia`, mesmo pregão, só no BD padrão):
   o `mm` logado na barra **B** é o `mm` da barra **B − 1** no `/api/dia`. Dif. constante é offset do contrato; dif. variável é dado/sessão.
3. **Rastrear**: com `Close[1] > mm` só aparecem ordens de **venda**; com `<`, só de **compra**; barra com candle tocando a EMA não arma nada.
4. **Afastamento**: no log, `dist ≥ 2 × media_op` nas barras com `perm=1`.
5. **Pré-arme**: antes do cruzamento existe **uma** ordem limite na continuação (`topo + 0,3 × media_op`).
6. **Cruzamento pelo lado contrário**: a pré-armada some e aparece a de **recuo** (`gatilho cruzado ± 0,3 × media_op`) — **meça o tempo** entre o cruzamento e a ordem no book.
7. **Ordem armada** fica no mesmo nível nas barras seguintes até encher ou até **11:30** (então some).
8. **Alvo e stop** aparecem como OCO; recalculam a cada barra; stop-limite com folga de 150 pts.
9. **Reversão** (o ponto principal): ao stop com perda, anote **preço do stop × preço de preenchimento da reversão**, o tempo entre os dois, e se o log mostrou **mais de uma ordem a mercado** (duplicidade). Teste `ModoRev=1` e `ModoRev=2` nos mesmos pregões **[REPLAY]**.
10. Perna revertida usa **stop 3,5 / alvo 2,2**; **não** reverte de novo; **tempo máximo** reinicia na reversão.
11. **Saída por tempo (240 min) ou zeragem 17:30 nunca dispara reversão**, mesmo com resultado negativo.
12. Máximo de **2 ciclos/dia** e nenhum re-arme na barra em que o ciclo terminou. Nada de ordens depois das 11:30, a não ser a reversão.
13. Verifique se `CurrentTime` acompanha o relógio do replay (para decidir `UsarRelogio`).

### Pregões de referência (motor, setup B com as duas pontas, dados até 2025)
Compare **horário, lado, pontos e motivo de saída** (os preços absolutos do MT5 não batem com os do Profit):

| Pregão | Operações do motor (horário do fill → saída · pontos · motivo) |
|---|---|
| 08/10/2021 | venda 11:18 → 12:15 · −950 stop · **compra (reversão) 12:15 → 12:19 · +1.025 alvo** |
| 26/11/2021 | compra 10:00 → 10:16 · −1.035 stop · **venda (reversão) 10:16 → 12:14 · +1.525 alvo** |
| 20/12/2021 | compra 10:04 → 11:14 · −1.110 stop · **venda (reversão) 11:14 → 15:14 · +460 tempo (240 min)** |
| 08/05/2025 | venda 09:52 → 10:41 · −755 stop · **compra (reversão) 10:41 → 12:08 · +845 alvo** |
| 19/08/2025 | compra 10:38 → 10:54 · +265 alvo · compra 11:21 → 12:21 · −425 stop · **venda (reversão) 12:21 → 15:10 · +325 alvo** |

Referência geral do motor (setup B, `book` = ambas, 2021-09 → 2025-12): 177 operações, 28 reversões, R$ 3.420 (use a faixa realista do §7, item 1).

---

## 9. Pontos que o script assume e **não foram verificados** (marcados para o replay)

- Que reemitir a mesma ordem a cada avaliação **não** gera ordens duplicadas (modelo "o modo contínuo reconcilia o conjunto de ordens", `importante.md` §3).
- Que `CancelPendingOrders` chamado **antes** de enviar a nova ordem, na mesma passagem, não cancela a nova.
- Que, no `ModoRev=1`, a ordem a mercado reenviada nas avaliações seguintes ao stop sai (e que o reenvio não duplica).
- Que `LastTradeResult < 0` é confiável logo após o stop (padrão dos v1–v3).
- `BuyPrice`/`SellPrice` como preço de entrada da perna (igual ao nível da ordem limite, salvo gap a favor).
- Sintaxe: nomes e assinaturas vêm do manual (`SellShortLimit`, `...ToCoverStop(stop, limite, qtd)`, `ReversePosition`, `ClosePosition`, `TimeToMinutes`, `CurrentTime`, `Round2Fraction`, `MinPriceIncrement`, `ConsoleLog`); o código **não foi compilado**.
