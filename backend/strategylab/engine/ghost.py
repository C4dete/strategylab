"""Motor GHOSTCANDLE: gatilho na zona + ordem(ns) no book, execução lida por sub-candle.

Porte do `strategy_ghost_v6.py` do sistema antigo, SEM os blocos que não fazem parte do produto
(ORB, VWAP, afastamento da média, reversão, trailing, breakeven, freio de formação, escada).
O comportamento do que ficou é idêntico — verificado trade a trade (ver `scripts/paridade_motor_antigo.py`).

Regras (por pregão, barras de `timeframe_min` lidas em sub-candles de `sub_min`):
  1. ZONA = máxima/mínima das últimas `n_zona` barras JÁ FECHADAS do dia. GATILHO = a própria zona.
  2. Percorre os sub-candles da barra corrente até um deles cruzar o gatilho.
  3. Cruzou -> congela as pontas a `k x media_op` do gatilho. FADE: acima do gatilho VENDE, abaixo COMPRA.
     `book` escolhe quais ordens ficam: ambas | cont (além do gatilho) | recuo (dentro da zona) | acima | abaixo.
     Todas as entradas são ordens LIMITE: preenchem no nível, sem custo. A ordem não expira até a última entrada.
  4. A ordem só conta como preenchida se o preço NEGOCIAR `penetracao` pontos além do nível (fila no book).
     Na ponta de recuo, o sub-candle do cruzamento que já abriu além do nível não vale (o nível foi tocado
     antes de a ordem existir).
  5. Gestão: stop = stop_mult x media_op, alvo = gain_mult x media_op, recalculados a cada barra. Dentro de um
     sub-candle vale stop primeiro (pessimista). Stop é ordem a mercado (paga custo e sofre gap); alvo é limite.
  6. Zeragem a mercado na abertura do primeiro sub-candle em/após `fim_min`; posição aberta no fim dos dados sai no fechamento.
  7. Parar o dia após N losses (todos do pregão ou só seguidos) e teto de operações por dia.
  8. FILTRO "Afastamento da MM" (opcional), decidido NO GATILHO, antes de a ordem entrar no book:
     candle de referência = a barra FECHADA anterior à do gatilho (i - 1). Acima da MM -> afastamento = mínima - MM;
     abaixo -> MM - máxima; cruza ou toca a MM -> reprovado. Precisa ser >= `afast_mult` x media_operacao.
     A MM é o valor NO FECHAMENTO dessa mesma barra (i - 1). Reprovou: não arma e a busca segue na barra seguinte.
  9. MODO DE ENTRADA "proximo_candle": o sinal (ordem executada pela regra 4, no sub-candle `se`) só vira entrada na
     ABERTURA da barra seguinte: a MERCADO (custo cheio), no preço de abertura do primeiro sub-candle dela. Stop e alvo
     contam a partir desse preço de abertura (o custo só entra no resultado) e o sub-candle da abertura NÃO é imune
     (a entrada acontece no início dele). Se a abertura cai na última entrada ou depois, ou não há barra seguinte, o
     sinal morre e o dia termina sem operação. No modo "padrao" vale tudo o que está acima (limite no nível, minuto imune).
 10. RASTREAR MM (opcional), decidido no gatilho: fechamento da barra fechada anterior (i - 1) contra a EMA do fechamento
     dela. Acima da MM só VENDE; abaixo só COMPRA (com `book` = ambas arma só a ordem permitida); igual ou sem EMA: não arma.
 11. REVERSÃO (opcional): stop COM PERDA (pontos <= 0) reverte a posição no PREÇO DO STOP, até `max_rev` vezes por ciclo.
     A perna nova entra a MERCADO (custo cheio, também no modo próximo candle), no lado oposto, ignora Rastrear MM e a
     última entrada (é continuação do ciclo), conta como o MESMO ciclo (`operacoes_por_dia` conta ciclos) e o sub-candle
     da reversão é imune. Stop/alvo próprios (`rev_*_mult`; 0 = herda) valem até o fim do ciclo, contados a partir do preço
     do stop. Só o STOP reverte: a saída na MM, o alvo e a zeragem não. A saída na MM vale para a perna revertida também.
 12. CONTROLE DE CAUDA (Etapa 6): `parar_dia_x`: ao fim de cada ciclo, se o resultado já REALIZADO do dia (soma das pernas, em pontos) for
     <= -X x media_operacao (a da barra atual, de barras fechadas), o dia acaba; a mesma conta barra a reversão. `tempo_max`: cada perna
     sai a MERCADO na abertura do primeiro sub-candle a `tempo_max` minutos ou mais da entrada (a zeragem vem primeiro).
 13. FILTROS DE REGIME (Etapa 6), só dado fechado: no DIA (decididos na abertura, sem história = bloqueia): gap = |abertura de hoje -
     fechamento de ontem| / amplitude média dos 20 pregões anteriores >= `gap_max`; vol de ontem = amplitude de ontem / média das 20
     anteriores a ontem >= `vol_max`. Na BARRA (no gatilho, olhando só i - 1): largura das bandas de Bollinger em % da linha central fora
     de [`bb_min`, `bb_max`]; |MM(i-1) - MM(i-1-N)| >= `incl_max` x media_operacao. Reprovou: o dia não opera / a busca segue na barra seguinte.
     CANDLE DISCREPANTE (`descarte_x`, 0 = desligado; porte do `malibu_vol_discard_mult` do sistema antigo): na media_operacao, se o MAIOR
     tamanho (máx − mín) da janela de `n_media` barras fechadas for ESTRITAMENTE maior que `descarte_x` × o 2º maior, esse candle (só ele)
     fica FORA da média (que passa a dividir por n − 1). Vale para toda conta com media_operacao (bracket, stop, alvo, filtros ×media, cauda);
     a zona (máx/mín do gatilho) continua com TODAS as barras.
 15. TRAILING STOP (opcional, porte do `ghost_trail_start_r` do sistema antigo; `trail_r`, 0 = desligado): a proteção é atualizada só quando uma
     barra FECHA, antes do primeiro sub-candle da barra seguinte. Para cada perna: no fechamento da barra b, o AVANÇO a favor (máx - entrada numa
     compra; entrada - mín numa venda) da barra b arma o trailing se >= `trail_r` x `stop_mult` x media_op(b). Armado, a cada barra que fecha o
     stop protegido vai para a MÍNIMA (compra) / MÁXIMA (venda) dessa barra e só aperta (nunca afrouxa); no fechamento que arma, ainda não move.
     A barra da entrada conta só o que veio DEPOIS da entrada (limite: a partir do sub-candle seguinte ao do fill; próximo candle: o sub-candle da
     abertura já conta; reversão: a partir do sub-candle seguinte). O stop efetivo é o mais apertado entre `stop_mult x media_op` e o protegido;
     o alvo não muda. Sai a MERCADO (custo cheio, gap na abertura se for o caso). Saída por esse nível = `saida_por='trailing'` (se o nível
     protegido era mais apertado que o stop normal); com perda (pts <= 0) a reversão também vale, como em qualquer stop. A reversão zera a proteção
     e reaplica o mesmo `trail_r` ao risco da nova perna (com o stop da reversão).
 16. ESCADA DE CONTRATOS (opcional, porte do `ghost_escada_*` do sistema antigo; `escada_ini` 0 = desligada): ver `aplicar_escada`. Não interfere na
     execução (contrato só multiplica o ponto): é aplicada ao FIM do pregão sobre as operações resolvidas, e o resultado é exato.
 14. SAÍDA AO TOCAR A MM (opcional): com a posição aberta, a MM do FECHAMENTO da barra anterior à do sub-candle
     (`mm[j - 1]`, congelada durante a barra j) encerra a operação quando o caminho do preço a alcança: máxima/mínima do
     sub-candle, estendidas até o fechamento do sub-candle anterior (um gap que PULA a MM também conta como toque). Sai a
     MERCADO, custo cheio, no nível da MM; se o toque é contra a posição e o sub-candle abriu além da MM, sai na
     abertura (gap), como o stop. Dentro de um sub-candle com mais de um evento vale a ordem pessimista: eventos do
     lado adverso do preço antes dos do lado a favor; no mesmo lado, o mais próximo primeiro (stop < MM < alvo no empate).

Sem look-ahead: zona, media_op, MM e candle de referência vêm de barras já fechadas (<= i - 1); o sub-candle só
informa a ORDEM dos toques.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .fills import Trade, close_action, fill, gap_level, make_trade


@dataclass(frozen=True)
class Cfg:
    """Configuração do motor, já em minutos/pontos (montada por `runner.montar_cfg`)."""

    inicio_min: int
    fim_min: int
    ult_entrada_min: int       # já resolvida: igual a fim_min quando não há limite próprio
    n_zona: int
    n_media: int
    k: float
    book: str
    penetracao: float          # em pontos (ticks x tamanho do tick)
    parar_n: int
    parar_modo: str
    max_ops: int
    stop_mult: float
    gain_mult: float
    sub_min: int
    slippage: float
    spread: float
    tick: float
    valor_ponto: float
    contratos: int
    afast_ativo: bool = False  # filtro "Afastamento da MM"
    afast_mult: float = 0.0    # afastamento mínimo, em x media_operacao
    modo_entrada: str = "padrao"   # "padrao" | "proximo_candle"
    sair_mm: bool = False      # saída ao tocar a MM
    rastrear: bool = False     # Rastrear MM: acima da MM só vende; abaixo dela só compra
    max_rev: int = 0           # reversões por ciclo (stop-and-reverse); 0 = desligado
    rev_stop_mult: float = 0.0   # stop da posição revertida, em x media_op (0 = herda o da entrada)
    rev_gain_mult: float = 0.0   # alvo da posição revertida, em x media_op (0 = herda o da entrada)
    parar_dia_x: float = 0.0     # para o dia ao perder X x media_op já realizado (0 = desligado)
    tempo_max: int = 0           # minutos máximos de cada perna (0 = desligado)
    gap_ativo: bool = False
    gap_max: float = 0.0
    vol_ativo: bool = False
    vol_max: float = 0.0
    bb_ativo: bool = False
    bb_min: float = 0.0          # largura das bandas em % da linha central; 0 = sem mínimo
    bb_max: float = 0.0
    incl_ativo: bool = False
    incl_max: float = 0.0        # x media_op
    escada_ini: int = 0          # escada de contratos: contratos no início de cada pregão (0 = desligada)
    escada_ganho: str = "manter"  # "manter" | "somar" | "subtrair" depois de pts > 0
    escada_ganho_qtd: int = 1
    escada_perda: str = "manter"  # depois de pts <= 0
    escada_perda_qtd: int = 1
    escada_min: int = 1
    escada_max: int = 5
    trail_r: float = 0.0         # trailing stop: arma ao avançar X x risco (risco = stop_mult x media_op da barra) a favor; 0 = desligado
    descarte_x: float = 0.0      # candle discrepante: o maior da janela > X × o 2º maior sai da media_op (0 = desligado)


@dataclass
class Ctx:
    """Contexto do pregão que NÃO é o candle: indicadores por barra (valor no FECHAMENTO da barra t; quem decide em i lê i-1)
    e as medidas de regime do dia (conhecidas na abertura: só dias anteriores + a abertura de hoje). NaN = sem história."""

    bbw: Optional[np.ndarray] = None      # largura das bandas de Bollinger em % da linha central
    slope: Optional[np.ndarray] = None    # MM[t] - MM[t - N], em pontos
    gap: float = float("nan")             # |abertura - fechamento de ontem| / amplitude média dos 20 pregões anteriores
    volp: float = float("nan")            # amplitude de ontem / média das 20 anteriores a ontem


def _subbars(df: pd.DataFrame, n_sub: int):
    """Achata os sub-candles do pregão em vetores cronológicos.

    Devolve (o, h, l, c, par, slot): `par` = índice da barra-mãe, `slot` = posição do sub-candle
    dentro dela. Slots sem negócio são descartados.
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


@dataclass
class DiaPrep:
    """Tudo o que o motor lê de um pregão e que NÃO depende dos parâmetros da estratégia (preparado uma vez, reaproveitado
    em todas as execuções: é o que torna o laboratório de combinações rápido). Os vetores não devem ser alterados."""

    n: int                  # nº de barras
    sub_min: int            # resolução dos sub-candles (o BD)
    bh: np.ndarray
    bl: np.ndarray
    bc: np.ndarray
    bt: np.ndarray          # início de cada barra (datetime64)
    bmin: np.ndarray        # minuto do dia do início de cada barra
    so: np.ndarray
    sh: np.ndarray
    sl: np.ndarray
    sc: np.ndarray
    spar: np.ndarray        # barra-mãe de cada sub-candle
    smin: np.ndarray        # minuto real de cada sub-candle
    sts: np.ndarray         # carimbo real de cada sub-candle
    prim: dict              # barra -> índice do primeiro sub-candle dela
    mo: dict = field(default_factory=dict, repr=False)   # memória de media_operacao: {janela: {barra: valor}} (função pura das barras)


def preparar_dia(day_df: pd.DataFrame, sub_min: int) -> Optional[DiaPrep]:
    """Prepara um pregão (`day_df` já ordenado por horário, índice 0..n-1). `None` = o motor não opera esse dia."""
    n = len(day_df)
    n_sub = 0
    while f"sh{n_sub}" in day_df.columns:
        n_sub += 1
    if n_sub < 2 or n < 3:
        return None                    # sem sub-candles não há o que este motor faz
    bt = day_df["datetime"].to_numpy()
    idx = pd.DatetimeIndex(day_df["datetime"])
    bmin = (idx.hour * 60 + idx.minute).to_numpy()
    so, sh, sl, sc, spar, sslot = _subbars(day_df, n_sub)
    if len(spar) == 0:
        return None
    prim: dict = {}
    for t in range(len(spar)):
        prim.setdefault(spar[t], t)
    return DiaPrep(
        n=n, sub_min=sub_min,
        bh=day_df["high"].to_numpy(float), bl=day_df["low"].to_numpy(float), bc=day_df["close"].to_numpy(float),
        bt=bt, bmin=bmin, so=so, sh=sh, sl=sl, sc=sc, spar=spar,
        smin=bmin[spar] + sslot * sub_min,                                  # minuto real de cada sub-candle
        sts=bt[spar] + (sslot * sub_min).astype("timedelta64[m]"),          # carimbo real do sub-candle
        prim=prim,
    )


def aplicar_escada(trades: List[Trade], cfg: Cfg) -> List[Trade]:
    """Escada de contratos (porte do `_escada_contratos` do sistema antigo), sobre as operações JÁ resolvidas de UM pregão, em ordem.

    O tamanho da posição não muda o caminho do preço, só quanto vale cada ponto: por isso a escada é aplicada depois e o resultado é exato.
    O pregão começa com `escada_ini` contratos (preso entre o piso e o teto); cada operação (cada PERNA, reversões incluídas) usa o tamanho
    corrente e depois o tamanho sobe, desce ou fica conforme ela tenha sido ganho (pts > 0) ou não (pts <= 0, inclusive zeragem sem ganho),
    sempre entre `escada_min` e `escada_max`. Reseta a cada pregão. `escada_ini` = 0 não faz nada (contratos fixos).
    """
    if cfg.escada_ini <= 0 or not trades:
        return trades
    lo = max(1, cfg.escada_min)
    hi = max(lo, cfg.escada_max if cfg.escada_max > 0 else cfg.escada_ini)
    k = min(max(cfg.escada_ini, lo), hi)
    for t in trades:
        t.contratos = int(k)
        t.rs = float(t.pts * k * cfg.valor_ponto)
        acao, qtd = (cfg.escada_ganho, cfg.escada_ganho_qtd) if t.pts > 0 else (cfg.escada_perda, cfg.escada_perda_qtd)
        if acao == "somar":
            k += qtd
        elif acao == "subtrair":
            k -= qtd
        k = min(hi, max(lo, k))
    return trades


def run_day(day_df: pd.DataFrame, cfg: Cfg) -> List[Trade]:
    """Roda um pregão a partir do DataFrame (com a coluna `mm` quando alguma regra de MM está ligada)."""
    df = day_df.sort_values("datetime").reset_index(drop=True)
    dp = preparar_dia(df, cfg.sub_min)
    if dp is None:
        return []
    mm = None
    if cfg.afast_ativo or cfg.sair_mm or cfg.rastrear:
        if "mm" not in df.columns:
            raise ValueError("Filtro de afastamento, Rastrear MM ou saída na MM ligado, mas a coluna 'mm' (EMA no fechamento) não foi fornecida.")
        mm = df["mm"].to_numpy(float)        # mm[t] = EMA no FECHAMENTO da barra t (quem decide em i lê mm[i-1])
    ctx = None
    if cfg.bb_ativo or cfg.incl_ativo or cfg.gap_ativo or cfg.vol_ativo:
        falta = [c for c, on in (("bbw", cfg.bb_ativo), ("slope", cfg.incl_ativo), ("gap_dia", cfg.gap_ativo), ("vol_ontem", cfg.vol_ativo))
                 if on and c not in df.columns]
        if falta:
            raise ValueError(f"Filtro de regime ligado, mas faltam as colunas {', '.join(falta)}.")
        col = lambda c: df[c].to_numpy(float) if c in df.columns else None      # noqa: E731
        ctx = Ctx(bbw=col("bbw"), slope=col("slope"),
                  gap=float(df["gap_dia"].iloc[0]) if "gap_dia" in df.columns else float("nan"),
                  volp=float(df["vol_ontem"].iloc[0]) if "vol_ontem" in df.columns else float("nan"))
    return run_day_prep(dp, cfg, mm, ctx)


def run_day_prep(dp: DiaPrep, cfg: Cfg, mm: Optional[np.ndarray] = None, ctx: Optional[Ctx] = None) -> List[Trade]:
    """O motor propriamente dito, sobre um pregão já preparado. `mm[t]` = EMA no FECHAMENTO da barra t."""
    if dp.sub_min != cfg.sub_min:
        raise ValueError(f"Pregão preparado com sub-candles de {dp.sub_min} min, mas a configuração usa {cfg.sub_min} min.")
    if mm is None and (cfg.afast_ativo or cfg.sair_mm or cfg.rastrear):
        raise ValueError("Filtro de afastamento, Rastrear MM ou saída na MM ligado, mas a coluna 'mm' (EMA no fechamento) não foi fornecida.")
    if (cfg.bb_ativo and (ctx is None or ctx.bbw is None)) or (cfg.incl_ativo and (ctx is None or ctx.slope is None)):
        raise ValueError("Filtro de largura das bandas / inclinação da MM ligado, mas o contexto do pregão não foi fornecido.")
    if ctx is None:
        ctx = Ctx()
    # Filtros de regime do DIA: decididos na abertura; sem história (NaN) = bloqueia, como o afastamento sem EMA.
    if cfg.gap_ativo and not (ctx.gap < cfg.gap_max):
        return []
    if cfg.vol_ativo and not (ctx.volp < cfg.vol_max):
        return []
    n, bh, bl, bc, bt, bmin = dp.n, dp.bh, dp.bl, dp.bc, dp.bt, dp.bmin
    so, sh, sl, sc, spar, smin, sts, prim = dp.so, dp.sh, dp.sl, dp.sc, dp.spar, dp.smin, dp.sts, dp.prim
    ns = len(spar)

    Wop, Wmm = cfg.n_media, cfg.n_zona
    warm = max(Wop, Wmm)
    start_m, end_m, ent_m = cfg.inicio_min, cfg.fim_min, cfg.ult_entrada_min

    desc = cfg.descarte_x
    mo_memo = dp.mo.setdefault((Wop, desc), {})

    def media_op(j: int) -> float:
        v = mo_memo.get(j)
        if v is None:
            rr = sorted((bh[j - Wop:j] - bl[j - Wop:j]).tolist())
            if desc > 0 and len(rr) >= 2 and rr[-1] > desc * rr[-2]:
                rr = rr[:-1]                                   # candle discrepante: o maior sai da média (só ele)
            v = mo_memo[j] = sum(rr) / len(rr) if rr else 0.0
        return v

    def up_sub(t: int) -> bool:
        """Heurística da abertura: True = o sub-candle subiu primeiro."""
        return abs(sh[t] - so[t]) <= abs(so[t] - sl[t])

    trades: List[Trade] = []
    cyc = 0
    i = warm
    while i < n and cyc < cfg.max_ops:
        if cfg.parar_n > 0 and trades:
            # Dia ruim: para de entrar. Não mexe em posição aberta (ela já foi resolvida no ciclo anterior).
            if cfg.parar_modo == "seguidos":
                perdidos = 0
                for tr_ant in reversed(trades):
                    if tr_ant.pts <= 0:
                        perdidos += 1
                    else:
                        break
            else:
                perdidos = sum(1 for tr_ant in trades if tr_ant.pts <= 0)
            if perdidos >= cfg.parar_n:
                break
        if cfg.parar_dia_x > 0 and trades and i >= Wop:
            # Controle de cauda: o que o dia já realizou (todas as pernas fechadas) contra X x media_operacao da barra atual.
            if sum(t_.pts for t_ in trades) <= -cfg.parar_dia_x * media_op(i):
                break
        if bmin[i] >= ent_m:
            break
        if bmin[i] < start_m:
            i += 1
            continue
        mx = float(bh[i - Wmm:i].max())
        mn = float(bl[i - Wmm:i].min())
        mo = media_op(i)
        if mo <= 0:
            i += 1
            continue
        t_up, t_dn = mx, mn

        # --- filtros de regime da BARRA: só leem a barra FECHADA i-1 (indicador no fechamento dela) ---
        if cfg.bb_ativo:
            w = ctx.bbw[i - 1]
            if not (w == w) or (cfg.bb_max > 0 and w > cfg.bb_max) or (cfg.bb_min > 0 and w < cfg.bb_min):
                i += 1
                continue
        if cfg.incl_ativo:
            s_ = ctx.slope[i - 1]
            if not (s_ == s_) or abs(s_) >= cfg.incl_max * mo:
                i += 1
                continue

        # --- filtro "Afastamento da MM": só lê a barra FECHADA i-1 e a EMA do fechamento dela ---
        ref = None
        if cfg.afast_ativo:
            r = i - 1                                 # candle de referência (sempre do mesmo pregão: i >= warm >= 2)
            ma = mm[r]
            if np.isnan(ma):                           # EMA ainda sem histórico suficiente
                i += 1
                continue
            if bl[r] > ma:                             # candle inteiro ACIMA da MM: do fundo até a MM
                dist = float(bl[r] - ma)
            elif bh[r] < ma:                           # candle inteiro ABAIXO da MM: do topo até a MM
                dist = float(ma - bh[r])
            else:                                      # toca ou cruza a MM
                dist = 0.0
            if dist <= 0.0 or dist < cfg.afast_mult * mo:
                i += 1
                continue
            ref = (pd.Timestamp(bt[r]), float(ma), dist, float(mo))

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

        # --- 2) as pontas, congeladas no gatilho cruzado (fade: acima VENDE, abaixo COMPRA) ---
        gat = t_up if cu else t_dn
        acima, abaixo = gat + cfg.k * mo, gat - cfg.k * mo
        lado_acima, lado_abaixo = "sell", "buy"
        if cfg.book == "recuo":
            if cu:
                lado_acima = None
            else:
                lado_abaixo = None
        elif cfg.book == "cont":
            # Só a ponta ALÉM do gatilho. Alcançá-la já prova que o gatilho foi cruzado, e com uma só
            # ordem no book nunca aparece o caso das duas tocadas no mesmo sub-candle.
            if cu:
                lado_abaixo = None
            else:
                lado_acima = None
        elif cfg.book == "acima":
            lado_abaixo = None
        elif cfg.book == "abaixo":
            lado_acima = None
        if cfg.rastrear:
            # Rastrear MM, decidido no gatilho: fechamento da barra FECHADA anterior (i-1) contra a EMA do fechamento
            # dela. Acima da MM só VENDE; abaixo só COMPRA; igual ou sem EMA: não opera. Vale para qualquer book.
            ma = mm[i - 1]
            if np.isnan(ma) or bc[i - 1] == ma:
                i += 1
                continue
            if bc[i - 1] > ma:
                lado_abaixo = None            # só venda (a ordem de venda é sempre a de cima)
            else:
                lado_acima = None             # só compra
        if lado_acima is None and lado_abaixo is None:
            i += 1
            continue

        se = -1
        side = None
        entry = 0.0
        t = tc
        while t < ns and smin[t] < ent_m:
            ta = (lado_acima is not None) and sh[t] >= acima + cfg.penetracao
            tb = (lado_abaixo is not None) and sl[t] <= abaixo - cfg.penetracao
            # No sub-candle do CRUZAMENTO a ponta de RECUO fica DENTRO da zona: o preço alcança aquele nível
            # sem ter cruzado o gatilho. Se o sub-candle já ABRIU além dela, o nível foi tocado antes de a
            # ordem existir (aritmética, não desempate). A ponta segue armada para os sub-candles seguintes.
            # A ponta de CONTINUAÇÃO não precisa do teste: ela fica além do gatilho.
            if t == tc and ((so[t] <= abaixo) if cu else (so[t] >= acima)):
                if cu:
                    tb = False
                else:
                    ta = False
            if ta and tb:                     # as duas no mesmo sub-candle: a abertura decide
                ta = up_sub(t)
                tb = not ta
            if ta or tb:
                se = t
                entry = acima if ta else abaixo
                side = lado_acima if ta else lado_abaixo
                break
            t += 1
        if se < 0:
            break                             # book não resolveu até o fim do pregão

        proximo = cfg.modo_entrada == "proximo_candle"
        if proximo:
            # O sinal (ordem executada no sub-candle `se`) só vira entrada na ABERTURA da barra seguinte, a mercado.
            te = prim.get(spar[se] + 1)
            if te is None or smin[te] >= ent_m:
                break                         # sem barra seguinte, ou a abertura cai na última entrada/depois: o sinal morre
            entry = float(so[te])             # stop e alvo contam a partir da abertura; o custo só entra no preço executado
            entry_fill = fill(entry, side, True, cfg)
            entry_ts = sts[te]
            ent_min = int(smin[te])
            t_ini = te                        # a entrada é no INÍCIO deste sub-candle: ele já conta para a gestão
        else:
            entry_fill = fill(entry, side, False, cfg)   # entrada por ordem limite
            entry_ts = sts[se]
            ent_min = int(smin[se])
            t_ini = se + 1                    # o sub-candle da entrada é imune
        cyc += 1
        n_antes = len(trades)
        sinal = 1.0 if side == "buy" else -1.0            # +1: lucro quando o preço sobe
        acao_saida = close_action(side)
        smult, gmult = cfg.stop_mult, cfg.gain_mult         # a reversão pode trocar os dois (valem até o fim do ciclo)
        revs = 0
        # Trailing (estado por perna): `prot` = stop já conquistado (só aperta); a barra da entrada só conta a partir de `k_ini`.
        prot = None
        trail_on = False
        bar_ant = spar[te] if proximo else spar[se]
        ent_bar = bar_ant
        k_ini = t_ini

        # --- 3) gestão, também por sub-candle ---
        saiu = None
        t = t_ini
        while t < ns:
            if smin[t] >= end_m:              # zeragem (a mercado, na abertura do sub-candle)
                xf = fill(so[t], acao_saida, True, cfg)
                trades.append(make_trade(cyc, side, entry_ts, entry_fill, sts[t], xf, "time_close", cfg, "zeragem", revs))
                saiu = spar[t]
                break
            if cfg.tempo_max > 0 and smin[t] >= ent_min + cfg.tempo_max:      # tempo máximo da perna: a mercado, na abertura
                xf = fill(so[t], acao_saida, True, cfg)
                pts = (xf - entry_fill) if side == "buy" else (entry_fill - xf)
                trades.append(make_trade(cyc, side, entry_ts, entry_fill, sts[t], xf, "gain" if pts > 0 else "loss", cfg, "tempo", revs))
                saiu = spar[t]
                break
            j = spar[t]
            mop = media_op(j) if j >= Wop else 0.0
            if mop <= 0:
                t += 1
                continue
            if cfg.trail_r > 0:
                # proteção atualizada quando uma barra FECHA: a barra b (< j) já fechou quando o sub-candle t (da barra j) abre
                while bar_ant < j:
                    b = bar_ant
                    mb = media_op(b) if b >= Wop else mop
                    lo_b, hi_b = bl[b], bh[b]
                    if b == ent_bar:                  # a barra da entrada: só o que veio depois dela
                        k1 = k_ini
                        while k1 < ns and spar[k1] == b:
                            k1 += 1
                        if k1 > k_ini:
                            lo_b, hi_b = float(sl[k_ini:k1].min()), float(sh[k_ini:k1].max())
                        else:
                            lo_b = hi_b = entry         # nada observado depois da entrada
                    adv = (hi_b - entry) if side == "buy" else (entry - lo_b)
                    if trail_on:                       # segue a mínima/máxima da barra que fechou (só aperta)
                        lvl = lo_b if side == "buy" else hi_b
                        prot = lvl if prot is None else (max(prot, lvl) if side == "buy" else min(prot, lvl))
                    if not trail_on:
                        trail_on = adv >= cfg.trail_r * smult * mb
                    bar_ant += 1
            if side == "buy":
                stop = base_stop = entry - smult * mop
                if prot is not None:
                    stop = max(stop, prot)
                target = entry + gmult * mop
                hit_stop = sl[t] <= stop
                hit_target = sh[t] >= target
            else:
                stop = base_stop = entry + smult * mop
                if prot is not None:
                    stop = min(stop, prot)
                target = entry - gmult * mop
                hit_stop = sh[t] >= stop
                hit_target = sl[t] <= target

            # Saída ao tocar a MM: a MM do fechamento da barra ANTERIOR (j-1), congelada durante a barra j.
            # O caminho do preço vai do fechamento do sub-candle anterior (ou da própria entrada) até o extremo do sub-candle.
            ma = float("nan")
            hit_mm = False
            pref = entry if (proximo and t == t_ini) else float(sc[t - 1])
            if cfg.sair_mm:
                ma = float(mm[j - 1])
                hit_mm = (not np.isnan(ma)) and min(sl[t], pref) <= ma <= max(sh[t], pref)

            if not (hit_stop or hit_target or hit_mm):
                t += 1
                continue

            # Mais de um evento no mesmo sub-candle: pessimista. Lado adverso do preço antes do lado a favor; no mesmo
            # lado, o nível mais próximo do preço primeiro (empate: stop, MM, alvo). Chave = (a favor?, distância, ordem).
            eventos = []
            if hit_stop:
                eventos.append((False, max(0.0, -sinal * (stop - pref)), 0, "stop"))
            if hit_mm:
                d = sinal * (ma - pref)
                eventos.append((d > 0, abs(d), 1, "mm"))
            if hit_target:
                eventos.append((True, max(0.0, sinal * (target - pref)), 2, "alvo"))
            quem = min(eventos)[3]

            if quem == "stop":
                lvl = gap_level(stop, so[t], acao_saida)
                xf = fill(lvl, acao_saida, True, cfg)
                pts = (xf - entry_fill) if side == "buy" else (entry_fill - xf)
                via_trail = prot is not None and ((side == "buy" and prot > base_stop) or (side == "sell" and prot < base_stop))
                trades.append(make_trade(cyc, side, entry_ts, entry_fill, sts[t], xf,
                                         "gain" if pts > 0 else "loss", cfg, "trailing" if via_trail else "stop", revs))
                dia_perdido = cfg.parar_dia_x > 0 and sum(t_.pts for t_ in trades) <= -cfg.parar_dia_x * mop
                if pts <= 0 and revs < cfg.max_rev and not dia_perdido:   # STOP-AND-REVERSE no preço do stop (lado oposto, a mercado)
                    revs += 1
                    if cfg.rev_stop_mult > 0:
                        smult = cfg.rev_stop_mult
                    if cfg.rev_gain_mult > 0:
                        gmult = cfg.rev_gain_mult
                    side = "sell" if side == "buy" else "buy"
                    entry = float(lvl)
                    entry_fill = fill(entry, side, True, cfg)
                    entry_ts = sts[t]
                    ent_min = int(smin[t])
                    sinal = -sinal
                    acao_saida = close_action(side)
                    prot = None                       # a reversão começa sem proteção; o relógio da barra da entrada recomeça
                    trail_on = False
                    bar_ant = ent_bar = spar[t]
                    k_ini = t + 1
                    t += 1                            # o sub-candle da reversão é imune
                    continue
            elif quem == "mm":                # a mercado, no nível da MM; contra a posição e abrindo além dela: abertura (gap)
                contra = sinal * (ma - pref) <= 0
                lvl = gap_level(ma, so[t], acao_saida) if contra else ma
                xf = fill(lvl, acao_saida, True, cfg)
                pts = (xf - entry_fill) if side == "buy" else (entry_fill - xf)
                trades.append(make_trade(cyc, side, entry_ts, entry_fill, sts[t], xf,
                                         "gain" if pts > 0 else "loss", cfg, "mm", revs))
            else:                             # alvo = ordem limite, preenche no nível
                xf = fill(target, acao_saida, False, cfg)
                trades.append(make_trade(cyc, side, entry_ts, entry_fill, sts[t], xf, "gain", cfg, "alvo", revs))
            saiu = spar[t]
            break
        if saiu is None:                      # fim dos dados com posição aberta
            x = ns - 1
            xf = fill(sc[x], acao_saida, True, cfg)
            trades.append(make_trade(cyc, side, entry_ts, entry_fill, sts[x], xf, "eod", cfg, "fim_dados", revs))
            saiu = spar[x]
        if ref is not None:                   # registra o que o filtro viu (candle de referência), para conferência
            for tr in trades[n_antes:]:
                tr.ref_barra, tr.ref_mm, tr.ref_afast, tr.media_op = ref
        i = saiu + 1
    return aplicar_escada(trades, cfg)
