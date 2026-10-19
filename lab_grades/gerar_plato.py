"""Passo 2 do walk-forward: candidatas escolhidas SÓ pelo treino (Ret/DD e Sharpe mensal) + seus vizinhos (um parâmetro por vez).

    python lab_grades/gerar_plato.py <resultados_walkforward.csv> <saida_grade.json> <saida_mapa.json> [N_por_criterio]

O mapa guarda, para cada combinação da grade, a qual grupo (fold, base) ela pertence e se é a própria base ou um vizinho.
"""

import json
import sys

import numpy as np
import pandas as pd

csv, saida, saida_mapa = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 25
df = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig")
df = df[df.status == "ok"].copy()
mcols = sorted(c for c in df.columns if c.startswith("m_"))

MENU = {
    "candles_gatilho": [3, 5, 8, 12, 20],
    "candles_media": [3, 5, 10, 15],
    "bracket_fracao": [0.05, 0.25, 0.5, 1.0, 1.5, 2.0],
    "modo_entrada": ["padrao", "proximo_candle"],
    "book": ["cont", "ambas", "recuo"],
    "operacoes_por_dia": [1, 2, 3, 5],
    "stop_x_media": [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0],
    "alvo_x_media": [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0],
    "janela_inicio": ["09:00", "09:30", "10:00", "10:30"],
    "ultima_entrada": ["12:00", "13:00", "14:00", "15:00", "16:00"],
    "reversoes": [0, 1, 2, 3],
    "rev_stop_x_media": [0.0, 0.5, 1.5, 3.0],
    "rev_alvo_x_media": [0.0, 1.0, 3.0],
    "rastrear_mm": [False, True],
    "sair_ao_tocar_mm": [False, True],
    "parar_apos_losses": [0, 1, 2, 3],
    "contagem_losses": ["dia", "seguidos"],
    "filtro_afast_mm_ativo": [False, True],
    "filtro_afast_mm_x_media": [0.3, 0.7, 1.5, 3.0],
    "mm_periodo": [9, 15, 30, 50],
}


def params_da_linha(r) -> dict:
    p = {}
    for c in MENU:
        v = r.get(c)
        if v is None or (isinstance(v, float) and v != v):
            continue
        p[c] = v.item() if hasattr(v, "item") else v
    return p


def normalizar(p: dict) -> dict:
    p = dict(p)
    if not p.get("reversoes"):
        p.pop("rev_stop_x_media", None), p.pop("rev_alvo_x_media", None)
    if not p.get("filtro_afast_mm_ativo"):
        p["filtro_afast_mm_ativo"] = False
        p.pop("filtro_afast_mm_x_media", None)
    if not p.get("parar_apos_losses"):
        p.pop("contagem_losses", None)
    if not (p.get("filtro_afast_mm_ativo") or p.get("rastrear_mm") or p.get("sair_ao_tocar_mm")):
        p.pop("mm_periodo", None)
    return p


def vizinhos(base: dict):
    for campo, valores in MENU.items():
        for v in valores:
            if base.get(campo) == v:
                continue
            q = dict(base)
            q[campo] = v
            if campo == "reversoes" and v and "rev_stop_x_media" not in q:
                q["rev_stop_x_media"], q["rev_alvo_x_media"] = 0.0, 0.0
            if campo == "filtro_afast_mm_ativo" and v and "filtro_afast_mm_x_media" not in q:
                q["filtro_afast_mm_x_media"] = 0.7
            if campo == "filtro_afast_mm_x_media" and not q.get("filtro_afast_mm_ativo"):
                continue
            if campo in ("rev_stop_x_media", "rev_alvo_x_media") and not q.get("reversoes"):
                continue
            if campo == "contagem_losses" and not q.get("parar_apos_losses"):
                continue
            if campo == "mm_periodo" and not (q.get("filtro_afast_mm_ativo") or q.get("rastrear_mm") or q.get("sair_ao_tocar_mm")):
                continue
            yield campo, normalizar(q)


def bases_do_fold(treino: str, ate: str):
    t = df[(df[f"{treino}_operacoes"] >= 150) & (df[f"{treino}_total_rs"] > 0)].copy()
    mm = t[[c for c in mcols if c[2:] <= ate]]
    t["sharpe_mes"] = mm.mean(axis=1) / mm.std(axis=1).replace(0, np.nan)
    a = t.sort_values(f"{treino}_ret_dd", ascending=False).head(N)
    b = t.sort_values("sharpe_mes", ascending=False).head(N)
    return pd.concat([a, b]).drop_duplicates("id")


variantes, mapa = [], []
for fold, treino, ate in (("A", "trainA", "2023-12"), ("B", "trainB", "2024-12")):
    bases = bases_do_fold(treino, ate)
    print(f"fold {fold}: {len(bases)} bases", file=sys.stderr)
    for _, r in bases.iterrows():
        base = normalizar(params_da_linha(r))
        grupo = {"fold": fold, "base_id": int(r["id"])}
        vistos = {json.dumps(base, sort_keys=True)}
        variantes.append(base)
        mapa.append({**grupo, "tipo": "base", "campo": None})
        for campo, q in vizinhos(base):
            k = json.dumps(q, sort_keys=True)
            if k in vistos:
                continue
            vistos.add(k)
            variantes.append(q)
            mapa.append({**grupo, "tipo": "vizinho", "campo": campo})

json.dump(mapa, open(saida_mapa, "w"))
print(json.dumps({
    "nome": "walkforward plato", "base": {"penetracao_ticks": 1}, "variantes": variantes, "corte_oos": "2025-01-01",
    "janelas": {"trainA": ["2021-09-01", "2023-12-31"], "testA": ["2024-01-01", "2024-12-31"],
                "trainB": ["2021-09-01", "2024-12-31"], "testB": ["2025-01-01", "2025-12-31"]},
    "ordenar_por": "trainB_ret_dd", "top": 10, "min_operacoes": 50,
}, ensure_ascii=False), file=open(saida, "w", encoding="utf-8"))
print(len(variantes), "combinações", file=sys.stderr)
