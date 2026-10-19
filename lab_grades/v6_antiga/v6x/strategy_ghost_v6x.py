"""Motor GHOSTCANDLE: gatilho na zona + bracket de meia-media, lido por sub-candle.

O GRAFICO e de `timeframe_min` (15 min no preset), mas a EXECUCAO le os sub-candles
de `ghost_sub_minutes` (5 min) que formam cada barra. Por que:

  Quando o preco cruza o gatilho, ficam DUAS ordens esperando - uma acima e uma
  abaixo. Se as duas forem tocadas dentro da mesma barra de 15 min, o OHLC nao diz
  qual veio primeiro, e a escolha muda o resultado inteiro (medido: Ret/DD 47 com o
  chute otimista contra 22 com a ordem resolvida). Os sub-candles de 5 min resolvem
  essa ordem na maior parte dos casos. Sobra a ambiguidade dentro do sub-candle de
  5 min, e ali o desempate e pela abertura (heuristica up_first), como no resto do
  projeto.

Regras (por pregao):
  1. ZONA = maxima/minima das ultimas ff2_maxmin_n barras JA FECHADAS.
     GATILHO = zona +/- ghost_trigger_offset_pts.
  2. Percorre os sub-candles da barra corrente ate um deles cruzar o gatilho.
  3. Cruzou -> congela as duas pontas a ghost_k x media_operacao do gatilho:
        acima do gatilho -> COMPRA        abaixo do gatilho -> VENDE
     (ff2_invert=True troca as duas: acima VENDE, abaixo COMPRA.)
     A primeira ponta tocada executa e cancela a outra. PODE ser no mesmo sub-candle
     do cruzamento. Com ghost_one_side_only=True fica so a ponta do RECUO (abaixo num
     topo, acima num fundo) - a de continuacao imediata nem e armada.
  4. Tipo de ordem: a ponta que o preco alcanca seguindo em frente e um STOP
     (agressiva, paga slippage e sofre gap); a outra e LIMITE (passiva, preenche no
     nivel). Isso e decidido pela direcao do movimento, nao por parametro.
  5. PROTECAO (opcional): breakeven por ff2_breakeven_pct (fracao do alvo) e trailing
     por ghost_trail_start_r (multiplos do risco). As duas so mudam quando uma barra
     de 15 min FECHA - a regra vive na barra, o sub-candle so resolve a ordem dos
     toques. CORRIGIDO EM 18/09/2026: o avanco a favor e medido a partir do
     sub-candle SEGUINTE ao da entrada; antes a barra da entrada entrava inteira e
     o trailing armava por movimento anterior a posicao. As medicoes antigas de
     trailing (a de 0,25R inclusive) foram feitas com o comportamento antigo e
     precisam ser refeitas. O breakeven usava o mesmo avanco e tambem mudou.
  6. Gestao identica a FFIII e reusa os ff2_*: stop = ff2_stop_mult x media_operacao,
     alvo = ff2_gain_mult x media_operacao, ambos recalculados a cada barra (a
     media_operacao flutua). Reversao opcional (ff2_max_reversals) no preco do stop;
     a posicao revertida pode ter stop/alvo PROPRIOS (ghost_rev_stop_mult e
     ghost_rev_gain_mult; 0 = herda os da entrada original).
     Resolvida tambem por sub-candle; dentro de um sub-candle o desempate e stop_first
     (pessimista). Ate ff2_max_trades entradas por pregao.

  7. ESCADA DE CONTRATOS (opcional, ghost_escada_*): o TAMANHO da posicao reseta todo
     pregao e sobe/desce/fica a cada trade conforme ganho ou perda. Nao interfere na
     execucao - contrato so multiplica o ponto -, entao e aplicado sobre os trades ja
     resolvidos e o numero e exato. Desligado por default.

Sem look-ahead: zona e media_operacao vem de barras JA FECHADAS; as duas ordens
descansam em niveis conhecidos antes da barra se formar; o sub-candle so informa a
ORDEM dos toques, nunca o futuro.
"""

from typing import List

import numpy as np
import pandas as pd

from ghostcandle.config import StrategyParams
from ghostcandle.strategy import (Trade, _make_trade, _fill, _close_action, _gap_level,
                       _protective_level)


def _subbars(df: pd.DataFrame, n_sub: int):
    """Achata os sub-candles do pregao em vetores cronologicos.

    Devolve (o, h, l, c, par, slot): `par` = indice da barra-mae, `slot` = posicao
    do sub-candle dentro dela (0, 1, 2...). Slots sem negocio sao descartados.
    """
    o, h, l, c, par, slot = [], [], [], [], [], []
    arrs = [tuple(df[f"s{x}{k}"].to_numpy(float) for x in "ohlc") for k in range(n_sub)]
    for i in range(len(df)):
        for k in range(n_sub):
            ao, ah, al, ac = arrs[k]
            if np.isnan(ah[i]):
                continue
            o.append(ao[i]); h.append(ah[i]); l.append(al[i]); c.append(ac[i])
            par.append(i); slot.append(k)
    return (np.array(o), np.array(h), np.array(l), np.array(c),
            np.array(par, dtype=int), np.array(slot, dtype=int))


def _escada_contratos(trades: List[Trade], params: StrategyParams) -> List[Trade]:
    """Aplica a escada de contratos sobre os trades JA resolvidos de UM pregao.

    O tamanho da posicao nao muda o caminho do preco - so quanto vale cada ponto.
    Por isso da para aplicar depois, sem tocar na execucao, e o resultado e
    EXATO, nao aproximado. A escada reseta a cada pregao porque run_day_ghost e
    chamada uma vez por pregao.

    Com ghost_escada_contratos = 0 nao faz nada (e o default).
    """
    ini = int(getattr(params, "ghost_escada_contratos", 0) or 0)
    if ini <= 0 or not trades:
        return trades
    lo = max(1, int(getattr(params, "ghost_escada_min", 1) or 1))
    hi = int(getattr(params, "ghost_escada_max", 0) or 0)
    hi = max(lo, hi if hi > 0 else ini)
    pv = float(params.point_value)
    k = min(max(ini, lo), hi)
    for t in trades:
        t.contracts = int(k)
        t.result_rs = float(t.pts * k * pv)
        # ganho = pts > 0. Zerado a mercado com pts <= 0 conta como perda.
        if t.pts > 0:
            acao = str(getattr(params, "ghost_escada_gain", "manter") or "manter")
            qtd = int(getattr(params, "ghost_escada_gain_qtd", 1) or 0)
        else:
            acao = str(getattr(params, "ghost_escada_loss", "manter") or "manter")
            qtd = int(getattr(params, "ghost_escada_loss_qtd", 1) or 0)
        if acao == "somar":
            k += qtd
        elif acao == "subtrair":
            k -= qtd
        k = min(hi, max(lo, k))
    return trades


def run_day_ghost_v6(day_df: pd.DataFrame, params: StrategyParams) -> List[Trade]:
    df = day_df.sort_values("datetime").reset_index(drop=True).copy()
    n = len(df)
    sub_m = int(getattr(params, "ghost_sub_minutes", 5) or 5)
    n_sub = 0
    while f"sh{n_sub}" in df.columns:
        n_sub += 1
    if n_sub < 2 or n < 3:
        return []                      # sem sub-candles nao ha o que este motor faz

    bh = df["high"].to_numpy(float); bl = df["low"].to_numpy(float)
    bc = df["close"].to_numpy(float)
    # bb_mid = EMA(ema_period) do fechamento, criada por add_indicators. Se a coluna
    # nao existir o filtro de afastamento fica INERTE (e nao bloqueia tudo calado).
    _tem_ema = "bb_mid" in df.columns
    _ema = (df["bb_mid"].to_numpy(float) if _tem_ema else np.full(len(df), np.nan))
    bt = df["datetime"].to_numpy()
    bmin = (pd.DatetimeIndex(df["datetime"]).hour * 60
            + pd.DatetimeIndex(df["datetime"]).minute).to_numpy()

    so, sh, sl, sc, spar, sslot = _subbars(df, n_sub)
    ns = len(spar)
    if ns == 0:
        return []
    smin = bmin[spar] + sslot * sub_m          # minuto real de cada sub-candle
    st = np.empty(ns, dtype=bt.dtype)
    for t in range(ns):
        st[t] = bt[spar[t]]            # carimbo da barra-mae (o trade pertence a ela)

    # --- Regras Adaptativas V6 ---
    # 1. VWAP diaria
    if "vfin" in df.columns:
        vwap = (bc * df["vfin"].to_numpy(float)).cumsum() / df["vfin"].to_numpy(float).cumsum()
    else:
        vwap = bc.copy() # fallback
    
    use_vwap = getattr(params, "v6_vwap_filter", False)
    
    # 2. ORB (Opening Range)
    orb_max_corpo = getattr(params, "v6_orb_max_corpo", 0.0)
    orb_min_corpo = getattr(params, "v6_orb_min_corpo", 0.0)
    
    dia_bloqueado = False
    reversao_bloqueada = False
    
    df_orb = df[(df['datetime'].dt.hour == 9) & (df['datetime'].dt.minute < 30)]
    if len(df_orb) > 0:
        orb_h = df_orb['high'].max()
        orb_l = df_orb['low'].min()
        orb_r = orb_h - orb_l
        if orb_r > 0:
            c_r = abs(df_orb.iloc[-1]['close'] - df_orb.iloc[0]['open']) / orb_r
            if orb_min_corpo > 0 and c_r < orb_min_corpo:
                dia_bloqueado = True
            if orb_max_corpo > 0 and c_r > orb_max_corpo:
                dia_bloqueado = True
                
    if dia_bloqueado:
        return []

    Wop = int(params.ff2_media_op_n); Wmm = int(params.ff2_maxmin_n)
    warm = max(Wop, Wmm)
    smult0 = float(params.ff2_stop_mult); gmult0 = float(params.ff2_gain_mult)
    # Stop/alvo PROPRIOS da reversao. 0 = herda o da entrada original, entao o
    # default e inerte e nenhum preset existente muda de comportamento.
    rev_s = float(getattr(params, "ghost_rev_stop_mult", 0.0) or 0.0)
    rev_g = float(getattr(params, "ghost_rev_gain_mult", 0.0) or 0.0)
    max_trades = int(params.ff2_max_trades)
    disc = float(params.malibu_vol_discard_mult)
    max_rev = int(params.ff2_max_reversals)
    if reversao_bloqueada:
        max_rev = 0
    rmin = float(getattr(params, "ff2_range_min_pts", 0.0))
    invert = bool(params.ff2_invert)
    kfrac = float(getattr(params, "ghost_k", 0.5))
    be_pct = float(getattr(params, "ff2_breakeven_pct", 0.0))    # 0 = sem breakeven
    tr_start = float(getattr(params, "ghost_trail_start_r", 0.0))  # 0 = sem trailing
    um_lado = bool(getattr(params, "ghost_one_side_only", False))
    armar = str(getattr(params, "ghost_armar", "ambas") or "ambas")
    filtro3 = str(getattr(params, "ghost_filtro3", "off") or "off")
    # AFASTAMENTO DA MEDIA: distancia entre o fechamento da ultima barra FECHADA e a
    # EMA dessa barra, em multiplos de media_op. So le barra fechada (ver config.py).
    op_mm = float(getattr(params, "op_mm_dist", 0.0) or 0.0)
    op_mm_max = float(getattr(params, "op_mm_max", 0.0) or 0.0)
    op_lado = str(getattr(params, "op_mm_lado", "livre") or "livre")

    f3_n = int(getattr(params, "f3_n", 3))
    f3_modo = str(getattr(params, "f3_modo", "ambos_lh"))   # ambos_lh | so_sobe | so_desce | fech | sobe_ou_fech
    f3_estrito = bool(getattr(params, "f3_estrito", True))
    f3_acao = str(getattr(params, "f3_acao", "cancelar"))

    def formacao3(j):
        """Generalizacao de pesquisa do freio de formacao: n barras fechadas antes de j."""
        if j < f3_n:
            return False, False
        if f3_modo == "fech":
            seq = [bc[j - k] for k in range(1, f3_n + 1)]          # j-1 (mais recente) ... j-n
            sobe = all(seq[k] > seq[k + 1] for k in range(f3_n - 1))
            desce = all(seq[k] < seq[k + 1] for k in range(f3_n - 1))
            return sobe, desce
        if f3_estrito:
            sobe = all(bl[j - k] > bl[j - k - 1] for k in range(1, f3_n))
            desce = all(bh[j - k] < bh[j - k - 1] for k in range(1, f3_n))
        else:
            sobe = all(bl[j - k] >= bl[j - k - 1] for k in range(1, f3_n))
            desce = all(bh[j - k] <= bh[j - k - 1] for k in range(1, f3_n))
        if f3_modo == "so_sobe":
            desce = False
        elif f3_modo == "so_desce":
            sobe = False
        return sobe, desce
    if armar == "ambas" and um_lado:
        armar = "recuo"                # compatibilidade com o parametro antigo
    off_t = float(getattr(params, "ghost_trigger_offset_pts", 0.0))
    end_m = params.end_time.hour * 60 + params.end_time.minute
    # Ultima ENTRADA do dia. A zeragem continua em end_m: sao coisas diferentes.
    _ue = int(getattr(params, "ghost_ult_entrada_hhmm", 0) or 0)
    ent_m = ((_ue // 100) * 60 + _ue % 100) if _ue else end_m
    parar_n = int(getattr(params, "ghost_parar_losses", 0) or 0)
    parar_md = str(getattr(params, "ghost_parar_modo", "dia") or "dia")
    pen = (float(getattr(params, "ghost_penetra_ticks", 0) or 0)
           * float(getattr(params, "tick_size", 0.0) or 0.0))
    start_m = params.start_time.hour * 60 + params.start_time.minute

    def media_op(j):
        rr = sorted((bh[j - Wop:j] - bl[j - Wop:j]).tolist())
        if disc > 0 and len(rr) >= 2 and rr[-1] > disc * rr[-2]:
            return sum(rr[:-1]) / (len(rr) - 1)
        return sum(rr) / len(rr) if rr else 0.0

    def up_sub(t):
        """Heuristica da abertura: True = o sub-candle subiu primeiro."""
        return abs(sh[t] - so[t]) <= abs(so[t] - sl[t])

    prim = {}
    for t in range(ns):
        prim.setdefault(spar[t], t)

    trades: List[Trade] = []
    cyc = 0
    i = warm
    while i < n and cyc < max_trades:
        if parar_n > 0 and trades:
            # Dia ruim: para de entrar. Nao mexe em posicao aberta - ela segue
            # ate alvo/stop/zeragem como sempre.
            if parar_md == "seguidos":
                perdidos = 0
                for tr_ant in reversed(trades):
                    if tr_ant.pts <= 0:
                        perdidos += 1
                    else:
                        break
            else:
                perdidos = sum(1 for tr_ant in trades if tr_ant.pts <= 0)
            if perdidos >= parar_n:
                break
        if bmin[i] >= ent_m:
            break
        if bmin[i] < start_m:
            i += 1
            continue
        mx = float(bh[i - Wmm:i].max()); mn = float(bl[i - Wmm:i].min())
        if rmin > 0 and (mx - mn) < rmin:
            i += 1
            continue
        mo = media_op(i)
        if mo <= 0:
            i += 1
            continue
        acima_mm = None
        if _tem_ema and (op_mm > 0 or op_mm_max > 0):
            ma = _ema[i - 1] if i >= 1 else float("nan")
            if not (ma == ma):                  # EMA ainda nao formada
                i += 1
                continue
            dmm = bc[i - 1] - ma
            if op_mm > 0 and abs(dmm) < op_mm * mo:        # perto demais da media
                i += 1
                continue
            if op_mm_max > 0 and abs(dmm) > op_mm_max * mo:  # longe demais
                i += 1
                continue
            acima_mm = dmm > 0
            
        t_up, t_dn = mx + off_t, mn - off_t

        if use_vwap and i > 0:
            # Trava pelo VWAP (0 = abaixo da VWAP, 1 = acima)
            # Acima = so compra, Abaixo = so vende
            v = vwap[i-1]
            if v > 0:
                if t_up < v: 
                    t_up = float('inf') # Bloqueia compra se gatilho de compra estiver abaixo da VWAP
                if t_dn > v:
                    t_dn = float('-inf') # Bloqueia venda se gatilho de venda estiver acima da VWAP

        # --- 1) cruzamento do gatilho, procurado sub-candle a sub-candle ---
        t0 = prim.get(i)
        if t0 is None:
            i += 1
            continue
        cu = False
        tc = -1
        t = t0
        while t < ns and spar[t] == i and smin[t] < ent_m:
            u = sh[t] >= t_up
            d = sl[t] <= t_dn
            if u and d:                       # cruzou os dois no mesmo sub-candle
                u = up_sub(t)
                d = not u
            if u or d:
                cu = u
                tc = t
                break
            t += 1
        if tc < 0:
            i += 1
            continue

        # --- 2) as duas pontas, congeladas no gatilho cruzado ---
        gat = t_up if cu else t_dn
        acima, abaixo = gat + kfrac * mo, gat - kfrac * mo
        lado_acima = "sell" if invert else "buy"
        lado_abaixo = "buy" if invert else "sell"
        # "Apenas um lado por gatilho": arma so a ponta do RECUO (abaixo se o gatilho
        # cruzado foi o topo; acima se foi o fundo). A outra - a de continuacao
        # imediata - nao chega a existir. O LADO de cada ponta nao muda (vem de
        # ff2_invert); o que muda e QUAL ordem fica no book.
        if armar == "recuo":
            if cu:
                lado_acima = None
            else:
                lado_abaixo = None
        elif armar == "cont":
            # So a ponta ALEM do gatilho. Como ela fica fora da zona, alcanca-la ja
            # PROVA que o gatilho foi cruzado antes - e como so ha uma ordem no book,
            # nunca aparece o caso das duas tocadas no mesmo sub-candle. Este modo e
            # inteiramente resolvido pelos dados.
            if cu:
                lado_abaixo = None
            else:
                lado_acima = None
        elif armar == "acima":
            lado_abaixo = None
        elif armar == "abaixo":
            lado_acima = None

        # Trava de direcao pelo lado da media (so quando o afastamento esta ligado).
        if acima_mm is not None and op_lado in ("fade", "momentum"):
            if op_lado == "fade":
                permitido = "sell" if acima_mm else "buy"
            else:
                permitido = "buy" if acima_mm else "sell"
            if lado_acima is not None and lado_acima != permitido:
                lado_acima = None
            if lado_abaixo is not None and lado_abaixo != permitido:
                lado_abaixo = None
        if lado_acima is None and lado_abaixo is None:
            i += 1
            continue

        se = -1
        cancel_bar = i
        entry = side = None
        eh_stop = False
        t = tc
        while t < ns and smin[t] < ent_m:
            # `pen` exige que o preco NEGOCIE alem do nivel para a ordem limite
            # contar como preenchida - encostar nao basta (ver config.py).
            ta = (lado_acima is not None) and sh[t] >= acima + pen
            tb = (lado_abaixo is not None) and sl[t] <= abaixo - pen
            # No sub-candle do CRUZAMENTO a ponta do RECUO precisa de um cuidado: ela
            # fica DENTRO da zona, entao o preco alcanca aquele nivel sem ter cruzado o
            # gatilho. Se este sub-candle ja ABRIU alem dela, o nivel foi tocado na
            # abertura - antes do cruzamento, quando a ordem ainda nao existia. Nao e
            # desempate, e aritmetica: aquela entrada nao podia ter ocorrido. A ponta
            # continua armada para os sub-candles seguintes.
            # A ponta de CONTINUACAO nao precisa do teste: ela fica ALEM do gatilho,
            # entao alcanca-la ja implica ter cruzado.
            if t == tc and ((so[t] <= abaixo) if cu else (so[t] >= acima)):
                if cu:
                    tb = False
                else:
                    ta = False
            if ta and tb:                     # as duas no mesmo sub-candle: abertura decide
                ta = up_sub(t)
                tb = not ta
            if (ta or tb) and filtro3 != "off":
                sobe, desce = formacao3(spar[t])
                lado_ord = lado_acima if ta else lado_abaixo
                if filtro3 == "contra":
                    freia = ((sobe and lado_ord == "sell")
                             or (desce and lado_ord == "buy"))
                else:
                    freia = sobe or desce
                if freia and f3_acao == "inverter":
                    # PESQUISA: em vez de cancelar, opera A FAVOR do rompimento no mesmo nivel (ordem stop, paga custo)
                    se = t
                    entry = acima if ta else abaixo
                    side = "buy" if ta else "sell"        # a favor do lado que o preco rompeu
                    eh_stop = True
                    break
                if freia:
                    se = -2               # entrada CANCELADA (a ordem morre)
                    cancel_bar = spar[t]
                    break
            if ta or tb:
                se = t
                entry = acima if ta else abaixo
                side = lado_acima if ta else lado_abaixo
                # a ponta que o preco alcanca seguindo em frente e ordem STOP
                eh_stop = (side == ("buy" if ta else "sell"))
                break
            t += 1
        if se == -2:                      # o freio de formacao cancelou esta entrada
            i = cancel_bar + 1            # volta a procurar gatilho na barra seguinte
            continue
        if se < 0:
            break                             # bracket nao resolveu ate o fim do pregao

        if eh_stop:
            entry = _gap_level(entry, so[se], side, params)
        entry_fill = _fill(entry, side, eh_stop, params)
        entry_time = st[se]
        cyc += 1
        reversals = 0
        # Cada CICLO comeca com o stop/alvo da entrada original. Se houver reversao
        # e ghost_rev_* estiver ligado, eles trocam ali e valem ate o fim do ciclo.
        smult, gmult = smult0, gmult0
        # Protecao (breakeven/trailing): estado por posicao. `prot` e o stop ja
        # conquistado - so aperta. `bar_ant` marca ate que barra de 15 min a protecao
        # ja foi atualizada (ela so muda quando uma barra FECHA).
        be_on = trail_on = False
        prot = None
        bar_ant = spar[se]
        ent_sub = se                      # sub-candle em que a posicao nasceu

        # --- 3) gestao, tambem por sub-candle ---
        saiu = None
        t = se + 1
        while t < ns:
            if smin[t] >= end_m:              # zeragem (a mercado, na abertura do sub-candle)
                xf = _fill(so[t], _close_action(side), True, params)
                trades.append(_make_trade(cyc, cyc, side, entry_time, entry_fill,
                                          st[t], xf, "time_close", params))
                saiu = spar[t]
                break
            j = spar[t]
            mop = media_op(j) if j >= Wop else 0.0
            if mop <= 0:
                t += 1
                continue

            # --- protecao: atualizada quando uma barra de 15 min FECHA ---
            while bar_ant < j:
                b = bar_ant                       # a barra b acabou de fechar
                mb = media_op(b) if b >= Wop else mop
                # A BARRA DA ENTRADA CONTA SO DEPOIS DA ENTRADA. Usar bh[b]/bl[b]
                # inteiros aqui creditaria a posicao o que o preco fez ANTES de ela
                # existir - e como a amplitude tipica de uma barra e ~1 media_operacao,
                # o trailing armaria por movimento nao vivido. Ao vivo (e em NTSL) a
                # contagem comeca na entrada. Das demais barras usa-se a barra inteira,
                # que e integralmente posterior a entrada.
                lo_b, hi_b = bl[b], bh[b]
                if b == spar[ent_sub]:
                    k0 = ent_sub + 1              # o proprio sub-candle da entrada nao
                    k1 = k0                       # conta: parte dele tambem e anterior
                    while k1 < ns and spar[k1] == b:
                        k1 += 1
                    if k1 > k0:
                        lo_b = float(sl[k0:k1].min())
                        hi_b = float(sh[k0:k1].max())
                    else:
                        lo_b = hi_b = entry       # nada observado apos a entrada
                adv = (hi_b - entry) if side == "buy" else (entry - lo_b)
                if trail_on:                      # segue a min/max da barra que fechou
                    lvl = lo_b if side == "buy" else hi_b
                    prot = lvl if prot is None else (max(prot, lvl) if side == "buy"
                                                     else min(prot, lvl))
                if be_pct > 0 and not be_on and adv >= be_pct * gmult * mb:
                    lvl = _protective_level(entry, lo_b, hi_b, side, params)
                    prot = lvl if prot is None else (max(prot, lvl) if side == "buy"
                                                     else min(prot, lvl))
                    be_on = True
                if tr_start > 0 and not trail_on:
                    trail_on = adv >= tr_start * smult * mb
                bar_ant += 1

            if side == "buy":
                stop = entry - smult * mop
                if prot is not None:
                    stop = max(stop, prot)
                target = entry + gmult * mop
                hit_stop = sl[t] <= stop
                hit_target = sh[t] >= target
            else:
                stop = entry + smult * mop
                if prot is not None:
                    stop = min(stop, prot)
                target = entry - gmult * mop
                hit_stop = sh[t] >= stop
                hit_target = sl[t] <= target
            if not (hit_stop or hit_target):
                t += 1
                continue
            if hit_stop:                      # dentro do sub-candle: stop primeiro (pessimista)
                lvl = _gap_level(stop, so[t], _close_action(side), params)
                xf = _fill(lvl, _close_action(side), True, params)
                pts = (xf - entry_fill) if side == "buy" else (entry_fill - xf)
                trades.append(_make_trade(cyc, cyc, side, entry_time, entry_fill,
                                          st[t], xf, "gain" if pts > 0 else "loss", params))
                if pts <= 0 and reversals < max_rev:   # STOP-AND-REVERSE no preco do stop
                    reversals += 1
                    # Stop/alvo proprios da reversao (0 = mantem os da entrada).
                    # Valem tambem para o trailing e o breakeven da posicao revertida,
                    # que sao medidos em multiplos do risco e do alvo CORRENTES.
                    if rev_s > 0:
                        smult = rev_s
                    if rev_g > 0:
                        gmult = rev_g
                    side = "sell" if side == "buy" else "buy"
                    entry = lvl
                    entry_fill = _fill(entry, side, True, params)
                    entry_time = st[t]
                    be_on = trail_on = False      # a reversao comeca sem protecao
                    prot = None
                    bar_ant = spar[t]
                    ent_sub = t
                    t += 1
                    continue
            else:                             # alvo = ordem limite, preenche no nivel
                xf = _fill(target, _close_action(side), False, params)
                trades.append(_make_trade(cyc, cyc, side, entry_time, entry_fill,
                                          st[t], xf, "gain", params))
            saiu = spar[t]
            break
        if saiu is None:                      # fim do pregao com posicao aberta
            x = ns - 1
            xf = _fill(sc[x], _close_action(side), True, params)
            trades.append(_make_trade(cyc, cyc, side, entry_time, entry_fill, st[x], xf,
                                      "eod", params))
            saiu = spar[x]
        i = saiu + 1
    return _escada_contratos(trades, params)
