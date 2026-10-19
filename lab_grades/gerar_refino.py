"""Refino (etapa 2): para cada uma das N melhores combinações de uma etapa anterior, varia UM parâmetro por vez no menu
(com as bordas estendidas) e, para as 6 melhores, a grade stop x alvo. Uso:

    python lab_grades/gerar_refino.py <resultados.csv> <N> > lab_grades/busca_meses_etapa2.json
"""

import json
import sys

import pandas as pd

csv, N = sys.argv[1], int(sys.argv[2])
df = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig")
ok = df[(df.status == "ok") & (df.operacoes >= 100)]
top = ok.sort_values(["meses_pos", "pior_mes", "total_rs"], ascending=False).head(N)

MENU = {
    "candles_gatilho": [3, 5, 8, 12, 20],
    "candles_media": [3, 5, 10, 15],
    "bracket_fracao": [0.05, 0.25, 0.5, 1.0, 1.5, 2.0],
    "modo_entrada": ["padrao", "proximo_candle"],
    "book": ["cont", "ambas", "recuo", "acima", "abaixo"],
    "operacoes_por_dia": [1, 2, 3, 5],
    "stop_x_media": [1.5, 2.0, 3.0, 4.0, 5.0],
    "alvo_x_media": [0.25, 0.5, 0.75, 1.0, 2.0, 3.0],
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
CAMPOS = list(MENU)


def linha_para_params(r) -> dict:
    p = {}
    for c in CAMPOS:
        v = r.get(c)                      # coluna ausente (campo que ficou fixo na grade anterior) = padrão de Params
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


variantes, vistos = [], set()


def add(p):
    p = normalizar(p)
    k = json.dumps(p, sort_keys=True)
    if k not in vistos:
        vistos.add(k)
        variantes.append(p)


for _, r in top.iterrows():
    base = linha_para_params(r)
    add(base)
    for campo, valores in MENU.items():
        for v in valores:
            q = dict(base)
            q[campo] = v
            if campo == "reversoes" and v and "rev_stop_x_media" not in q:
                q["rev_stop_x_media"], q["rev_alvo_x_media"] = 0.0, 0.0
            if campo == "filtro_afast_mm_ativo" and v and "filtro_afast_mm_x_media" not in q:
                q["filtro_afast_mm_x_media"] = 0.7
            if campo in ("filtro_afast_mm_x_media",) and not q.get("filtro_afast_mm_ativo"):
                q["filtro_afast_mm_ativo"] = True
            if campo in ("rev_stop_x_media", "rev_alvo_x_media") and not q.get("reversoes"):
                q["reversoes"] = 1
            if campo == "contagem_losses" and not q.get("parar_apos_losses"):
                q["parar_apos_losses"] = 2
            if campo == "mm_periodo" and not (q.get("filtro_afast_mm_ativo") or q.get("rastrear_mm") or q.get("sair_ao_tocar_mm")):
                continue
            add(q)

for _, r in top.head(6).iterrows():
    base = linha_para_params(r)
    for s in (2.0, 3.0, 4.0, 5.0):
        for a in (0.25, 0.5, 0.75, 1.0):
            q = dict(base)
            q["stop_x_media"], q["alvo_x_media"] = s, a
            add(q)

print(json.dumps({
    "nome": "busca meses etapa2 (refino)", "base": {"penetracao_ticks": 1}, "variantes": variantes,
    "corte_oos": "2025-01-01", "ordenar_por": "meses_pos", "top": 20, "min_operacoes": 100,
}, ensure_ascii=False))
