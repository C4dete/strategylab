"""Experimento walk-forward: qual critério de SELEÇÃO (calculado só no treino) escolhe combinações que seguem boas no teste?

    python lab_grades/analisar_walkforward.py <resultados.csv>

Folds: A = treino 2021-09..2023-12 -> teste 2024 ; B = treino 2021-09..2024-12 -> teste 2025.
Cada critério escolhe as K melhores do treino; mede-se o teste. A referência é sortear K combinações elegíveis (1.000 sorteios).
"""

import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
df = pd.read_csv(sys.argv[1], sep=";", decimal=",", encoding="utf-8-sig")
df = df[df.status == "ok"].copy()
mcols = sorted(c for c in df.columns if c.startswith("m_"))
meses = [c[2:] for c in mcols]
rng = np.random.default_rng(1)

# blocos de 6 meses (semestres de calendário)
def semestre(m):
    return m[:4] + ("H1" if int(m[5:7]) <= 6 else "H2")


def blocos(ate):
    ms = [m for m in meses if m <= ate]
    nomes = sorted({semestre(m) for m in ms})
    return {n: [f"m_{m}" for m in ms if semestre(m) == n] for n in nomes}


FOLDS = {"A": dict(treino="trainA", teste="testA", ate="2023-12", anos_treino=2.33),
         "B": dict(treino="trainB", teste="testB", ate="2024-12", anos_treino=3.33)}


def features(f):
    t, a = f["treino"], f["anos_treino"]
    x = pd.DataFrame(index=df.index)
    x["ops"] = df[f"{t}_operacoes"]
    x["total"] = df[f"{t}_total_rs"]
    x["dd"] = df[f"{t}_dd_rs"]
    x["retdd"] = df[f"{t}_ret_dd"]
    x["meses_pos"] = df[f"{t}_meses_pos"] / df[f"{t}_meses_total"]
    x["pior_mes"] = df[f"{t}_pior_mes"]
    bl = blocos(f["ate"])
    bs = pd.DataFrame({n: df[cols].sum(axis=1) for n, cols in bl.items()})
    x["blocos_pos"] = (bs > 0).sum(axis=1) / bs.shape[1]
    x["pior_bloco"] = bs.min(axis=1)
    mm = df[[f"m_{m}" for m in meses if m <= f["ate"]]]
    x["sharpe_mes"] = mm.mean(axis=1) / mm.std(axis=1).replace(0, np.nan)
    x["teste_total"] = df[f"{f['teste']}_total_rs"]
    x["teste_dd"] = df[f"{f['teste']}_dd_rs"]
    x["teste_retdd"] = df[f"{f['teste']}_ret_dd"]
    x["teste_mpos"] = df[f"{f['teste']}_meses_pos"] / df[f"{f['teste']}_meses_total"]
    x["teste_ops"] = df[f"{f['teste']}_operacoes"]
    x["retencao"] = x["teste_total"] / (x["total"] / a).replace(0, np.nan)      # quanto do ritmo do treino sobrou no teste
    return x


def selecoes(x, elegivel, k):
    e = x[elegivel]
    rk = lambda s, asc=False: s.rank(ascending=asc, pct=True)
    comp = (rk(e.retdd.fillna(-9)) + rk(e.meses_pos) + rk(e.pior_bloco) + rk(e.sharpe_mes.fillna(-9)) + rk(e.blocos_pos)) / 5
    return {
        "S0 meses positivos (o que usamos)": e.sort_values(["meses_pos", "pior_mes", "total"], ascending=False).head(k).index,
        "S1 total em R$": e.sort_values("total", ascending=False).head(k).index,
        "S2 Ret/DD": e.sort_values("retdd", ascending=False).head(k).index,
        "S3 semestres positivos + pior semestre": e.sort_values(["blocos_pos", "pior_bloco", "retdd"], ascending=False).head(k).index,
        "S4 melhor pior-semestre": e[e.total > 0].sort_values("pior_bloco", ascending=False).head(k).index,
        "S5 Sharpe mensal": e.sort_values("sharpe_mes", ascending=False).head(k).index,
        "S6 composto (5 ranks)": comp.sort_values(ascending=False).head(k).index,
    }


def resumo(x, idx):
    s = x.loc[idx]
    return {"teste R$ mediano": s.teste_total.median(), "% teste>0": (s.teste_total > 0).mean() * 100,
            "teste Ret/DD med": s.teste_retdd.median(), "teste meses+ %": s.teste_mpos.median() * 100,
            "retenção med": s.retencao.median(), "teste ops med": s.teste_ops.median()}


for k in (20, 50):
    print(f"\n################ K = {k} (as {k} melhores do treino, mínimo 150 operações no treino) ################")
    for nome, f in FOLDS.items():
        x = features(f)
        elegivel = (x.ops >= 150) & x.total.notna()
        print(f"\n--- fold {nome}: treino {f['treino']} -> teste {f['teste']} | combinações elegíveis: {int(elegivel.sum())} | "
              f"% elegíveis com teste>0: {(x[elegivel].teste_total > 0).mean() * 100:.0f}%, teste R$ mediano {x[elegivel].teste_total.median():.0f}")
        linhas = {}
        for sel, idx in selecoes(x, elegivel, k).items():
            linhas[sel] = resumo(x, idx)
        base = x[elegivel]
        sorteios = [resumo(x, rng.choice(base.index, k, replace=False)) for _ in range(500)]
        linhas["REF sorteio aleatório (média)"] = {c: float(np.nanmean([s[c] for s in sorteios])) for c in sorteios[0]}
        t = pd.DataFrame(linhas).T.round(1)
        print(t.to_string())
        # p-valor de cada critério contra o sorteio (mediana de R$ no teste)
        ref = np.array([s["teste R$ mediano"] for s in sorteios])
        print("    p-valor (R$ mediano no teste > sorteio):",
              {sel.split()[0]: round(float((ref >= linhas[sel]["teste R$ mediano"]).mean()), 3) for sel in list(linhas)[:-1]})
