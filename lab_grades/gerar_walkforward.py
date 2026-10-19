"""Busca ampla para o experimento walk-forward (caminho 1 da robustez).

    python lab_grades/gerar_walkforward.py 8000 7 > lab_grades/walkforward_busca.json

Sorteio uniforme num espaço de valores "redondos" (penetração fixa em 1). A mesma rodada mede, por combinação, as janelas:
  trainA 2021-09..2023-12 -> testA 2024     |     trainB 2021-09..2024-12 -> testB 2025
Assim dá para comparar critérios de SELEÇÃO: escolher usando só o treino e ver o que acontece no teste.
"""

import json
import random
import sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 7)

variantes, vistos = [], set()
while len(variantes) < N:
    v = {
        "candles_gatilho": rng.choice([3, 5, 8, 12, 20]),
        "candles_media": rng.choice([3, 5, 10]),
        "bracket_fracao": rng.choice([0.05, 0.25, 0.5, 1.0, 2.0]),
        "modo_entrada": rng.choice(["padrao", "padrao", "proximo_candle"]),
        "book": rng.choice(["cont", "ambas", "recuo"]),
        "operacoes_por_dia": rng.choice([1, 2, 3, 5]),
        "stop_x_media": rng.choice([0.5, 1.0, 1.5, 2.0, 3.0, 5.0]),
        "alvo_x_media": rng.choice([0.25, 0.5, 1.0, 2.0, 3.0, 5.0]),
        "janela_inicio": rng.choice(["09:00", "09:30", "10:00"]),
        "ultima_entrada": rng.choice(["12:00", "13:00", "15:00", "16:00"]),
        "reversoes": rng.choice([0, 0, 1, 2]),
        "rastrear_mm": rng.random() < 0.4,
        "sair_ao_tocar_mm": rng.random() < 0.4,
    }
    v["parar_apos_losses"] = rng.choice([0, 0, 1, 2])
    if v["parar_apos_losses"]:
        v["contagem_losses"] = rng.choice(["dia", "seguidos"])
    if v["reversoes"]:
        v["rev_stop_x_media"] = rng.choice([0.0, 0.5, 1.5])
        v["rev_alvo_x_media"] = rng.choice([0.0, 1.0, 3.0])
    afast = rng.choice([None, None, 0.3, 0.7, 1.5, 3.0])
    if afast is not None:
        v["filtro_afast_mm_ativo"] = True
        v["filtro_afast_mm_x_media"] = afast
    if afast is not None or v["rastrear_mm"] or v["sair_ao_tocar_mm"]:
        v["mm_periodo"] = rng.choice([9, 15, 30, 50])
    chave = json.dumps(v, sort_keys=True)
    if chave in vistos:
        continue
    vistos.add(chave)
    variantes.append(v)

print(json.dumps({
    "nome": "walkforward busca ampla", "base": {"penetracao_ticks": 1}, "variantes": variantes,
    "corte_oos": "2025-01-01",
    "janelas": {"trainA": ["2021-09-01", "2023-12-31"], "testA": ["2024-01-01", "2024-12-31"],
                "trainB": ["2021-09-01", "2024-12-31"], "testB": ["2025-01-01", "2025-12-31"]},
    "ordenar_por": "trainB_total_rs", "top": 10, "min_operacoes": 50,
}, ensure_ascii=False))
