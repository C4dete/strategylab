"""Cruza as finalistas #414 e #220 da busca de meses positivos: sorteia N combinações do produto dos valores de cada uma.

    python lab_grades/gerar_combinacao_414_220.py 4500 > lab_grades/combinacao_414_220.json

#414: gatilho 8, média 10, bracket 0,5, recuo, 2 ops, stop 5, alvo 0,25, 10:00-15:00, Rastrear + Sair na MM (MM 30), sem filtro.
#220: gatilho 20, média 3, bracket 0,25, cont, 2 ops, stop 1, alvo 0,5, 09:00-15:00, parar 2 seguidos, Afastamento 1,5x (MM 50).
"""

import itertools
import json
import random
import sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4500
rng = random.Random(414220)

EIXOS = {
    "candles_gatilho": [8, 20],
    "candles_media": [3, 10],
    "bracket_fracao": [0.25, 0.5],
    "book": ["cont", "recuo"],
    "stop_x_media": [1.0, 2.0, 3.0, 5.0],
    "alvo_x_media": [0.25, 0.5],
    "janela_inicio": ["09:00", "10:00"],
    "parar": [0, 2],
    "afast": [None, 1.5],
    "rastrear_mm": [False, True],
    "sair_ao_tocar_mm": [False, True],
    "mm_periodo": [30, 50],
}
todas = list(itertools.product(*EIXOS.values()))
rng.shuffle(todas)

variantes, vistos = [], set()
for vals in todas:
    d = dict(zip(EIXOS, vals))
    v = {k: d[k] for k in ("candles_gatilho", "candles_media", "bracket_fracao", "book", "stop_x_media", "alvo_x_media",
                           "janela_inicio", "rastrear_mm", "sair_ao_tocar_mm")}
    v.update(operacoes_por_dia=2, ultima_entrada="15:00", modo_entrada="padrao")
    if d["parar"]:
        v.update(parar_apos_losses=d["parar"], contagem_losses="seguidos")
    if d["afast"] is not None:
        v.update(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=d["afast"])
    if d["afast"] is not None or d["rastrear_mm"] or d["sair_ao_tocar_mm"]:
        v["mm_periodo"] = d["mm_periodo"]
    chave = json.dumps(v, sort_keys=True)
    if chave in vistos:
        continue
    vistos.add(chave)
    variantes.append(v)
    if len(variantes) >= N:
        break

print(json.dumps({
    "nome": "combinacao 414 x 220", "base": {"penetracao_ticks": 1}, "variantes": variantes,
    "corte_oos": "2025-01-01", "ordenar_por": "meses_pos", "top": 20, "min_operacoes": 100,
}, ensure_ascii=False))
