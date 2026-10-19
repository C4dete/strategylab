"""Métricas de uma combinação, calculadas com as MESMAS funções do app (`resumo_diario`, `metricas_globais`).

Só acrescenta o que o app não mostra e a metodologia de testes pede: Ret/DD, soma dos 20 piores dias, resultado por ano e a
separação IS × OOS e, opcionalmente, o resultado dentro de JANELAS de tempo nomeadas (treino/teste de uma busca walk-forward).
As janelas só recortam os trades por data: cada pregão é independente e a EMA só usa o passado, então o resultado de uma janela
não depende do que vem depois dela.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ..engine.metrics import metricas_globais, resumo_diario


def _dd(diario: pd.DataFrame) -> float:
    if diario.empty:
        return 0.0
    eq = diario.sort_values("data")["rs"].cumsum()
    return float((eq - eq.cummax()).min())


def _ret_dd(total: float, dd: float) -> float:
    return float(total / abs(dd)) if dd < 0 else float("nan")


def _janela(diario: pd.DataFrame, meses_bd: Optional[list], ini: str, fim: str) -> dict:
    """Métricas dos pregões em [ini, fim] (datas AAAA-MM-DD, inclusive). Meses da janela = meses do BD entre ini[:7] e fim[:7]."""
    d = diario[(pd.to_datetime(diario["data"]) >= pd.Timestamp(ini)) & (pd.to_datetime(diario["data"]) <= pd.Timestamp(fim))]
    total, dd = float(d["rs"].sum()), _dd(d)
    out = {"total_rs": total, "dd_rs": dd, "ret_dd": _ret_dd(total, dd), "operacoes": int(d["operacoes"].sum()), "pregoes": int(len(d))}
    meses = [m for m in (meses_bd or []) if ini[:7] <= m <= fim[:7]]
    if meses:
        mes = d.groupby(pd.to_datetime(d["data"]).dt.strftime("%Y-%m"))["rs"].sum().reindex(meses).fillna(0.0)
        out.update(meses_total=len(meses), meses_pos=int((mes > 0).sum()), meses_neg=int((mes < 0).sum()), pior_mes=float(mes.min()))
    return out


def metricas(trades: pd.DataFrame, corte_oos: Optional[str] = None, meses_bd: Optional[list] = None,
             janelas: Optional[dict] = None) -> dict:
    diario = resumo_diario(trades)
    g = metricas_globais(diario)
    out = {
        "operacoes": g["operacoes"],
        "ciclos": int(trades.groupby(["data", "ciclo"]).ngroups) if len(trades) else 0,
        "pregoes": g["pregoes"],
        "total_rs": g["total_rs"],
        "total_pts": g["total_pts"],
        "dd_rs": g["drawdown"]["rs"],
        "dd_pregoes": g["drawdown"]["pregoes"],
        "win_rate": g["win_rate"],
        "ganhos": g["ganhos"],
        "perdas": g["perdas"],
        "zeradas": g["zeradas"],
        "melhor_dia": g["melhor_dia"]["rs"] if g["melhor_dia"] else 0.0,
        "pior_dia": g["pior_dia"]["rs"] if g["pior_dia"] else 0.0,
    }
    out["ret_dd"] = _ret_dd(out["total_rs"], out["dd_rs"])
    if janelas:
        for nome in janelas:
            out.update({f"{nome}_{k}": 0 for k in ("total_rs", "dd_rs", "operacoes", "pregoes", "meses_pos", "meses_neg", "pior_mes")})
    if diario.empty:
        out.update(meses_total=len(meses_bd or []), meses_pos=0, meses_neg=0, pior_mes=0.0, melhor_mes=0.0,
                   soma_20_piores=0.0, meses_pos_pct=float("nan"), anos_pos=0, anos=0, is_rs=0.0, oos_rs=0.0,
                   oos_dd=0.0, oos_ret_dd=float("nan"), oos_operacoes=0, por_ano={})
        return out
    d = diario.assign(_t=pd.to_datetime(diario["data"]))
    out["soma_20_piores"] = float(d["rs"].nsmallest(20).sum())
    mes = d.groupby(d["_t"].dt.strftime("%Y-%m"))["rs"].sum()
    out["meses_pos_pct"] = float((mes > 0).mean() * 100.0)
    ano = d.groupby(d["_t"].dt.year)["rs"].sum()
    if meses_bd:                                       # meses do BD inteiro: mês sem operação NÃO conta como positivo
        mes_bd = mes.reindex(meses_bd).fillna(0.0)
        out["meses_total"] = len(meses_bd)
        out["meses_pos"] = int((mes_bd > 0).sum())
        out["meses_neg"] = int((mes_bd < 0).sum())
        out["pior_mes"] = float(mes_bd.min())
        out["melhor_mes"] = float(mes_bd.max())
    if meses_bd:
        out["por_mes"] = {m: float(v) for m, v in mes.reindex(meses_bd).fillna(0.0).items()}
    for nome, (ini, fim) in (janelas or {}).items():
        out.update({f"{nome}_{k}": v for k, v in _janela(diario, meses_bd, ini, fim).items()})
    out["por_ano"] = {int(a): float(v) for a, v in ano.items()}
    out["anos_pos"] = int((ano > 0).sum())
    out["anos"] = int(len(ano))
    if corte_oos:
        corte = pd.Timestamp(corte_oos)
        antes, depois = d[d["_t"] < corte], d[d["_t"] >= corte]
        out["is_rs"] = float(antes["rs"].sum())
        out["oos_rs"] = float(depois["rs"].sum())
        out["oos_dd"] = _dd(depois)
        out["oos_ret_dd"] = _ret_dd(out["oos_rs"], out["oos_dd"])
        out["oos_operacoes"] = int(depois["operacoes"].sum())
    else:
        out.update(is_rs=float("nan"), oos_rs=float("nan"), oos_dd=float("nan"), oos_ret_dd=float("nan"), oos_operacoes=0)
    return out


COLUNAS = ["operacoes", "ciclos", "pregoes", "total_rs", "total_pts", "dd_rs", "dd_pregoes", "ret_dd", "win_rate", "ganhos",
           "perdas", "zeradas", "melhor_dia", "pior_dia", "soma_20_piores", "meses_pos_pct", "meses_total", "meses_pos", "meses_neg", "pior_mes", "melhor_mes", "anos_pos", "anos",
           "is_rs", "oos_rs", "oos_dd", "oos_ret_dd", "oos_operacoes"]
