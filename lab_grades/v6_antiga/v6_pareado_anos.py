import os, pickle
import numpy as np, pandas as pd
SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(SP)), "lab_cache")
d = pickle.load(open(os.path.join(CACHE, "pareado.pkl"), "rb"))
res = d["res"]
rows = []
for r in res:
    for a in (2021, 2022, 2023, 2024, 2025):
        rows.append(dict(i=r["i"], t=r["t"], ano=a, v=r["anos"].get(a, 0)))
df = pd.DataFrame(rows).pivot_table(index=["i", "ano"], columns="t", values="v").reset_index()
print("Δ por ano = base − sem o componente: mediana R$ (e % de configs em que o componente ajuda)\n")
for nome, col in (("filtro formação ambos vs off", "f3_off"), ("ambos vs contra", "f3_contra"), ("trailing vs off", "sem_trail"), ("reversão vs 0", "sem_rev")):
    linhas = {}
    for a in (2021, 2022, 2023, 2024, 2025):
        x = df[df.ano == a]
        dif = x["base"] - x[col]
        linhas[a] = f"{dif.median():7.0f} ({(dif > 0).mean()*100:3.0f}%)"
    print(f"{nome:32s}", "  ".join(f"{a}: {v}" for a, v in linhas.items()))
# nível médio por ano das configs base e v6
b = df[df.ano > 0].pivot_table(index="i", columns="ano", values="base")
print("\nR$ por ano: vizinhos (mediana)", b.median().round(0).to_dict(), "| v6:", {2021: 3494, 2022: 7928, 2023: 3527, 2024: 2603, 2025: 2499})
print("% de vizinhos com ano positivo:", (b > 0).mean().round(2).to_dict())
# spearman sem scipy
tot = pd.DataFrame(d["res"])
x = pd.DataFrame([dict(i=r["i"], tr=r["treino"][0] / abs(r["treino"][1] or 1), te=r["teste"][0] / abs(r["teste"][1] or 1), trR=r["treino"][0], teR=r["teste"][0]) for r in d["res"] if r["t"] == "base"])
print("\nvizinhos: correlação de postos treino×teste  Ret/DD:", round(x["tr"].rank().corr(x["te"].rank()), 2), "| R$:", round(x["trR"].rank().corr(x["teR"].rank()), 2))
top = x.sort_values("tr", ascending=False).head(10)
print(f"top-10 pelo Ret/DD do treino: teste R$ mediano {top['teR'].median():.0f} (todos: {x['teR'].median():.0f}); 20 piores no treino: {x.sort_values('tr').head(20)['teR'].median():.0f}")
