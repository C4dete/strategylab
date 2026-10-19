"""Teste PAREADO dos componentes da v6 em configurações sorteadas na vizinhança (motor antigo, dados até 2025).

Para cada configuração sorteada (trailing e reversão sempre ligados, filtro3 = 'ambos') roda também:
  filtro3 off, filtro3 contra, sem trailing, sem reversão  -> efeito marginal de cada componente com os OUTROS parâmetros variando.
Períodos: treino (<=2023) e teste (2024-2025). Descritivo: nada é escolhido aqui.
"""
import os, pickle, sys, time
from multiprocessing import Pool

import numpy as np

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(SP)), "lab_cache")
sys.path.insert(0, SP)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
rng = np.random.default_rng(20260109)
ESP = dict(
    ff2_stop_mult=[0.8, 1.0, 1.2, 1.5], ff2_gain_mult=[2.0, 3.0, 4.0, 5.0], ghost_k=[0.0, 0.05, 0.1, 0.15],
    ff2_maxmin_n=[4, 5, 6], ff2_media_op_n=[4, 5, 6], ghost_trail_start_r=[1.0, 1.3, 1.6, 2.0],
    ff2_max_reversals=[1, 2], ghost_rev_stop_mult=[0.0, 1.0], ghost_rev_gain_mult=[0.0, 3.0, 4.0],
    ghost_ult_entrada_hhmm=[1400, 1600], ff2_max_trades=[1, 2],
)
CONFIGS = []
for i in range(N):
    c = {k: v[int(rng.integers(len(v)))] for k, v in ESP.items()}
    c["ghost_filtro3"] = "ambos"
    CONFIGS.append(c)

TOGGLES = {
    "base": {},
    "f3_off": dict(ghost_filtro3="off"),
    "f3_contra": dict(ghost_filtro3="contra"),
    "sem_trail": dict(ghost_trail_start_r=0.0),
    "sem_rev": dict(ff2_max_reversals=0),
}
TASKS = [(i, t) for i in range(N) for t in TOGGLES]


def _init():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass
    global L
    import v6lab as L


def _run(task):
    i, t = task
    ov = dict(CONFIGS[i])
    ov.update(TOGGLES[t])
    tr = L.rodar(**ov)
    out = dict(i=i, t=t)
    for nome, kw in (("all", {}), ("treino", dict(ate="2023-12-31")), ("teste", dict(de="2024-01-01"))):
        m = L.metricas(tr, **kw)
        out[nome] = (m["total"], m["dd"], m["n"], m["meses_pos"], m["meses"])
    out["anos"] = L.por_ano(tr)
    return out


if __name__ == "__main__":
    t0 = time.time()
    with Pool(5, initializer=_init) as pool:
        res = pool.map(_run, TASKS, chunksize=1)
    pickle.dump(dict(res=res, configs=CONFIGS), open(os.path.join(CACHE, "pareado.pkl"), "wb"))
    print(f"{len(res)} execuções em {time.time()-t0:.0f}s")
