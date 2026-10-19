"""Ablação de UM controle por vez na v6 (motor antigo, dados até 2025). Descritivo: não escolhe nada."""
import os, sys, time
from datetime import time as T
from multiprocessing import Pool

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(SP)), "lab_cache")
sys.path.insert(0, SP)

V = {
    "BASE v6": {},
    # --- componentes ligados/desligados
    "sem trailing": dict(ghost_trail_start_r=0.0),
    "sem reversão": dict(ff2_max_reversals=0),
    "sem trailing e sem reversão": dict(ghost_trail_start_r=0.0, ff2_max_reversals=0),
    "filtro3 off": dict(ghost_filtro3="off"),
    "filtro3 contra": dict(ghost_filtro3="contra"),
    "zona mín 0 (sem filtro)": dict(ff2_range_min_pts=0.0),
    "zona mín 300": dict(ff2_range_min_pts=300.0),
    "zona mín 500": dict(ff2_range_min_pts=500.0),
    "sem filtro3 e sem zona mín": dict(ghost_filtro3="off", ff2_range_min_pts=0.0),
    "armar ambas": dict(ghost_armar="ambas"),
    "armar recuo": dict(ghost_armar="recuo"),
    # --- trailing
    "trail 1.0": dict(ghost_trail_start_r=1.0),
    "trail 1.3": dict(ghost_trail_start_r=1.3),
    "trail 2.0": dict(ghost_trail_start_r=2.0),
    "trail 2.5": dict(ghost_trail_start_r=2.5),
    # --- reversão
    "2 reversões": dict(ff2_max_reversals=2),
    "rev stop 0.5": dict(ghost_rev_stop_mult=0.5),
    "rev stop 1.5": dict(ghost_rev_stop_mult=1.5),
    "rev alvo 2": dict(ghost_rev_gain_mult=2.0),
    "rev alvo 3": dict(ghost_rev_gain_mult=3.0),
    "rev alvo 6": dict(ghost_rev_gain_mult=6.0),
    "rev alvo 8": dict(ghost_rev_gain_mult=8.0),
    # --- geometria
    "stop 0.8": dict(ff2_stop_mult=0.8), "stop 1.2": dict(ff2_stop_mult=1.2),
    "stop 1.5": dict(ff2_stop_mult=1.5), "stop 2.0": dict(ff2_stop_mult=2.0),
    "alvo 1.5": dict(ff2_gain_mult=1.5), "alvo 2": dict(ff2_gain_mult=2.0), "alvo 2.5": dict(ff2_gain_mult=2.5),
    "alvo 4": dict(ff2_gain_mult=4.0), "alvo 5": dict(ff2_gain_mult=5.0), "alvo 8": dict(ff2_gain_mult=8.0),
    "k 0": dict(ghost_k=0.0), "k 0.1": dict(ghost_k=0.1), "k 0.25": dict(ghost_k=0.25), "k 0.5": dict(ghost_k=0.5),
    "gatilho 3": dict(ff2_maxmin_n=3), "gatilho 4": dict(ff2_maxmin_n=4), "gatilho 6": dict(ff2_maxmin_n=6),
    "gatilho 8": dict(ff2_maxmin_n=8), "gatilho 12": dict(ff2_maxmin_n=12),
    "média 3": dict(ff2_media_op_n=3), "média 4": dict(ff2_media_op_n=4), "média 6": dict(ff2_media_op_n=6),
    "média 8": dict(ff2_media_op_n=8), "média 12": dict(ff2_media_op_n=12),
    # --- tempo e fila
    "ult. entrada 12:00": dict(ghost_ult_entrada_hhmm=1200), "ult. entrada 14:00": dict(ghost_ult_entrada_hhmm=1400),
    "ult. entrada 17:00": dict(ghost_ult_entrada_hhmm=1700),
    "início 09:30": dict(start_time=T(9, 30)), "início 10:00": dict(start_time=T(10, 0)),
    "penetração 0": dict(ghost_penetra_ticks=0), "penetração 2": dict(ghost_penetra_ticks=2),
    "penetração 3": dict(ghost_penetra_ticks=3),
    # --- ciclos
    "2 ciclos/dia": dict(ff2_max_trades=2), "3 ciclos/dia": dict(ff2_max_trades=3), "5 ciclos/dia": dict(ff2_max_trades=5),
}


def _init():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # below normal
    except Exception:
        pass
    global L
    import v6lab as L


def _run(item):
    nome, ov = item
    tr = L.rodar(**ov)
    m = L.metricas(tr)
    ya = L.por_ano(tr)
    A = L.metricas(tr, ate="2023-12-31")
    B = L.metricas(tr, de="2024-01-01")
    return nome, m, ya, A, B


if __name__ == "__main__":
    t0 = time.time()
    with Pool(5, initializer=_init) as pool:
        res = pool.map(_run, list(V.items()), chunksize=1)
    import pickle; pickle.dump(res, open(os.path.join(CACHE, "ablacao.pkl"), "wb"))
    print(f"{len(res)} variantes em {time.time()-t0:.0f}s\n")
    print(f"{'variante':32s} {'R$':>7s} {'DD':>7s} {'R/DD':>6s} {'ops':>5s} {'m+':>5s} {'pior mês':>8s} | "
          f"{'2021':>6s} {'2022':>6s} {'2023':>6s} {'2024':>6s} {'2025':>6s} | {'≤2023':>6s} {'24-25':>6s} {'R/DD ≤23':>8s} {'R/DD 24-25':>10s}")
    for nome, m, ya, A, B in res:
        print(f"{nome:32s} {m['total']:7.0f} {m['dd']:7.0f} {m['ret_dd']:6.1f} {m['n']:5d} {m['meses_pos']:2d}/{m['meses']:2d} {m['pior_mes']:8.0f} | "
              + " ".join(f"{ya.get(a, 0):6.0f}" for a in (2021, 2022, 2023, 2024, 2025))
              + f" | {A['total']:6.0f} {B['total']:6.0f} {A['ret_dd']:8.1f} {B['ret_dd']:10.1f}")
