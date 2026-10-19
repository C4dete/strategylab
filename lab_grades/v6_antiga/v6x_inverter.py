import os, sys, pickle, time
from multiprocessing import Pool
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import v6x_formacao as F
V = {
    "BASE (cancelar)": {},
    "inverter (ambos n=3)": dict(f3_acao="inverter"),
    "inverter só fundos subindo": dict(f3_acao="inverter", f3_modo="so_sobe"),
    "inverter só topos descendo": dict(f3_acao="inverter", f3_modo="so_desce"),
    "inverter n=4": dict(f3_acao="inverter", f3_n=4),
    "inverter + sem reversão": dict(f3_acao="inverter", ff2_max_reversals=0),
    "inverter + sem trailing": dict(f3_acao="inverter", ghost_trail_start_r=0.0),
    "inverter n=3 stop 1.5 alvo 2": dict(f3_acao="inverter", ff2_stop_mult=1.5, ff2_gain_mult=2.0),
    "inverter n=3 stop 0.8 alvo 3": dict(f3_acao="inverter", ff2_stop_mult=0.8),
}
def _run(item):
    nome, ov = item
    ov = dict(ov)
    extra = {k: ov.pop(k) for k in ("f3_acao",) if k in ov}
    import v6x_formacao as FF
    tr = FF.rodar_x_extra(extra, **ov)
    L = FF.L
    return nome, L.metricas(tr), L.por_ano(tr), L.metricas(tr, ate="2023-12-31"), L.metricas(tr, de="2024-01-01")
if __name__ == "__main__":
    t0 = time.time()
    with Pool(5, initializer=F._init) as pool:
        res = pool.map(_run, list(V.items()), chunksize=1)
    print(f"{len(res)} variantes em {time.time()-t0:.0f}s\n")
    print(f"{'variante':32s} {'R$':>7s} {'DD':>7s} {'R/DD':>6s} {'ops':>5s} {'m+':>5s} | {'2021':>6s} {'2022':>6s} {'2023':>6s} {'2024':>6s} {'2025':>6s} | {'R/DD<=23':>8s} {'R/DD 24-25':>10s}")
    for nome, m, ya, A, B in res:
        print(f"{nome:32s} {m['total']:7.0f} {m['dd']:7.0f} {m['ret_dd']:6.1f} {m['n']:5d} {m['meses_pos']:2d}/{m['meses']:2d} | " + " ".join(f"{ya.get(a, 0):6.0f}" for a in (2021, 2022, 2023, 2024, 2025)) + f" | {A['ret_dd']:8.1f} {B['ret_dd']:10.1f}")
