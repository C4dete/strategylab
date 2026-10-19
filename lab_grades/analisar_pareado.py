"""Análise pareada: o controle melhora o TESTE da MESMA candidata?   python lab_grades/analisar_pareado.py <resultados.csv> <mapa.json>"""

import json
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
df = pd.read_csv(sys.argv[1], sep=";", decimal=",", encoding="utf-8-sig")
df = pd.concat([df.reset_index(drop=True), pd.DataFrame(json.load(open(sys.argv[2])))], axis=1)
df = df[df.status == "ok"]


def sinal_p(melhorou, n):
    """p-valor bilateral do teste do sinal (binomial 0,5)."""
    from math import comb
    k = int(melhorou)
    cauda = sum(comb(n, i) for i in range(max(k, n - k), n + 1)) / 2 ** n
    return min(1.0, 2 * cauda)


print("Cada linha: para as 32 candidatas de cada fold (escolhidas SÓ pelo treino), variação do TESTE da própria candidata ao acrescentar o controle.")
print("Δ R$ = teste COM o controle − teste da candidata sem ele (mediana e média). '% melhorou' = candidatas cujo teste subiu. p = teste do sinal.\n")
for fold, teste, treino in (("A", "testA", "trainA"), ("B", "testB", "trainB"), ("A+B", None, None)):
    print(f"================ fold {fold} ================")
    linhas = []
    for ctrl in [c for c in df.controle.unique() if c != "base"]:
        d_rs, d_dd, d_rdd, d_tr, ops_ratio = [], [], [], [], []
        for f in ("A", "B") if fold == "A+B" else (fold,):
            te = f"test{f}"
            tr = f"train{f}"
            for bid, g in df[df.fold == f].groupby("base_id"):
                b = g[g.controle == "base"]
                c = g[g.controle == ctrl]
                if len(b) != 1 or len(c) != 1:
                    continue
                b, c = b.iloc[0], c.iloc[0]
                d_rs.append(c[f"{te}_total_rs"] - b[f"{te}_total_rs"])
                d_dd.append(c[f"{te}_dd_rs"] - b[f"{te}_dd_rs"])                     # dd é negativo: positivo = drawdown menor
                d_tr.append(c[f"{tr}_total_rs"] - b[f"{tr}_total_rs"])
                ops_ratio.append(c[f"{te}_operacoes"] / max(b[f"{te}_operacoes"], 1))
        d_rs, d_dd, d_tr = np.array(d_rs), np.array(d_dd), np.array(d_tr)
        n = len(d_rs)
        linhas.append({"controle": ctrl, "n": n, "Δ R$ teste (med)": np.median(d_rs), "Δ R$ teste (média)": d_rs.mean(),
                       "% melhorou": (d_rs > 0).mean() * 100, "p (sinal)": sinal_p((d_rs > 0).sum(), n),
                       "Δ DD teste (med, + = menor)": np.median(d_dd), "Δ R$ treino (med)": np.median(d_tr),
                       "ops teste (razão med)": np.median(ops_ratio)})
    print(pd.DataFrame(linhas).set_index("controle").round(2).to_string())
    print()
