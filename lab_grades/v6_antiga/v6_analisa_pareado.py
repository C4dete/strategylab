import os, pickle, sys
from math import comb

import numpy as np
import pandas as pd

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(SP)), "lab_cache")
d = pickle.load(open(os.path.join(CACHE, "pareado.pkl"), "rb"))
res, configs = d["res"], d["configs"]
N = len(configs)
rows = []
for r in res:
    for per in ("all", "treino", "teste"):
        tot, dd, n, mp, mm = r[per]
        rows.append(dict(i=r["i"], t=r["t"], per=per, total=tot, dd=dd, n=n, mp=mp, mm=mm))
df = pd.DataFrame(rows)
w = df.pivot_table(index=["i", "per"], columns="t", values="total").reset_index()
dd_ = df.pivot_table(index=["i", "per"], columns="t", values="dd").reset_index()


def sinal_p(k, n):
    cauda = sum(comb(n, i) for i in range(max(k, n - k), n + 1)) / 2 ** n
    return min(1.0, 2 * cauda)


print(f"{N} configurações sorteadas na vizinhança da v6 (trailing e reversão ligados, filtro3 'ambos'); cada uma rodada com e sem cada componente.")
print("Δ = (base COM o componente) − (sem ele), em R$. Positivo = o componente ajuda.\n")
for comp, col in (("filtro de formação (ambos vs off)", "f3_off"), ("filtro de formação (ambos vs contra)", "f3_contra"),
                  ("trailing (ligado vs off)", "sem_trail"), ("reversão (1-2 vs 0)", "sem_rev")):
    print(f"=== {comp}")
    linhas = []
    for per, nome in (("treino", "treino ≤2023"), ("teste", "teste 2024-25"), ("all", "tudo")):
        x = w[w.per == per]
        dif = (x["base"] - x[col]).to_numpy()
        ddx = dd_[dd_.per == per]
        ddd = (ddx["base"] - ddx[col]).to_numpy()          # dd negativo: positivo = DD menor com o componente
        linhas.append(dict(período=nome, **{"Δ R$ mediano": np.median(dif), "Δ R$ médio": dif.mean(), "% configs que melhoram": (dif > 0).mean() * 100,
                                          "p (sinal)": sinal_p(int((dif > 0).sum()), len(dif)), "Δ DD mediano (+ = menor)": np.median(ddd)}))
    print(pd.DataFrame(linhas).set_index("período").round(2).to_string())
    print()

# onde está a v6 entre os vizinhos
b = df[df.t == "base"].pivot_table(index="i", columns="per", values="total")
bd = df[df.t == "base"].pivot_table(index="i", columns="per", values="dd")
rd = (b / bd.abs())
print("=== a v6 entre os 'vizinhos' sorteados (todos com os componentes ligados) ===")
print("            v6        vizinhos: mediana   p10     p90   | % com R$>0")
for per, ref_tot, ref_rd in (("treino", 14949, 9.3), ("teste", 5102, 3.0), ("all", 20051, 11.7)):
    print(f"R$ {per:7s} {ref_tot:7d}   {b[per].median():10.0f} {b[per].quantile(.1):8.0f} {b[per].quantile(.9):8.0f} | {(b[per]>0).mean()*100:5.0f}%")
    print(f"R/DD {per:6s} {ref_rd:7.1f}   {rd[per].median():10.1f} {rd[per].quantile(.1):8.1f} {rd[per].quantile(.9):8.1f}")
print("\nRetenção: ritmo do teste (R$/ano 24-25) ÷ ritmo do treino (R$/ano 2021-23):")
anos_tr, anos_te = 2.3, 2.0
ret = (b["teste"] / anos_te) / (b["treino"] / anos_tr)
print(f"  vizinhos: mediana {ret.median():.2f} (p10 {ret.quantile(.1):.2f}, p90 {ret.quantile(.9):.2f})   |   v6: {(5102/2.0)/(14949/2.3):.2f}")

# seleção pelo treino entre os vizinhos: o melhor do treino rende mais no teste que a mediana?
top = rd["treino"].sort_values(ascending=False).head(10).index
print(f"\nTop 10 pelo Ret/DD do treino: teste R$ mediano {b.loc[top,'teste'].median():.0f} (todos os vizinhos: {b['teste'].median():.0f}); "
      f"correlação de postos treino×teste do Ret/DD: {pd.Series(rd['treino']).corr(pd.Series(rd['teste']), method='spearman'):.2f}")
