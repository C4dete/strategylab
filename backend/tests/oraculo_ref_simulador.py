# ORÁCULO INDEPENDENTE — cópia de base_conhecimento/scratch/ref_simulador.py (escrito do zero a partir das
# regras, sem reutilizar o motor). Usado só em tests/test_golden.py para conferir o cenário base trade a trade.
# EXTENSÃO (Etapa 2): filtro "Afastamento da MM" (`Cfg.afast`, `Cfg.afast_p`), escrito aqui de forma independente:
# a EMA é uma recursão em Python puro (sem pandas.ewm) sobre os fechamentos das barras de 10 min de TODOS os pregões, e
# o filtro lê SEMPRE a barra anterior (i-1) e a EMA do fechamento dela.
# EXTENSÃO (Etapa 3), também escrita de forma independente, com ramos explícitos de compra/venda:
#   `Cfg.entry_mode = "next_open"`: o sinal (ordem executada) só vira entrada na ABERTURA da barra seguinte, a mercado (custo
#     cheio); stop/alvo contam da abertura; o minuto da abertura já é gerido; sem barra seguinte ou com a abertura na última
#     entrada/depois, o sinal morre e o dia acaba.
#   `Cfg.rastrear = True`: decidido no gatilho; fechamento da barra anterior (i-1) contra a EMA do fechamento dela: acima so vende,
#     abaixo so compra, igual ou sem EMA nao opera (o oraculo cobre book cont: a ordem unica precisa ser do lado permitido).
#   (Etapa 6) controle de cauda e filtros de regime, tambem independentes: `Cfg.stop_day` (para o dia ao perder X x media_op ja realizado; barra
#     tambem a reversao), `Cfg.tmax` (cada perna sai a mercado na abertura do 1o minuto a >= N minutos da entrada), `Cfg.gap_max`/`Cfg.vol_max`
#     (dia: gap de abertura e amplitude de ontem contra a media das 20 amplitudes anteriores), `Cfg.bb` (largura das bandas, EMA +- k desvios da
#     janela, calculada aqui em Python puro) e `Cfg.incl` (|EMA[i-1] - EMA[i-1-N]| >= X x media_op). Sempre so a barra i-1 e dias anteriores.
#   `Cfg.mm_exit = True`: com a posição aberta, a EMA(`afast_p`) do fechamento da barra ANTERIOR à do minuto encerra a operação
#     quando o caminho do preço a alcança (extremos do minuto estendidos até o fechamento do minuto anterior); sai a mercado
#     no nível da MM (abertura, se o toque é contra a posição e o minuto abriu além). Vários eventos no mesmo minuto: o lado
#     adverso antes do lado a favor; no mesmo lado, o mais próximo; empate: stop, MM, alvo.
"""SIMULADOR DE REFERENCIA do motor `ghostcandle` (familia v5/v6), minuto a minuto.

Escrito do zero a partir das regras documentadas, SEM reutilizar codigo do motor. Serve para
validar o motor: com os defaults reproduz o preset `ghostcandle_v6_10min (sem ORB/VWAP)` trade a
trade (1.644 trades, R$ 20.051 no perfil 'Ao vivo', WIN_1M_21_25.csv). Ver docs/04-testes-internos.md.

Uso:
    import io, ref_simulador as ref
    from ghostcandle.io_csv import load_candles
    raw = load_candles(io.BytesIO(open("exemplo/WIN_1M_21_25.csv", "rb").read()))
    trades = ref.run(raw, ref.Cfg())          # DataFrame: um trade por linha (coluna rs = R$)

Cfg espelha o perfil realista: slip 5, spread 5, tick 5, penetracao 1 tick, janela 09:00-17:30,
ultima entrada 16:00. Opcoes de pesquisa (todas desligadas por default; so existem aqui, NAO no motor):
time_stop, block, rev_cond, align, gap, target_mode, trail_k, entry_risk, be, rev_trail, rev_be.
Registra MFE/MAE (mfe, mae, mo_e) e a perna (leg 0 = entrada, 1 = reversao) em cada trade.
"""
import numpy as np, pandas as pd, math


class Cfg:
    tf = 10; Wop = 5; Wmm = 5; k = 0.05; off = 0.0; stop = 1.0; gain = 3.0; trail = 1.6
    rev_max = 1; rev_s = 1.0; rev_g = 4.0; rangemin = 150.0; invert = True
    start = 9 * 60; ent_end = 16 * 60; end = 17 * 60 + 30; max_cycles = 1
    pen_ticks = 1; tick = 5.0; slip = 5.0; spread = 5.0; pv = 0.20
    filtro3 = "ambos"
    orb_lo = 0.0; orb_hi = 0.0; vwap_gate = False
    entry_risk = False
    be = 0.0
    rev_trail = None; rev_be = None
    # ---- novas (todas desligadas) ----
    time_stop = None          # minutos: fecha a MERCADO a perna que ficou N min sem alvo/stop (sem reversao)
    block = None              # (ini_min, fim_min): nao arma/preenche entradas com a barra nesta janela
    rev_cond = None           # ("fast"|"slow", N_min): reverte so se o stop da 1a perna veio em <= N (fast) ou > N (slow)
    align = None              # ("with"|"anti", {data: deriva}): so entra a favor (with) / contra (anti) da deriva multi-dia
    gap = None                # ({data: |gap|/amplitude_dia_anterior}, limite): pula o dia se razao >= limite
    target_mode = None        # "mid": alvo da 1a perna no meio da zona (congelado) | "midcap": min(meio da zona, gain x media_op)
    trail_k = None            # trailing 'chandelier' por barra: extremo - k x media_op (substitui a minima/maxima da barra)
    afast = 0.0               # filtro Afastamento da MM: distancia minima (x media_op) do candle i-1 ate a EMA(afast_p); 0 = off
    afast_p = 15
    emad = None               # {inicio da barra: EMA no fechamento dela}; montado em run()
    entry_mode = "limit"      # "limit" (ordem no nivel, minuto imune) | "next_open" (a mercado na abertura da barra seguinte)
    rastrear = False          # Rastrear MM: acima da EMA(afast_p) so vende; abaixo so compra (fechamento da barra i-1 vs EMA dela)
    stop_day = 0.0            # controle de cauda: para o dia ao perder X x media_op ja realizado (0 = off)
    tmax = 0                  # minutos maximos de cada perna (0 = off)
    gap_max = None            # filtro de gap do dia (x amplitude media dos 20 pregoes anteriores); None = off
    vol_max = None            # filtro de amplitude de ontem (÷ media das 20 anteriores a ontem); None = off
    bb = None                 # (periodo, k, min_pct, max_pct) largura das bandas; None = off
    esc = None                # escada de contratos: (ini, acao_ganho, qtd_ganho, acao_perda, qtd_perda, piso, teto); None = 1 contrato fixo
    disc = 0.0                # candle discrepante: o maior da janela > disc x o 2o maior sai da media_op (0 = off); regra do sistema antigo
    incl = None               # (max_x_media, barras) inclinacao da EMA(afast_p); None = off
    diaf = None               # {data: (gap, vol_ontem)}; montado em run()
    bbd = None                # {inicio da barra: largura % das bandas}
    incld = None              # {inicio da barra: EMA[t] - EMA[t-N]}
    mm_exit = False           # sai ao tocar a EMA(afast_p) do fechamento da barra anterior


def rnd_near(p, tick):
    return float(np.round(p / tick)) * tick if tick > 0 else p


def agg_fill(level, action, c):
    adv = c.slip + c.spread / 2.0
    p = level + adv if action == "buy" else level - adv
    if c.tick > 0:
        q = p / c.tick
        q = math.ceil(q) if action == "buy" else math.floor(q)
        p = q * c.tick
    return p


def lim_fill(level, c):
    return rnd_near(level, c.tick)


def day_bars(d1, tf):
    d1 = d1.sort_values("datetime").reset_index(drop=True)
    key = d1.datetime.dt.floor(f"{tf}min")
    bars = []; mins = []
    for kb, g in d1.groupby(key, sort=True):
        bars.append(dict(t=kb, o=g.open.iloc[0], h=g.high.max(), l=g.low.min(), c=g.close.iloc[-1], v=g.vfin.sum()))
        mins.append(g.reset_index(drop=True))
    return bars, mins


def run_day(d1, c):
    bars, mins = day_bars(d1, c.tf); n = len(bars)
    H = [b['h'] for b in bars]; L = [b['l'] for b in bars]
    mod = lambda ts: ts.hour * 60 + ts.minute
    warm = max(c.Wop, c.Wmm)
    if n < 3:
        return []
    dia = bars[0]['t'].date()
    if c.gap_max is not None and not (c.diaf.get(dia, (float('nan'), float('nan')))[0] < c.gap_max):
        return []
    if c.vol_max is not None and not (c.diaf.get(dia, (float('nan'), float('nan')))[1] < c.vol_max):
        return []
    if c.gap is not None and c.gap[0].get(dia, 0.0) >= c.gap[1]:
        return []
    if c.orb_lo > 0 or c.orb_hi > 0:
        ob = [b for b in bars if b['t'].hour == 9 and b['t'].minute < 30]
        if ob:
            r = max(b['h'] for b in ob) - min(b['l'] for b in ob)
            if r > 0:
                cr = abs(ob[-1]['c'] - ob[0]['o']) / r
                if (c.orb_lo > 0 and cr < c.orb_lo) or (c.orb_hi > 0 and cr > c.orb_hi):
                    return []
    vw = []; cv = cvv = 0.0
    for b in bars:
        cv += b['v']; cvv += b['c'] * b['v']; vw.append(cvv / cv)
    def mo(j):
        rr = sorted(H[x] - L[x] for x in range(j - c.Wop, j))
        if c.disc > 0 and len(rr) >= 2 and rr[-1] > c.disc * rr[-2]:
            rr = rr[:-1]
        return sum(rr) / len(rr)
    flat = []
    for bi, g in enumerate(mins):
        for r in g.itertuples(index=False):
            flat.append((bi, r))
    first = {}
    for idx, (bi, r) in enumerate(flat):
        first.setdefault(bi, idx)
    pen = c.pen_ticks * c.tick
    in_block = (lambda m: c.block is not None and c.block[0] <= m < c.block[1])
    trades = []; cyc = 0; i = warm
    while i < n and cyc < c.max_cycles:
        if c.stop_day > 0 and trades and sum(t_['pts'] for t_ in trades) <= -c.stop_day * mo(i):
            break
        if mod(bars[i]['t']) >= c.ent_end:
            break
        if mod(bars[i]['t']) < c.start:
            i += 1; continue
        if in_block(mod(bars[i]['t'])):
            i += 1; continue
        mx = max(H[i - c.Wmm:i]); mn = min(L[i - c.Wmm:i])
        if c.rangemin > 0 and (mx - mn) < c.rangemin:
            i += 1; continue
        m = mo(i)
        if m <= 0:
            i += 1; continue
        if c.bb is not None:
            w = c.bbd.get(bars[i - 1]['t'], float('nan'))
            if w != w or (c.bb[3] > 0 and w > c.bb[3]) or (c.bb[2] > 0 and w < c.bb[2]):
                i += 1; continue
        if c.incl is not None:
            sl_ = c.incld.get(bars[i - 1]['t'], float('nan'))
            if sl_ != sl_ or abs(sl_) >= c.incl[0] * m:
                i += 1; continue
        if c.afast > 0:
            rb = bars[i - 1]                              # candle de referencia: a barra FECHADA anterior
            ma = c.emad.get(rb['t'], float('nan'))        # EMA no fechamento DESSA barra
            if ma != ma:
                i += 1; continue
            if rb['l'] > ma:
                dist = rb['l'] - ma
            elif rb['h'] < ma:
                dist = ma - rb['h']
            else:
                dist = -1.0
            if dist <= 0 or dist < c.afast * m:
                i += 1; continue
        if c.rastrear:
            rb = bars[i - 1]
            ma_r = c.emad.get(rb['t'], float('nan'))
            if ma_r != ma_r or rb['c'] == ma_r:
                i += 1; continue
            rastro_lado = 'sell' if rb['c'] > ma_r else 'buy'
        t_up, t_dn = mx + c.off, mn - c.off
        if c.vwap_gate and i > 0:
            v = vw[i - 1]
            if v > 0:
                if t_up < v: t_up = float('inf')
                if t_dn > v: t_dn = float('-inf')
        cross = None
        for idx in range(first[i], len(flat)):
            bi, r = flat[idx]
            if bi != i or mod(r.datetime) >= c.ent_end:
                break
            u = r.high >= t_up; d = r.low <= t_dn
            if u and d:
                u = abs(r.high - r.open) <= abs(r.open - r.low); d = not u
            if u or d:
                cross = (idx, u); break
        if cross is None:
            i += 1; continue
        tc, cu = cross
        gat = t_up if cu else t_dn
        level = gat + c.k * m if cu else gat - c.k * m
        side = ("sell" if c.invert else "buy") if cu else ("buy" if c.invert else "sell")
        if c.rastrear and side != rastro_lado:                # so cobre book cont: a ordem unica e a do lado do cruzamento
            i += 1; continue
        if c.align is not None:
            dr = c.align[1].get(dia)
            if dr is None or dr == 0:
                i += 1; continue
            trend_up = dr > 0
            with_trend = (side == "buy") == trend_up
            if (c.align[0] == "with") != with_trend:
                i += 1; continue
        fill = None; killed = False; kb = None
        for idx in range(tc, len(flat)):
            bi, r = flat[idx]
            if mod(r.datetime) >= c.ent_end:
                break
            if in_block(mod(r.datetime)):
                killed = True; kb = bi; break
            hit = (r.high >= level + pen) if cu else (r.low <= level - pen)
            if hit:
                if c.filtro3 != "off" and bi >= 3:
                    sobe = L[bi - 1] > L[bi - 2] > L[bi - 3]; desce = H[bi - 1] < H[bi - 2] < H[bi - 3]
                    if sobe or desce:
                        killed = True; kb = bi; break
                fill = idx; break
        if killed:
            i = kb + 1; continue
        if fill is None:
            break
        ebi, er = flat[fill]
        entry = level; entry_fill = lim_fill(entry, c)
        if c.entry_mode == "next_open":
            nb = ebi + 1
            if nb not in first:                                   # sem barra seguinte: o sinal morre
                break
            nidx = first[nb]
            if mod(flat[nidx][1].datetime) >= c.ent_end:          # a abertura cai na ultima entrada (ou depois): o sinal morre
                break
            entry = flat[nidx][1].open                            # stop/alvo contam da abertura; o custo so entra no preco executado
            entry_fill = agg_fill(entry, side, c)
            ebi = nb; fill = nidx
        mid = (mx + mn) / 2.0
        tdist0 = (entry - mid) if side == "sell" else (mid - entry)       # distancia ate o meio da zona (congelada)
        cyc += 1
        rev = 0; smult, gmult = c.stop, c.gain
        prot = None; trail_on = False; be_on = False; bar_ant = ebi; ent_idx = fill; cur_side = side
        tr_cur = c.trail; be_cur = c.be
        ext = None
        mfe = mae = 0.0; mo_e = mo(ebi)
        done = False; idx = (fill if (c.entry_risk or c.entry_mode == "next_open") else fill + 1); xbar = None

        def rec(outcome, xf, r_, via_prot=False, by=""):
            pts_ = (xf - entry_fill) if cur_side == "buy" else (entry_fill - xf)
            trades.append(dict(date=dia, side=cur_side, entry_fill=entry_fill, exit_fill=xf, pts=pts_, outcome=outcome, leg=rev,
                               via_prot=via_prot, armed=trail_on, mfe=mfe, mae=mae, mo_e=mo_e, by=by,
                               entry_min=mod(flat[ent_idx][1].datetime), exit_min=mod(r_.datetime)))
            return pts_

        while idx < len(flat):
            bi, r = flat[idx]
            # excursoes (inclui o minuto corrente)
            if cur_side == "buy":
                mfe = max(mfe, r.high - entry); mae = max(mae, entry - r.low)
            else:
                mfe = max(mfe, entry - r.low); mae = max(mae, r.high - entry)
            if mod(r.datetime) >= c.end:
                xf = agg_fill(r.open, "sell" if cur_side == "buy" else "buy", c)
                rec("time_close", xf, r, by="zeragem")
                done = True; xbar = bi; break
            if c.tmax > 0 and mod(r.datetime) >= mod(flat[ent_idx][1].datetime) + c.tmax:       # tempo maximo da perna: a mercado, na abertura
                xf = agg_fill(r.open, "sell" if cur_side == "buy" else "buy", c)
                pts_t = (xf - entry_fill) if cur_side == "buy" else (entry_fill - xf)
                rec("gain" if pts_t > 0 else "loss", xf, r, by="tempo")
                done = True; xbar = bi; break
            if c.time_stop is not None and (mod(r.datetime) - mod(flat[ent_idx][1].datetime)) >= c.time_stop:
                xf = agg_fill(r.open, "sell" if cur_side == "buy" else "buy", c)
                rec("time_stop", xf, r)
                done = True; xbar = bi; break
            j = bi
            mop = mo(j) if j >= c.Wop else 0.0
            if mop <= 0:
                idx += 1; continue
            while bar_ant < j:
                b = bar_ant; mb = mo(b) if b >= c.Wop else mop
                lo_b, hi_b = L[b], H[b]
                if b == flat[ent_idx][0]:
                    # limite: o minuto do fill nao conta (parte dele e anterior); proximo candle: a entrada e na ABERTURA do minuto, ele conta
                    ini = ent_idx if (c.entry_mode == 'next_open' and rev == 0) else ent_idx + 1
                    after = [x for x in range(ini, len(flat)) if flat[x][0] == b]
                    if after:
                        lo_b = min(flat[x][1].low for x in after); hi_b = max(flat[x][1].high for x in after)
                    else:
                        lo_b = hi_b = entry
                adv = (hi_b - entry) if cur_side == "buy" else (entry - lo_b)
                if c.trail_k is not None:
                    fav_ext = hi_b if cur_side == "buy" else lo_b
                    ext = fav_ext if ext is None else (max(ext, fav_ext) if cur_side == "buy" else min(ext, fav_ext))
                if trail_on:
                    if c.trail_k is not None:
                        lvl = (ext - c.trail_k * mb) if cur_side == "buy" else (ext + c.trail_k * mb)
                    else:
                        lvl = lo_b if cur_side == "buy" else hi_b
                    prot = lvl if prot is None else (max(prot, lvl) if cur_side == "buy" else min(prot, lvl))
                if be_cur > 0 and not be_on and adv >= be_cur * gmult * mb:
                    lvl = min(entry, lo_b) if cur_side == "buy" else max(entry, hi_b)
                    prot = lvl if prot is None else (max(prot, lvl) if cur_side == "buy" else min(prot, lvl))
                    be_on = True
                if tr_cur > 0 and not trail_on:
                    trail_on = adv >= tr_cur * smult * mb
                bar_ant += 1
            if rev == 0 and c.target_mode in ("mid", "midcap") and tdist0 > 0:
                tdist = tdist0 if c.target_mode == "mid" else min(tdist0, gmult * mop)
            else:
                tdist = gmult * mop
            if cur_side == "buy":
                stop = entry - smult * mop
                if prot is not None: stop = max(stop, prot)
                target = entry + tdist
                hs = r.low <= stop; ht = r.high >= target
            else:
                stop = entry + smult * mop
                if prot is not None: stop = min(stop, prot)
                target = entry - tdist
                hs = r.high >= stop; ht = r.low <= target
            first_min = c.entry_risk and idx == ent_idx
            if first_min:
                ht = False
            # preco de referencia do caminho dentro do minuto: o fechamento do minuto anterior (ou a propria entrada, se ela
            # acontece na abertura deste minuto)
            pc = entry if (c.entry_mode == "next_open" and idx == ent_idx) else flat[idx - 1][1].close
            hm = False; ma = float("nan")
            if c.mm_exit:
                ma = c.emad.get(bars[bi - 1]['t'], float('nan'))   # EMA no fechamento da barra ANTERIOR a do minuto
                if ma == ma:
                    hm = min(r.low, pc) <= ma <= max(r.high, pc)
            if not (hs or ht or hm):
                idx += 1; continue
            closeact = "sell" if cur_side == "buy" else "buy"
            # ordem dos eventos no mesmo minuto: (a favor?, distancia ate o preco de referencia, empate stop<MM<alvo)
            cand = []
            if cur_side == "buy":
                if hs: cand.append((0, max(0.0, pc - stop), 0, "stop"))
                if hm: cand.append((1 if ma > pc else 0, abs(ma - pc), 1, "mm"))
                if ht: cand.append((1, max(0.0, target - pc), 2, "alvo"))
            else:
                if hs: cand.append((0, max(0.0, stop - pc), 0, "stop"))
                if hm: cand.append((1 if ma < pc else 0, abs(ma - pc), 1, "mm"))
                if ht: cand.append((1, max(0.0, pc - target), 2, "alvo"))
            quem = min(cand)[3]
            if quem == "mm":
                a_favor = (ma > pc) if cur_side == "buy" else (ma < pc)
                if a_favor:
                    lv = ma
                else:                                       # contra a posicao: se o minuto abriu alem da MM, sai na abertura
                    lv = min(ma, r.open) if closeact == "sell" else max(ma, r.open)
                xf = agg_fill(lv, closeact, c)
                pts_mm = (xf - entry_fill) if cur_side == "buy" else (entry_fill - xf)
                rec("gain" if pts_mm > 0 else "loss", xf, r, by="mm")
            elif quem == "stop":
                lv = stop if first_min else (min(stop, r.open) if closeact == "sell" else max(stop, r.open))
                xf = agg_fill(lv, closeact, c)
                via_prot = prot is not None and ((cur_side == "buy" and prot > entry - smult * mop) or (cur_side == "sell" and prot < entry + smult * mop))
                pts = rec("gain" if ((xf - entry_fill) if cur_side == "buy" else (entry_fill - xf)) > 0 else "loss", xf, r, via_prot, by="stop")
                rev_ok = True
                if c.rev_cond is not None:
                    held = mod(r.datetime) - mod(flat[ent_idx][1].datetime)
                    rev_ok = (held <= c.rev_cond[1]) if c.rev_cond[0] == "fast" else (held > c.rev_cond[1])
                dia_perdido = c.stop_day > 0 and sum(t_['pts'] for t_ in trades) <= -c.stop_day * mop
                if pts <= 0 and rev < c.rev_max and rev_ok and not dia_perdido:
                    rev += 1
                    if c.rev_s > 0: smult = c.rev_s
                    if c.rev_g > 0: gmult = c.rev_g
                    cur_side = "sell" if cur_side == "buy" else "buy"
                    entry = lv; entry_fill = agg_fill(entry, cur_side, c)
                    if c.rev_trail is not None: tr_cur = c.rev_trail
                    if c.rev_be is not None: be_cur = c.rev_be
                    prot = None; trail_on = False; be_on = False; bar_ant = bi; ent_idx = idx; ext = None
                    mfe = mae = 0.0; mo_e = mo(bi) if bi >= c.Wop else mo_e
                    idx += 1; continue
            else:
                xf = lim_fill(target, c)
                rec("gain", xf, r, by="alvo")
            done = True; xbar = bi; break
        if not done:
            last = flat[-1][1]; xf = agg_fill(last.close, "sell" if cur_side == "buy" else "buy", c)
            rec("eod", xf, last, by="fim_dados")
            xbar = flat[-1][0]
        i = xbar + 1
    return trades


def montar_ema(raw, c, p=None):
    """EMA(p, padrao c.afast_p) dos fechamentos das barras de c.tf min, de todos os pregoes em ordem, por recursao (adjust=False)."""
    p = c.afast_p if p is None else p
    d1 = raw.sort_values("datetime")
    fech = d1.groupby(d1.datetime.dt.floor(f"{c.tf}min"), sort=True).close.last()
    a = 2.0 / (p + 1)
    e = None
    out = {}
    for k, (t, cl) in enumerate(fech.items()):
        e = cl if e is None else a * cl + (1 - a) * e
        out[t] = e if k >= p - 1 else float('nan')
    return out


def montar_regime(raw, c):
    """Medidas de regime, em Python puro: do DIA (gap e amplitude de ontem; so dias anteriores + a abertura de hoje) e da BARRA
    (largura das bandas e inclinacao da EMA, no fechamento de cada barra)."""
    d1 = raw.sort_values("datetime")
    dias = []
    for dte, g in d1.groupby(d1.datetime.dt.date, sort=True):
        dias.append((dte, float(g.open.iloc[0]), float(g.high.max()), float(g.low.min()), float(g.close.iloc[-1])))
    amp = [h - l for _, _, h, l, _ in dias]
    c.diaf = {}
    for k, (dte, ab, _, _, _) in enumerate(dias):
        gap = vo = float('nan')
        if k >= 20:
            base = sum(amp[k - 20:k]) / 20.0
            if k >= 1 and base > 0:
                gap = abs(ab - dias[k - 1][4]) / base
        if k >= 21:
            base2 = sum(amp[k - 21:k - 1]) / 20.0
            if base2 > 0:
                vo = amp[k - 1] / base2
        c.diaf[dte] = (gap, vo)
    fech = d1.groupby(d1.datetime.dt.floor(f"{c.tf}min"), sort=True).close.last()
    ts, cl = list(fech.index), [float(x) for x in fech.values]
    if c.bb is not None:
        p, kk = c.bb[0], c.bb[1]
        mid = montar_ema(raw, c, p)
        c.bbd = {}
        for k, t in enumerate(ts):
            if k >= p - 1 and mid[t] == mid[t]:
                janela = cl[k - p + 1:k + 1]
                mu = sum(janela) / p
                sd = (sum((x - mu) ** 2 for x in janela) / p) ** 0.5            # desvio populacional
                c.bbd[t] = (2.0 * kk * sd) / mid[t] * 100.0
    if c.incl is not None:
        e = c.emad if c.emad is not None else montar_ema(raw, c)
        n_ = c.incl[1]
        c.incld = {}
        for k, t in enumerate(ts):
            if k >= n_ and e[t] == e[t] and e[ts[k - n_]] == e[ts[k - n_]]:
                c.incld[t] = e[t] - e[ts[k - n_]]


def aplica_escada(trades, c):
    """Contratos por operacao, pregao a pregao (reseta no dia): comeca no inicial; depois de cada operacao (pernas de reversao incluidas)
    sobe/desce/fica pelo resultado (pts > 0 = ganho; senao perda), sempre entre piso e teto."""
    if c.esc is None:
        for t in trades:
            t['contracts'] = 1
        return
    ini, ag, qg, ap, qp, lo, hi = c.esc
    dia = None
    k = ini
    for t in trades:
        if t['date'] != dia:
            dia = t['date']
            k = min(max(ini, lo), hi)
        t['contracts'] = k
        acao, q = (ag, qg) if t['pts'] > 0 else (ap, qp)
        if acao == 'somar':
            k = k + q
        elif acao == 'subtrair':
            k = k - q
        k = max(lo, min(hi, k))


def run(raw, c):
    if c.afast > 0 or c.mm_exit or c.rastrear or c.incl is not None:
        c.emad = montar_ema(raw, c)
    if c.gap_max is not None or c.vol_max is not None or c.bb is not None or c.incl is not None:
        montar_regime(raw, c)
    out = []
    for dte, g in raw.groupby("date", sort=True):
        out += run_day(g, c)
    aplica_escada(out, c)
    df = pd.DataFrame(out)
    if len(df):
        df['rs'] = df.pts * df.contracts * c.pv
    return df
