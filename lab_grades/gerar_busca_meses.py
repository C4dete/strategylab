"""Gera a grade da busca "mais meses positivos": sorteio aleatório no espaço inteiro (etapa 1).

    python lab_grades/gerar_busca_meses.py 5000 1 > lab_grades/busca_meses_etapa1.json

Valores "redondos" (sem passos de 0,05); penetração fixa em 1 (padrão). Campos que não fazem efeito numa combinação
(ex.: stop da reversão sem reversões, período da MM sem nenhum controle de MM) ficam no padrão para o laboratório deduplicar.
"""

import json
import random
import sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
SEMENTE = int(sys.argv[2]) if len(sys.argv) > 2 else 1
rng = random.Random(SEMENTE)

variantes = []
vistos = set()
while len(variantes) < N:
    v = {
        "candles_gatilho": rng.choice([3, 5, 8, 12]),
        "candles_media": rng.choice([3, 5, 10]),
        "bracket_fracao": rng.choice([0.05, 0.25, 0.5, 1.0]),
        "modo_entrada": rng.choice(["padrao", "proximo_candle"]),
        "book": rng.choice(["cont", "ambas", "recuo"]),
        "operacoes_por_dia": rng.choice([1, 2, 3, 5]),
        "stop_x_media": rng.choice([0.5, 1.0, 1.5, 2.0, 3.0]),
        "alvo_x_media": rng.choice([0.5, 1.0, 2.0, 3.0, 5.0]),
        "janela_inicio": rng.choice(["09:00", "09:30", "10:00"]),
        "ultima_entrada": rng.choice(["13:00", "15:00", "16:00"]),
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
    afast = rng.choice([None, None, 0.3, 0.7, 1.5])
    if afast is not None:
        v["filtro_afast_mm_ativo"] = True
        v["filtro_afast_mm_x_media"] = afast
    if afast is not None or v["rastrear_mm"] or v["sair_ao_tocar_mm"]:
        v["mm_periodo"] = rng.choice([9, 15, 30])
    chave = json.dumps(v, sort_keys=True)
    if chave in vistos:
        continue
    vistos.add(chave)
    variantes.append(v)

print(json.dumps({
    "nome": f"busca meses etapa1 (semente {SEMENTE})",
    "base": {"penetracao_ticks": 1},
    "variantes": variantes,
    "corte_oos": "2025-01-01",
    "ordenar_por": "meses_pos",
    "top": 20,
    "min_operacoes": 100,
}, ensure_ascii=False))
