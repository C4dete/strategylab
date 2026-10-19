"""Efeito de cada controle da Etapa 6 no TESTE (experimento randomizado) + como ficam as seleções feitas só pelo treino.

    python lab_grades/analisar_regime.py <resultados.csv>
"""

import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
df = pd.read_csv(sys.argv[1], sep=";", decimal=",", encoding="utf-8-sig")
df = df[df.status == "ok"].copy()
mcols = sorted(c for c in df.columns if c.startswith("m_"))
rng = np.random.default_rng(5)

CONTROLES = {
    "parar o dia por perda": df.parar_dia_perda_x_media > 0,
    "tempo máximo": df.tempo_max_min > 0,
    "gap do dia": df.filtro_gap_ativo.astype(bool),
    "amplitude de ontem": df.filtro_vol_ontem_ativo.astype(bool),
    "largura das bandas": df.filtro_bb_ativo.astype(bool),
    "inclinação da MM": df.filtro_inclinacao_ativo.astype(bool),
}
FOLDS = {"A": dict(t="trainA", s="testA", ate="2023-12"), "B": dict(t="trainB", s="testB", ate="2024-12")}


def perm_p(a, b, n=1500):
    """p-valor (bilateral) da diferença de medianas por permutação."""
    obs = np.median(a) - np.median(b)
    todos = np.concatenate([a, b])
    cont = 0
    for _ in range(n):
        rng.shuffle(todos)
        cont += abs(np.median(todos[:len(a)]) - np.median(todos[len(a):])) >= abs(obs)
    return (cont + 1) / (n + 1)


print("=" * 100)
print("1) EFEITO DE CADA CONTROLE (ligado x desligado), combinações com >= 150 operações no treino")
print("   métricas: R$ mediano no TESTE | % de combinações com teste > 0 | Ret/DD mediano no teste | (treino: Ret/DD mediano)")
for fold, f in FOLDS.items():
    e = df[df[f"{f['t']}_operacoes"] >= 150]
    print(f"\n--- fold {fold}: treino {f['t']} -> teste {f['s']} | {len(e)} combinações")
    linhas = []
    for nome, on in CONTROLES.items():
        a, b = e[on.loc[e.index]], e[~on.loc[e.index]]
        ta, tb = a[f"{f['s']}_total_rs"].values, b[f"{f['s']}_total_rs"].values
        linhas.append({
            "controle": nome, "n_on": len(a),
            "teste R$ med ON": np.median(ta), "teste R$ med OFF": np.median(tb),
            "% teste>0 ON": (ta > 0).mean() * 100, "% teste>0 OFF": (tb > 0).mean() * 100,
            "teste Ret/DD ON": a[f"{f['s']}_ret_dd"].median(), "teste Ret/DD OFF": b[f"{f['s']}_ret_dd"].median(),
            "treino Ret/DD ON": a[f"{f['t']}_ret_dd"].median(), "treino Ret/DD OFF": b[f"{f['t']}_ret_dd"].median(),
            "p (R$ teste)": perm_p(ta, tb),
        })
    print(pd.DataFrame(linhas).set_index("controle").round(2).to_string())

print("\n" + "=" * 100)
print("2) DOSE-RESPOSTA (fold B, teste 2025; R$ mediano no teste e % com teste>0 por nível; n em parênteses)")
e = df[df["trainB_operacoes"] >= 150]
for col, nome in (("parar_dia_perda_x_media", "parar o dia por perda (x media_op)"), ("tempo_max_min", "tempo máximo (min)"),
                  ("filtro_gap_max_x_media", "gap máx (só com filtro)"), ("filtro_vol_ontem_max", "amplitude de ontem máx (só com filtro)"),
                  ("filtro_bb_largura_max_pct", "largura máx bandas (só com filtro)"), ("filtro_inclinacao_max_x_media", "inclinação máx (só com filtro)")):
    x = e.copy()
    if col == "filtro_gap_max_x_media":
        x = x[x.filtro_gap_ativo.astype(bool)]
    elif col == "filtro_vol_ontem_max":
        x = x[x.filtro_vol_ontem_ativo.astype(bool)]
    elif col == "filtro_bb_largura_max_pct":
        x = x[x.filtro_bb_ativo.astype(bool)]
    elif col == "filtro_inclinacao_max_x_media":
        x = x[x.filtro_inclinacao_ativo.astype(bool)]
    g = x.groupby(col)["testB_total_rs"].agg(med="median", pos=lambda s: (s > 0).mean() * 100, n="size").round(1)
    print(f"\n{nome}:")
    print(g.T.to_string())

print("\n" + "=" * 100)
print("3) SELEÇÃO SÓ PELO TREINO (as 20 melhores por Ret/DD e por Sharpe mensal): que controles elas usam e como vão no teste")
for fold, f in FOLDS.items():
    e = df[(df[f"{f['t']}_operacoes"] >= 150) & (df[f"{f['t']}_total_rs"] > 0)].copy()
    mm = e[[c for c in mcols if c[2:] <= f["ate"]]]
    e["sharpe"] = mm.mean(axis=1) / mm.std(axis=1).replace(0, np.nan)
    for crit, ordem in (("Ret/DD", e.sort_values(f"{f['t']}_ret_dd", ascending=False)), ("Sharpe mensal", e.sort_values("sharpe", ascending=False))):
        top = ordem.head(20)
        usa = {nome: f"{int(on.loc[top.index].sum())}/20" for nome, on in CONTROLES.items()}
        s = top[f"{f['s']}_total_rs"]
        print(f"fold {fold} | {crit}: teste R$ mediano {s.median():.0f} | {(s > 0).mean() * 100:.0f}% positivas | Ret/DD teste {top[f'{f['s']}_ret_dd'].median():.2f} | "
              f"referência anterior (sem controles novos): A +216 (65%) / B +555 (70%) para Ret/DD")
        print("    usam:", usa)
    ref = e[f"{f['s']}_total_rs"]
    print(f"    todas as elegíveis: teste R$ mediano {ref.median():.0f}, {(ref > 0).mean() * 100:.0f}% positivas")
