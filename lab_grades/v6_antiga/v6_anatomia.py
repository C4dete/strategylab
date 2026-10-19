"""Anatomia da v6 (motor antigo, dados até 2025): onde está o resultado."""
import os, sys
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import numpy as np
import pandas as pd
import v6lab as L

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

B = L.BARRAS.reset_index(drop=True)
# media_op por barra (a vigente na barra i usa as 5 anteriores FECHADAS do dia) e amplitude da zona
B["dia"] = B["datetime"].dt.date
rng = (B["high"] - B["low"])
B["mop"] = rng.groupby(B["dia"]).transform(lambda s: s.shift(1).rolling(5).mean())
B["zmax"] = B["high"].groupby(B["dia"]).transform(lambda s: s.shift(1).rolling(5).max())
B["zmin"] = B["low"].groupby(B["dia"]).transform(lambda s: s.shift(1).rolling(5).min())
B["zona"] = B["zmax"] - B["zmin"]
idx = B.set_index("datetime")[["mop", "zona"]]

tr = L.rodar()
tr["entrada"] = pd.to_datetime(tr["entry_time"])
tr["saida"] = pd.to_datetime(tr["exit_time"])
tr["dia"] = tr["entrada"].dt.date
tr["ano"] = tr["entrada"].dt.year
tr["hora"] = tr["entrada"].dt.hour
tr["dsem"] = tr["entrada"].dt.dayofweek
tr["perna"] = np.where(tr.groupby("dia").cumcount() == 0, "entrada", "reversão")
tr["mop"] = idx["mop"].reindex(tr["entrada"]).to_numpy()
tr["zona"] = idx["zona"].reindex(tr["entrada"]).to_numpy()
tr["R"] = tr["pts"] / tr["mop"]
tr["dur_min"] = (tr["saida"] - tr["entrada"]).dt.total_seconds() / 60


def resumo(g):
    return pd.Series(dict(ops=len(g), R_total=g["result_rs"].sum(), R_por_op=g["result_rs"].mean(), acerto=(g["pts"] > 0).mean() * 100,
                          pts=g["pts"].mean(), R_mult=g["R"].mean()))

print("=== por perna");  print(tr.groupby("perna").apply(resumo).round(2))
print("\n=== por lado");  print(tr.groupby("side").apply(resumo).round(2))
print("\n=== por ano");   print(tr.groupby("ano").apply(resumo).round(2))
print("\n=== por hora de entrada");  print(tr.groupby("hora").apply(resumo).round(2))
print("\n=== por dia da semana (0=seg)");  print(tr.groupby("dsem").apply(resumo).round(2))
tr["q_mop"] = pd.qcut(tr["mop"], 4, labels=["Q1 calmo", "Q2", "Q3", "Q4 volátil"])
print("\n=== por escala (media_op na entrada, quartis)");  print(tr.groupby("q_mop", observed=True).apply(resumo).round(2))
print("   limites dos quartis (pts):", tr["mop"].quantile([.25, .5, .75]).round(0).to_dict())
tr["q_zona"] = pd.qcut(tr["zona"], 4, labels=["Z1 estreita", "Z2", "Z3", "Z4 larga"])
print("\n=== por amplitude da zona (quartis)");  print(tr.groupby("q_zona", observed=True).apply(resumo).round(2))
tr["q_zr"] = pd.qcut(tr["zona"] / tr["mop"], 4, labels=["zona/mop baixa", "Q2", "Q3", "alta"])
print("\n=== por zona/media_op (quartis)");  print(tr.groupby("q_zr", observed=True).apply(resumo).round(2))
print("   limites:", (tr["zona"] / tr["mop"]).quantile([.25, .5, .75]).round(2).to_dict())

# R por ano normalizado
print("\n=== R (pts/media_op) médio por ano e por perna")
print(tr.pivot_table(index="ano", columns="perna", values="R", aggfunc="mean").round(3))

# duração
print("\n=== duração (min) dos ganhos e perdas: mediana");  print(tr.groupby(tr["pts"] > 0)["dur_min"].median())

# ---- o que o filtro de formação faz, dia a dia
off = L.rodar(ghost_filtro3="off")
off["dia"] = pd.to_datetime(off["entry_time"]).dt.date
a = tr.groupby("dia")["result_rs"].sum().rename("com")
b = off.groupby("dia")["result_rs"].sum().rename("sem")
d = pd.concat([a, b], axis=1).fillna(0.0)
d["dif"] = d["com"] - d["sem"]
mud = d[d["dif"].abs() > 0.01]
print(f"\n=== filtro de formação: {len(mud)} de {len(d)} dias mudam; soma da diferença R$ {d['dif'].sum():.0f}")
print(f"   dias que melhoram: {(mud['dif']>0).sum()} (soma {mud.loc[mud['dif']>0,'dif'].sum():.0f}) | pioram: {(mud['dif']<0).sum()} (soma {mud.loc[mud['dif']<0,'dif'].sum():.0f})")
print(f"   nos dias que mudam: com = {mud['com'].sum():.0f} ({mud['com'].mean():.1f}/dia) | sem = {mud['sem'].sum():.0f} ({mud['sem'].mean():.1f}/dia)")
d["ano"] = pd.to_datetime(d.index).year
print("   diferença por ano:", d.groupby("ano")["dif"].sum().round(0).to_dict())
pe = tr[tr["perna"] == "entrada"].set_index("dia")["entrada"]
po = off[off.groupby("dia").cumcount() == 0].set_index("dia")["entry_time"].pipe(pd.to_datetime)
j = pd.concat([pe.rename("com"), po.rename("sem")], axis=1).dropna()
atras = (j["com"] > j["sem"]).sum(); igual = (j["com"] == j["sem"]).sum()
print(f"   1ª entrada: igual em {igual} dias, mais tarde com o filtro em {atras}, mais cedo em {(j['com'] < j['sem']).sum()}; dias só com entrada (com={pe.index.difference(po.index).size}, sem={po.index.difference(pe.index).size})")

# curva e sequências
s = L.diario(tr)
eq = s.cumsum()
under = (eq < eq.cummax())
runs = (under != under.shift()).cumsum()
maior = under.groupby(runs).sum().max()
print(f"\n=== maior período abaixo do topo: {int(maior)} dias de pregão | dias no resultado = {len(s)} | dias positivos {(s>0).mean()*100:.0f}%")
m = tr.assign(m=tr["entrada"].dt.to_period("M")).groupby("m")["result_rs"].sum()
print("meses: pos", int((m > 0).sum()), "neg", int((m < 0).sum()), "| mediana", round(float(m.median())), "| p10", round(float(m.quantile(.1))), "| p90", round(float(m.quantile(.9))))
