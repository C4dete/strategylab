"""Consolidação dos resultados: por pregão, por mês, drawdown e sequências.

Todas as contas são feitas sobre o fechamento de cada pregão (curva de capital diária).
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .fills import Trade

_TRADE_COLS = ["data", "ciclo", "lado", "entrada_ts", "preco_entrada", "saida_ts", "preco_saida",
               "contratos", "pts", "rs", "desfecho", "saida_por", "reversao", "ref_barra", "ref_mm", "ref_afast", "media_op"]
_DIARIO_COLS = ["data", "operacoes", "ganhos", "perdas", "zeradas", "pts", "rs", "acumulado"]


def trades_para_df(trades: List[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=_TRADE_COLS)
    df = pd.DataFrame([{
        "ciclo": t.ciclo, "lado": t.lado, "entrada_ts": t.entrada_ts, "preco_entrada": t.preco_entrada,
        "saida_ts": t.saida_ts, "preco_saida": t.preco_saida, "contratos": t.contratos,
        "pts": t.pts, "rs": t.rs, "desfecho": t.desfecho, "saida_por": t.saida_por, "reversao": t.reversao,
        "ref_barra": t.ref_barra, "ref_mm": t.ref_mm, "ref_afast": t.ref_afast, "media_op": t.media_op,
    } for t in trades])
    df["data"] = pd.to_datetime(df["entrada_ts"]).dt.date
    return df[_TRADE_COLS]


def resumo_diario(trades: pd.DataFrame) -> pd.DataFrame:
    """Um registro por pregão COM operação + curva acumulada."""
    if trades.empty:
        return pd.DataFrame(columns=_DIARIO_COLS)
    t = trades.assign(
        _g=(trades["desfecho"] == "gain"),
        _l=(trades["desfecho"] == "loss"),
        _z=trades["desfecho"].isin(["eod", "time_close"]),
    )
    d = (t.groupby("data", sort=True)
         .agg(operacoes=("desfecho", "size"), ganhos=("_g", "sum"), perdas=("_l", "sum"),
              zeradas=("_z", "sum"), pts=("pts", "sum"), rs=("rs", "sum"))
         .reset_index())
    for c in ("operacoes", "ganhos", "perdas", "zeradas"):
        d[c] = d[c].astype(int)
    d = d.sort_values("data").reset_index(drop=True)
    d["acumulado"] = d["rs"].cumsum()
    return d[_DIARIO_COLS]


def drawdown(diario: pd.DataFrame) -> dict:
    """Maior queda do topo ao fundo da curva diária (no fechamento de cada pregão)."""
    vazio = {"rs": 0.0, "pts": 0.0, "pico": None, "fundo": None, "pregoes": 0}
    if diario.empty:
        return vazio
    d = diario.sort_values("data").reset_index(drop=True)
    eq = d["rs"].cumsum()
    dd = eq - eq.cummax()
    i = int(dd.idxmin())
    if float(dd.iloc[i]) >= 0:
        return vazio
    j = int(eq.iloc[:i + 1].idxmax())          # o topo é o último máximo da curva até o fundo
    eqp = d["pts"].cumsum()
    return {
        "rs": float(dd.iloc[i]),
        "pts": float((eqp - eqp.cummax()).min()),
        "pico": d.loc[j, "data"],
        "fundo": d.loc[i, "data"],
        "pregoes": int(i - j),
    }


def sequencias(diario: pd.DataFrame) -> dict:
    """Maior sequência de pregões consecutivos ganhando e perdendo (empate desfeito pelo valor)."""
    res = {"ganho": None, "perda": None}
    if diario.empty:
        return res
    d = diario.sort_values("data").reset_index(drop=True).copy()
    d["_sinal"] = np.sign(d["rs"])
    grp = (d["_sinal"] != d["_sinal"].shift()).cumsum()
    runs = d.groupby(grp).agg(sinal=("_sinal", "first"), dias=("rs", "size"), total=("rs", "sum"),
                              inicio=("data", "first"), fim=("data", "last"))

    def pick(sub: pd.DataFrame, maior_valor: bool):
        if sub.empty:
            return None
        cand = sub[sub["dias"] == sub["dias"].max()]
        row = cand.loc[cand["total"].idxmax()] if maior_valor else cand.loc[cand["total"].idxmin()]
        return {"dias": int(row["dias"]), "total": float(row["total"]),
                "inicio": row["inicio"], "fim": row["fim"]}

    res["ganho"] = pick(runs[runs["sinal"] > 0], True)
    res["perda"] = pick(runs[runs["sinal"] < 0], False)
    return res


def resumo_mensal(diario: pd.DataFrame) -> pd.DataFrame:
    cols = ["mes", "rs", "pts", "dias", "dias_positivos"]
    if diario.empty:
        return pd.DataFrame(columns=cols)
    d = diario.copy()
    d["mes"] = pd.to_datetime(d["data"]).dt.strftime("%Y-%m")
    m = d.groupby("mes").agg(rs=("rs", "sum"), pts=("pts", "sum"), dias=("rs", "size"),
                             dias_positivos=("rs", lambda s: int((s > 0).sum()))).reset_index()
    return m[cols].sort_values("mes").reset_index(drop=True)


def metricas_globais(diario: pd.DataFrame) -> dict:
    if diario.empty:
        return {"total_rs": 0.0, "total_pts": 0.0, "pregoes": 0, "operacoes": 0, "ganhos": 0,
                "perdas": 0, "zeradas": 0, "win_rate": 0.0, "melhor_dia": None, "pior_dia": None,
                "drawdown": drawdown(diario), "sequencias": sequencias(diario)}
    ganhos, perdas = int(diario["ganhos"].sum()), int(diario["perdas"].sum())
    fechadas = ganhos + perdas
    i_melhor, i_pior = diario["rs"].idxmax(), diario["rs"].idxmin()
    return {
        "total_rs": float(diario["rs"].sum()),
        "total_pts": float(diario["pts"].sum()),
        "pregoes": int(len(diario)),
        "operacoes": int(diario["operacoes"].sum()),
        "ganhos": ganhos,
        "perdas": perdas,
        "zeradas": int(diario["zeradas"].sum()),
        "win_rate": (ganhos / fechadas * 100.0) if fechadas else 0.0,
        "melhor_dia": {"data": diario.loc[i_melhor, "data"], "rs": float(diario.loc[i_melhor, "rs"])},
        "pior_dia": {"data": diario.loc[i_pior, "data"], "rs": float(diario.loc[i_pior, "rs"])},
        "drawdown": drawdown(diario),
        "sequencias": sequencias(diario),
    }
