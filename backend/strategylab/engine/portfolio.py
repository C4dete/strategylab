"""Resultado CONJUNTO de várias estratégias ("Correlacionar").

O conjunto é a SOMA, pregão a pregão, de backtests independentes: cada estratégia roda como se estivesse sozinha (seus
próprios limites, custo cheio, nada de netting entre elas). Na conta real, posições opostas no mesmo ativo se compensam e
dividem margem; isto não é modelado aqui. Função pura: recebe os resultados já calculados (`executar`) e não toca no motor.

O primeiro componente é a estratégia principal ("A"): a correlação de cada uma é medida contra ela.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

import numpy as np
import pandas as pd

from .metrics import resumo_mensal
from .runner import diario_json, mensal_json, resumo_json

LIMITE_COMPONENTES = 12
_SOMAS = ["operacoes", "ganhos", "perdas", "zeradas", "pts", "rs"]


def pearson(a: Iterable[float], b: Iterable[float]) -> Optional[float]:
    """Correlação de Pearson; `None` quando uma das séries é constante (indefinida) ou não há dados."""
    x, y = np.asarray(list(a), dtype=float), np.asarray(list(b), dtype=float)
    if x.size < 2 or x.size != y.size or x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _diario_df(res: dict) -> pd.DataFrame:
    d = pd.DataFrame(res["diario"], columns=["data", "rs", "pts", "acumulado", "operacoes", "ganhos", "perdas"])
    d = d.astype({"rs": float, "pts": float, "acumulado": float, "operacoes": int, "ganhos": int, "perdas": int})    # vazio não vira `object`
    d["data"] = pd.to_datetime(d["data"]).dt.date
    d["zeradas"] = d["operacoes"] - d["ganhos"] - d["perdas"]          # desfechos: gain, loss, time_close, eod
    return d


def combinar(componentes: List[dict], datas_bd: Iterable, meses_bd: Iterable[str]) -> dict:
    """`componentes`: `[{"nome": str, "res": <saída de executar>}]`, principal primeiro. Devolve o formato do backtest + os campos do conjunto."""
    if not componentes:
        raise ValueError("O conjunto precisa de ao menos uma estratégia.")
    n = len(componentes)
    quadros = [_diario_df(c["res"]) for c in componentes]

    todos = pd.concat(quadros, ignore_index=True)
    comb = (todos.groupby("data", sort=True)[_SOMAS].sum().reset_index() if not todos.empty
            else pd.DataFrame(columns=["data", *_SOMAS]))
    for c in ("operacoes", "ganhos", "perdas", "zeradas"):
        comb[c] = comb[c].astype(int)
    comb["acumulado"] = comb["rs"].cumsum()
    comb = comb[["data", "operacoes", "ganhos", "perdas", "zeradas", "pts", "rs", "acumulado"]]

    datas = list(comb["data"])
    rs_por_dia = np.vstack([q.set_index("data")["rs"].reindex(datas).fillna(0.0).to_numpy() for q in quadros]) if datas \
        else np.zeros((n, 0))
    diario = diario_json(comb)
    for i, linha in enumerate(diario):
        linha["rs_por"] = [float(rs_por_dia[k, i]) for k in range(n)]

    mensal_c = resumo_mensal(comb, meses_bd=meses_bd)
    por_mes = [{m["mes"]: m["rs"] for m in c["res"]["mensal"]} for c in componentes]
    mensal = mensal_json(mensal_c)
    for m in mensal:
        m["rs_por"] = [float(pm.get(m["mes"], 0.0)) for pm in por_mes]

    ops = []
    for i, c in enumerate(componentes):
        ops.extend({**o, "estrategia": i} for o in c["res"]["operacoes"])
    ops.sort(key=lambda o: (o["data"], o["entrada"], o["estrategia"]))

    # correlação do R$ diário contra a principal, sobre TODOS os pregões do BD (zero onde a estratégia não operou)
    calendario = sorted(set(datas_bd) | set(datas))
    serie = [q.set_index("data")["rs"].reindex(calendario).fillna(0.0).to_numpy() for q in quadros]
    estrategias = []
    for i, c in enumerate(componentes):
        r = c["res"]["resumo"]
        estrategias.append({
            "indice": i, "nome": c["nome"],
            "total_rs": r["total_rs"], "total_pts": r["total_pts"], "operacoes": r["operacoes"],
            "pregoes_operados": r["pregoes_operados"], "win_rate": r["win_rate"],
            "drawdown": {"rs": r["drawdown"]["rs"], "pts": r["drawdown"]["pts"]},
            "correlacao_principal": None if i == 0 else pearson(serie[0], serie[i]),
        })

    resumo = resumo_json(comb)
    return {
        "resumo": resumo,
        "diario": diario,
        "mensal": mensal,
        "operacoes": ops,
        "estrategias": estrategias,
        "diversificacao": {"dd_conjunto": resumo["drawdown"]["rs"],
                           "soma_dd_isolados": float(sum(e["drawdown"]["rs"] for e in estrategias))},
        "tempo_ms": int(sum(c["res"]["tempo_ms"] for c in componentes)),
    }
