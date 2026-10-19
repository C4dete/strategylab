"""Orquestra um backtest: parâmetros -> motor por pregão -> métricas (tudo JSON-ready)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .ghost import Cfg, Ctx, DiaPrep, preparar_dia, run_day_prep
from .indicators import bollinger, ema
from .metrics import (metricas_globais, resumo_diario, resumo_mensal, trades_para_df)
from .params import EXECUCAO, Params, hhmm_para_min

_DESFECHOS = {"gain", "loss", "time_close", "eod"}


def montar_cfg(p: Params, sub_min: int) -> Cfg:
    fim = hhmm_para_min(p.janela_fim)
    ult = hhmm_para_min(p.ultima_entrada) if p.ultima_entrada else fim
    return Cfg(
        inicio_min=hhmm_para_min(p.janela_inicio),
        fim_min=fim,
        ult_entrada_min=ult,
        n_zona=p.candles_gatilho,
        n_media=p.candles_media,
        k=p.bracket_fracao,
        book=p.book,
        penetracao=p.penetracao_ticks * EXECUCAO.tick_pts,
        parar_n=p.parar_apos_losses,
        parar_modo=p.contagem_losses,
        max_ops=p.operacoes_por_dia,
        stop_mult=p.stop_x_media,
        gain_mult=p.alvo_x_media,
        sub_min=sub_min,
        slippage=EXECUCAO.slippage_pts,
        spread=EXECUCAO.spread_pts,
        tick=EXECUCAO.tick_pts,
        valor_ponto=EXECUCAO.valor_ponto,
        contratos=EXECUCAO.contratos,
        afast_ativo=p.filtro_afast_mm_ativo,
        afast_mult=p.filtro_afast_mm_x_media,
        modo_entrada=p.modo_entrada,
        sair_mm=p.sair_ao_tocar_mm,
        rastrear=p.rastrear_mm,
        max_rev=p.reversoes,
        rev_stop_mult=p.rev_stop_x_media,
        rev_gain_mult=p.rev_alvo_x_media,
        parar_dia_x=p.parar_dia_perda_x_media,
        tempo_max=p.tempo_max_min,
        gap_ativo=p.filtro_gap_ativo,
        gap_max=p.filtro_gap_max_x_media,
        vol_ativo=p.filtro_vol_ontem_ativo,
        vol_max=p.filtro_vol_ontem_max,
        bb_ativo=p.filtro_bb_ativo,
        bb_min=p.filtro_bb_largura_min_pct,
        bb_max=p.filtro_bb_largura_max_pct,
        incl_ativo=p.filtro_inclinacao_ativo,
        incl_max=p.filtro_inclinacao_max_x_media,
        escada_ini=p.escada_contratos,
        escada_ganho=p.escada_ganho_acao,
        escada_ganho_qtd=p.escada_ganho_qtd,
        escada_perda=p.escada_perda_acao,
        escada_perda_qtd=p.escada_perda_qtd,
        escada_min=p.escada_min,
        escada_max=p.escada_max,
        trail_r=p.trailing_inicio_r,
        descarte_x=p.filtro_candle_discrepante_x if p.filtro_candle_discrepante_ativo else 0.0,
    )


@dataclass
class Mercado:
    """O BD já preparado para o motor: cada pregão pré-processado (independente dos parâmetros) + a EMA do fechamento
    por período, em cache. Construído uma vez por BD e reaproveitado em todas as execuções (app e laboratório)."""

    sub_min: int
    dias: list                                   # [(data, inicio, fim, DiaPrep)]: fatia [inicio, fim) das barras de cada pregão
    close: np.ndarray                            # fechamento de TODAS as barras, em série contínua (atravessa os pregões)
    feat: dict = field(default_factory=dict)       # {data: (gap, vol de ontem)}: medidas de regime do dia, só com dias anteriores
    _mm: dict = field(default_factory=dict, repr=False)
    _bb: dict = field(default_factory=dict, repr=False)
    _slope: dict = field(default_factory=dict, repr=False)

    def mm(self, periodo: int) -> np.ndarray:
        """EMA(periodo) no fechamento de cada barra, sobre a série contínua inteira (a mesma conta de sempre)."""
        achou = self._mm.get(periodo)
        if achou is None:
            achou = ema(self.close, periodo)
            self._mm[periodo] = achou
        return achou


    def bbw(self, periodo: int, k: float) -> np.ndarray:
        """Largura das Bandas de Bollinger (superior - inferior) em % da linha central, no fechamento de cada barra."""
        chave = (int(periodo), round(float(k), 4))
        achou = self._bb.get(chave)
        if achou is None:
            mid, sup, inf = bollinger(self.close, periodo, k)
            with np.errstate(divide="ignore", invalid="ignore"):
                achou = (sup - inf) / mid * 100.0
            self._bb[chave] = achou
        return achou

    def slope(self, periodo: int, barras: int) -> np.ndarray:
        """MM[t] - MM[t - barras], em pontos (NaN nas primeiras `barras` posições)."""
        chave = (int(periodo), int(barras))
        achou = self._slope.get(chave)
        if achou is None:
            mm = self.mm(periodo)
            achou = np.full_like(mm, np.nan)
            achou[barras:] = mm[barras:] - mm[:-barras]
            self._slope[chave] = achou
        return achou


def preparar_mercado(barras: pd.DataFrame, sub_min: int) -> Mercado:
    dias, pos = [], 0
    resumo = []                                   # (data, abertura, máxima, mínima, fechamento) de TODOS os pregões, em ordem
    for data, dia in barras.groupby("date", sort=True):
        dia = dia.sort_values("datetime").reset_index(drop=True)
        n = len(dia)
        resumo.append((data, float(dia["open"].iloc[0]), float(dia["high"].max()), float(dia["low"].min()), float(dia["close"].iloc[-1])))
        dp = preparar_dia(dia, sub_min)
        if dp is not None:
            dias.append((data, pos, pos + n, dp))
        pos += n
    # Medidas de regime do dia, SÓ com dias anteriores + a abertura de hoje (conhecidas às 09:00). Menos de 20 dias de história = NaN.
    amp = np.array([h - l for _, _, h, l, _ in resumo])
    feat = {}
    for k, (data, ab, _, _, _) in enumerate(resumo):
        base_gap = amp[k - 20:k].mean() if k >= 20 else np.nan                     # os 20 pregões anteriores a hoje
        gap = abs(ab - resumo[k - 1][4]) / base_gap if k >= 1 and base_gap > 0 else np.nan
        base_vol = amp[k - 21:k - 1].mean() if k >= 21 else np.nan                 # os 20 anteriores a ONTEM
        volp = amp[k - 1] / base_vol if k >= 1 and base_vol > 0 else np.nan
        feat[data] = (float(gap), float(volp))
    return Mercado(sub_min=sub_min, dias=dias, close=barras["close"].to_numpy(float), feat=feat)


def rodar_trades(barras: Optional[pd.DataFrame], p: Params, sub_min: int, mercado: Optional[Mercado] = None) -> pd.DataFrame:
    """Só o motor: DataFrame de trades (uma linha por operação), com a coluna `data`.

    Com `mercado` (BD já preparado) não relê as barras: é o caminho do laboratório e do app. Sem ele, prepara na hora.
    """
    if mercado is None:
        mercado = preparar_mercado(barras, sub_min)
    cfg = montar_cfg(p, mercado.sub_min)
    # EMA no fechamento de cada barra, sobre a série contínua inteira (atravessa os pregões).
    # O motor só lê a posição i-1 ao decidir na barra i (e mm[j-1] ao sair na barra j).
    mm = mercado.mm(p.mm_periodo) if (cfg.afast_ativo or cfg.sair_mm or cfg.rastrear) else None
    bbw = mercado.bbw(p.bb_periodo, p.bb_desvio) if cfg.bb_ativo else None
    slope = mercado.slope(p.mm_periodo, p.filtro_inclinacao_barras) if cfg.incl_ativo else None
    usa_ctx = cfg.bb_ativo or cfg.incl_ativo or cfg.gap_ativo or cfg.vol_ativo
    nan = float("nan")
    todos = []
    for data, ini, fim, dp in mercado.dias:
        ctx = None
        if usa_ctx:
            gap, volp = mercado.feat.get(data, (nan, nan))
            ctx = Ctx(bbw=None if bbw is None else bbw[ini:fim], slope=None if slope is None else slope[ini:fim], gap=gap, volp=volp)
        todos.extend(run_day_prep(dp, cfg, None if mm is None else mm[ini:fim], ctx))
    return trades_para_df(todos)


def _dia(d) -> Optional[str]:
    return None if d is None else str(d)


def _num(v) -> Optional[float]:
    return None if v is None or v != v else float(v)       # NaN -> null no JSON


def executar(barras: Optional[pd.DataFrame], p: Params, sub_min: int, mercado: Optional[Mercado] = None) -> dict:
    """Roda o backtest completo e devolve o resultado em tipos JSON."""
    t0 = time.perf_counter()
    trades = rodar_trades(barras, p, sub_min, mercado)
    diario = resumo_diario(trades)
    g = metricas_globais(diario)
    mensal = resumo_mensal(diario)

    dd = g["drawdown"]
    seq = g["sequencias"]

    def _seq(s):
        return None if s is None else {"dias": s["dias"], "total": s["total"],
                                       "inicio": _dia(s["inicio"]), "fim": _dia(s["fim"])}

    def _dia_rs(x):
        return None if x is None else {"data": _dia(x["data"]), "rs": x["rs"]}

    resumo = {
        "total_rs": g["total_rs"], "total_pts": g["total_pts"],
        "pregoes_operados": g["pregoes"], "operacoes": g["operacoes"],
        "ganhos": g["ganhos"], "perdas": g["perdas"], "zeradas": g["zeradas"],
        "win_rate": g["win_rate"],
        "drawdown": {"rs": dd["rs"], "pts": dd["pts"], "pico": _dia(dd["pico"]),
                     "fundo": _dia(dd["fundo"]), "pregoes": dd["pregoes"]},
        "melhor_dia": _dia_rs(g["melhor_dia"]),
        "pior_dia": _dia_rs(g["pior_dia"]),
        "seq_ganho": _seq(seq["ganho"]),
        "seq_perda": _seq(seq["perda"]),
    }

    bar = EXECUCAO.timeframe_min
    ops = []
    for r in trades.itertuples(index=False):
        e, s = pd.Timestamp(r.entrada_ts), pd.Timestamp(r.saida_ts)
        ops.append({
            "data": str(r.data), "ciclo": int(r.ciclo), "lado": r.lado,
            "entrada": e.strftime("%H:%M"), "entrada_barra": e.floor(f"{bar}min").strftime("%H:%M"),
            "preco_entrada": float(r.preco_entrada),
            "saida": s.strftime("%H:%M"), "saida_barra": s.floor(f"{bar}min").strftime("%H:%M"),
            "preco_saida": float(r.preco_saida),
            "contratos": int(r.contratos), "pts": float(r.pts), "rs": float(r.rs),
            "desfecho": r.desfecho if r.desfecho in _DESFECHOS else "eod",
            "saida_por": r.saida_por, "reversao": int(r.reversao),
            "ref": None if r.ref_barra is None or r.ref_barra != r.ref_barra else {
                "barra": pd.Timestamp(r.ref_barra).strftime("%H:%M"),
                "mm": _num(r.ref_mm), "afast_pts": _num(r.ref_afast),
                "afast_x": _num(r.ref_afast / r.media_op) if r.media_op and r.media_op == r.media_op else None,
            },
        })

    return {
        "resumo": resumo,
        "diario": [{"data": str(r.data), "rs": float(r.rs), "pts": float(r.pts),
                    "acumulado": float(r.acumulado), "operacoes": int(r.operacoes),
                    "ganhos": int(r.ganhos), "perdas": int(r.perdas)}
                   for r in diario.itertuples(index=False)],
        "mensal": [{"mes": r.mes, "rs": float(r.rs), "pts": float(r.pts), "dias": int(r.dias),
                    "dias_positivos": int(r.dias_positivos)} for r in mensal.itertuples(index=False)],
        "operacoes": ops,
        "tempo_ms": int((time.perf_counter() - t0) * 1000),
    }
