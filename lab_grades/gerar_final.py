"""Seleção FINAL (treino = todos os dados até 2025): candidatas por Ret/DD e Sharpe mensal + vizinhos, para o platô.

    python lab_grades/gerar_final.py <resultados_walkforward.csv> <saida_grade.json> <saida_mapa.json> [N_por_criterio]

Mesmo método validado no walk-forward; só a janela de treino muda (2021-09..2025-12). Reaproveita o menu de `gerar_plato.py`.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# reaproveita MENU/params_da_linha/normalizar/vizinhos de gerar_plato.py sem executar o resto do script
fonte = (Path(__file__).parent / "gerar_plato.py").read_text(encoding="utf-8")
trecho = fonte[fonte.index("MENU = {"):fonte.index("def bases_do_fold")]
exec(trecho, globals())  # noqa: S102 - código do próprio projeto

csv, saida, saida_mapa = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 25
df = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig")
df = df[df.status == "ok"].copy()
mcols = sorted(c for c in df.columns if c.startswith("m_"))
assert max(c[2:] for c in mcols) <= "2025-12", "há meses depois de 2025 no BD!"

t = df[(df.operacoes >= 150) & (df.total_rs > 0)].copy()
mm = t[mcols]
t["sharpe_mes"] = mm.mean(axis=1) / mm.std(axis=1).replace(0, np.nan)
bases = pd.concat([t.sort_values("ret_dd", ascending=False).head(N), t.sort_values("sharpe_mes", ascending=False).head(N)]).drop_duplicates("id")
print(len(bases), "bases", file=sys.stderr)

variantes, mapa = [], []
for _, r in bases.iterrows():
    base = normalizar(params_da_linha(r))
    vistos = {json.dumps(base, sort_keys=True)}
    variantes.append(base)
    mapa.append({"base_id": int(r["id"]), "tipo": "base", "campo": None})
    for campo, q in vizinhos(base):
        k = json.dumps(q, sort_keys=True)
        if k in vistos:
            continue
        vistos.add(k)
        variantes.append(q)
        mapa.append({"base_id": int(r["id"]), "tipo": "vizinho", "campo": campo})

json.dump(mapa, open(saida_mapa, "w"))
json.dump({"nome": "selecao final 2021-2025", "base": {"penetracao_ticks": 1}, "variantes": variantes, "corte_oos": "2025-01-01",
           "janelas": {"tudo": ["2021-09-01", "2025-12-31"]}, "ordenar_por": "ret_dd", "top": 10, "min_operacoes": 50},
          open(saida, "w", encoding="utf-8"), ensure_ascii=False)
print(len(variantes), "combinações", file=sys.stderr)
