"""Helper de pesquisa (ver docs/analise_v6_antiga.md): roda o motor ANTIGO ghostcandle_v6 (base_conhecimento, só leitura) em cima do BD do projeto (até 2025).

Não grava nada no projeto. Uso: importar `rodar(**overrides)`; devolve (trades_df, métricas).
"""
from __future__ import annotations

import sys
from datetime import date, time
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "base_conhecimento"))

import numpy as np                                                              # noqa: E402
import pandas as pd                                                             # noqa: E402
from ghostcandle.backtest import run_backtest                                   # noqa: E402
from ghostcandle.io_csv import load_candles, resample_ohlc                      # noqa: E402
from ghostcandle.strategies import params_from                                  # noqa: E402

LIMITE = date(2025, 12, 31)
PRESET = "ghostcandle_v6_10min (sem ORB/VWAP)"
CSV = RAIZ / "dados" / "WIN_1M_21_25.csv"

_bruto = load_candles(str(CSV))
assert _bruto["datetime"].max().date() <= LIMITE, "BD passa de 2025 - recusado (hold-out do Ricardo)"
BARRAS = resample_ohlc(_bruto, 10, sub_minutes=1)

PERFIL = dict(contracts=1, point_value=0.20, entry_order="limit", indicators_timing="closed", entry_bar_risk=True,
              slippage_pts=5.0, spread_pts=5.0, tick_size=5.0, indicators_mode="continuous",
              start_time=time(9, 0), end_time=time(17, 30))


def rodar(barras=None, **ov):
    kw = dict(PERFIL)
    kw.update(ov)
    p = params_from(PRESET, **kw)
    _, tr = run_backtest(BARRAS if barras is None else barras, p)
    return tr


def diario(tr: pd.DataFrame) -> pd.Series:
    if tr.empty:
        return pd.Series(dtype=float)
    d = tr.copy()
    d["dia"] = pd.to_datetime(d["exit_time"]).dt.date
    return d.groupby("dia")["result_rs"].sum()


def metricas(tr: pd.DataFrame, de=None, ate=None) -> dict:
    if tr.empty:
        return dict(total=0.0, dd=0.0, ret_dd=0.0, n=0, ganho=np.nan, meses_pos=0, meses=0, pior_mes=0.0)
    d = tr.copy()
    d["dia"] = pd.to_datetime(d["exit_time"]).dt.date
    if de:
        d = d[d["dia"] >= pd.Timestamp(de).date()]
    if ate:
        d = d[d["dia"] <= pd.Timestamp(ate).date()]
    if d.empty:
        return dict(total=0.0, dd=0.0, ret_dd=0.0, n=0, ganho=np.nan, meses_pos=0, meses=0, pior_mes=0.0)
    s = d.groupby("dia")["result_rs"].sum()
    eq = s.cumsum()
    dd = float((eq - eq.cummax().clip(lower=0)).min())
    m = d.assign(m=pd.to_datetime(d["dia"]).dt.to_period("M")).groupby("m")["result_rs"].sum()
    tot = float(s.sum())
    return dict(total=tot, dd=dd, ret_dd=(tot / abs(dd) if dd else np.inf), n=len(d), ganho=float((d["result_rs"] > 0).mean()),
                meses_pos=int((m > 0).sum()), meses=len(m), pior_mes=float(m.min()))


def por_ano(tr: pd.DataFrame) -> dict:
    if tr.empty:
        return {}
    d = tr.copy()
    d["ano"] = pd.to_datetime(d["exit_time"]).dt.year
    return {int(a): round(float(v)) for a, v in d.groupby("ano")["result_rs"].sum().items()}
