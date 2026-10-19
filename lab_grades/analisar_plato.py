"""Passo 2 do walk-forward: exigir PLATÔ melhora a escolha? Compara, por fold, escolher só pela base x pela mediana da vizinhança.

    python lab_grades/analisar_plato.py <resultados_plato.csv> <mapa.json>
Tudo que decide usa só o TREINO; o teste (2024 no fold A, 2025 no fold B) só mede.
"""

import json
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
df = pd.read_csv(sys.argv[1], sep=";", decimal=",", encoding="utf-8-sig")
mapa = pd.DataFrame(json.load(open(sys.argv[2])))
assert len(mapa) == len(df), (len(mapa), len(df))
df = pd.concat([df.reset_index(drop=True), mapa], axis=1)
df = df[df.status == "ok"].copy()
mcols = sorted(c for c in df.columns if c.startswith("m_"))
rng = np.random.default_rng(3)

FOLDS = {"A": dict(t="trainA", s="testA", ate="2023-12"), "B": dict(t="trainB", s="testB", ate="2024-12")}


def sharpe(d, ate):
    m = d[[c for c in mcols if c[2:] <= ate]]
    return m.mean(axis=1) / m.std(axis=1).replace(0, np.nan)


for fold, f in FOLDS.items():
    d = df[df.fold == fold].copy()
    d["sharpe"] = sharpe(d, f["ate"])
    d["retdd"] = d[f"{f['t']}_ret_dd"]
    d["ops_t"] = d[f"{f['t']}_operacoes"]
    d["teste"] = d[f"{f['s']}_total_rs"]
    d["teste_retdd"] = d[f"{f['s']}_ret_dd"]
    d["ok_viz"] = (d[f"{f['t']}_total_rs"] > 0) & (d.ops_t >= 100)
    bases = d[d.tipo == "base"].set_index("base_id")
    linhas = []
    for bid, b in bases.iterrows():
        v = d[(d.tipo == "vizinho") & (d.base_id == bid)]
        if len(v) < 10:
            continue
        linhas.append({
            "base_id": bid, "retdd": b.retdd, "sharpe": b.sharpe, "ops": b.ops_t,
            "viz_retdd_med": v.retdd.median(), "viz_sharpe_med": v.sharpe.median(),
            "viz_pos": v.ok_viz.mean(), "n_viz": len(v),
            "plato_retdd": (b.retdd + v.retdd.median()) / 2, "plato_sharpe": (b.sharpe + v.sharpe.median()) / 2,
            "teste": b.teste, "teste_retdd": b.teste_retdd, "viz_teste_med": v.teste.median(),
            "viz_teste_pos": (v.teste > 0).mean(),
        })
    t = pd.DataFrame(linhas)
    print(f"\n================ fold {fold}: treino {f['t']} -> teste {f['s']} | {len(t)} bases com vizinhança (média {t.n_viz.mean():.0f} vizinhos) ================")
    print(f"todas as bases: teste mediano R$ {t.teste.median():.0f}, % com teste>0 {(t.teste > 0).mean() * 100:.0f}% | "
          f"vizinhos (teste): mediana R$ {t.viz_teste_med.median():.0f}")
    sel = {
        "base por Ret/DD": t.sort_values("retdd", ascending=False),
        "base por Sharpe mensal": t.sort_values("sharpe", ascending=False),
        "PLATÔ Ret/DD (base+med.vizinhos)": t.sort_values("plato_retdd", ascending=False),
        "PLATÔ Sharpe (base+med.vizinhos)": t.sort_values("plato_sharpe", ascending=False),
        "platô + 60% vizinhos lucrativos no treino": t[t.viz_pos >= 0.6].sort_values("plato_sharpe", ascending=False),
    }
    for k in (10,):
        out = {}
        for nome, s in sel.items():
            s = s.head(k)
            out[nome] = {"n": len(s), "teste R$ med": s.teste.median(), "% teste>0": (s.teste > 0).mean() * 100,
                         "teste Ret/DD med": s.teste_retdd.median(), "vizinhos teste>0 (med %)": s.viz_teste_pos.median() * 100,
                         "ops treino med": s.ops.median()}
        ref = [t.sample(k, random_state=int(rng.integers(1e9))).teste.median() for _ in range(300)]
        out["REF sorteio entre as bases"] = {"n": k, "teste R$ med": float(np.mean(ref)), "% teste>0": float((t.teste > 0).mean() * 100),
                                              "teste Ret/DD med": float(t.teste_retdd.median()),
                                              "vizinhos teste>0 (med %)": float(t.viz_teste_pos.median() * 100), "ops treino med": float(t.ops.median())}
        print(pd.DataFrame(out).T.round(1).to_string())
    # o platô no treino diz algo sobre o teste?
    print("correlação de postos (treino -> teste R$): base Ret/DD", round(t.retdd.rank().corr(t.teste.rank()), 2),
          "| platô Sharpe", round(t.plato_sharpe.rank().corr(t.teste.rank()), 2),
          "| fração de vizinhos lucrativos no treino", round(t.viz_pos.rank().corr(t.teste.rank()), 2))
