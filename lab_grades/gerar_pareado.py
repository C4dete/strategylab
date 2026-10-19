"""Teste PAREADO dos controles da Etapa 6: para cada candidata já escolhida só pelo treino (32 bases por fold do passo do platô),
roda a mesma candidata sem e com cada controle e compara o TESTE da própria candidata.

    python lab_grades/gerar_pareado.py <resultados_plato.csv> <mapa.json> <saida_grade.json> <saida_mapa.json>
"""

import json
import sys
from pathlib import Path

import pandas as pd

csv, mapa_in, saida, saida_mapa = sys.argv[1:5]
fonte = (Path(__file__).parent / "gerar_plato.py").read_text(encoding="utf-8")
exec(fonte[fonte.index("MENU = {"):fonte.index("def vizinhos")], globals())  # noqa: S102 - MENU, params_da_linha, normalizar

df = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig")
df = pd.concat([df.reset_index(drop=True), pd.DataFrame(json.load(open(mapa_in)))], axis=1)
bases = df[(df.tipo == "base") & (df.status == "ok")]

CONTROLES = {
    "base": {},
    "cauda 0,5": {"parar_dia_perda_x_media": 0.5},
    "cauda 1,0": {"parar_dia_perda_x_media": 1.0},
    "cauda 2,0": {"parar_dia_perda_x_media": 2.0},
    "tempo 120": {"tempo_max_min": 120},
    "gap 0,25": {"filtro_gap_ativo": True, "filtro_gap_max_x_media": 0.25},
    "gap 0,4": {"filtro_gap_ativo": True, "filtro_gap_max_x_media": 0.4},
    "vol ontem 1,25": {"filtro_vol_ontem_ativo": True, "filtro_vol_ontem_max": 1.25},
    "vol ontem 1,6": {"filtro_vol_ontem_ativo": True, "filtro_vol_ontem_max": 1.6},
    "bandas máx 0,8": {"filtro_bb_ativo": True, "filtro_bb_largura_max_pct": 0.8},
    "bandas máx 1,2": {"filtro_bb_ativo": True, "filtro_bb_largura_max_pct": 1.2},
    "inclinação 0,6": {"filtro_inclinacao_ativo": True, "filtro_inclinacao_barras": 5, "filtro_inclinacao_max_x_media": 0.6},
    "inclinação 1,0": {"filtro_inclinacao_ativo": True, "filtro_inclinacao_barras": 5, "filtro_inclinacao_max_x_media": 1.0},
    "cauda 1,0 + inclinação 0,6": {"parar_dia_perda_x_media": 1.0, "filtro_inclinacao_ativo": True, "filtro_inclinacao_barras": 5,
                                   "filtro_inclinacao_max_x_media": 0.6},
}

variantes, mapa = [], []
for _, r in bases.iterrows():
    base = normalizar(params_da_linha(r))
    for nome, extra in CONTROLES.items():
        v = dict(base)
        v.update(extra)
        if extra.get("filtro_inclinacao_ativo") and "mm_periodo" not in v:
            v["mm_periodo"] = 15
        variantes.append(v)
        mapa.append({"fold": r["fold"], "base_id": int(r["base_id"]), "controle": nome})

json.dump(mapa, open(saida_mapa, "w"))
json.dump({"nome": "pareado controles etapa 6", "base": {"penetracao_ticks": 1}, "variantes": variantes, "corte_oos": "2025-01-01",
           "janelas": {"trainA": ["2021-09-01", "2023-12-31"], "testA": ["2024-01-01", "2024-12-31"],
                       "trainB": ["2021-09-01", "2024-12-31"], "testB": ["2025-01-01", "2025-12-31"]},
           "ordenar_por": "trainB_ret_dd", "top": 5, "min_operacoes": 1}, open(saida, "w", encoding="utf-8"), ensure_ascii=False)
print(len(variantes), "combinações", file=sys.stderr)
