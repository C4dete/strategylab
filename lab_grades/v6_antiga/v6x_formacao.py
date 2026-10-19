"""Variações do freio de formação (cópia de pesquisa do motor v6; original intacto). Dados até 2025."""
import os, pickle, sys, time
from multiprocessing import Pool

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(SP)), "lab_cache")
sys.path.insert(0, SP)

V = {"BASE (n=3, ambos, estrito)": {}}
for n in (2, 3, 4, 5, 6):
    V[f"n={n} ambos estrito"] = dict(f3_n=n)
V["n=3 ambos NÃO estrito (>=)"] = dict(f3_n=3, f3_estrito=False)
V["n=4 ambos NÃO estrito"] = dict(f3_n=4, f3_estrito=False)
V["n=3 só fundos subindo"] = dict(f3_n=3, f3_modo="so_sobe")
V["n=3 só topos descendo"] = dict(f3_n=3, f3_modo="so_desce")
V["n=2 só fundos subindo"] = dict(f3_n=2, f3_modo="so_sobe")
V["n=2 só topos descendo"] = dict(f3_n=2, f3_modo="so_desce")
V["n=4 só fundos subindo"] = dict(f3_n=4, f3_modo="so_sobe")
V["n=4 só topos descendo"] = dict(f3_n=4, f3_modo="so_desce")
V["n=3 fechamentos (ambos)"] = dict(f3_n=3, f3_modo="fech")
V["n=4 fechamentos (ambos)"] = dict(f3_n=4, f3_modo="fech")
V["n=2 fechamentos (ambos)"] = dict(f3_n=2, f3_modo="fech")
V["contra n=2"] = dict(f3_n=2, ghost_filtro3="contra")
V["contra n=3"] = dict(f3_n=3, ghost_filtro3="contra")
V["contra n=4"] = dict(f3_n=4, ghost_filtro3="contra")
V["off (referência)"] = dict(ghost_filtro3="off")


def _init():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass
    global L, rodar_x
    import v6lab as L
    from v6x.strategy_ghost_v6x import run_day_ghost_v6 as run_x
    from ghostcandle.indicators import add_indicators
    from ghostcandle.strategies import params_from
    from ghostcandle.strategy import trades_to_df

    def rodar_x(**ov):
        kw = dict(L.PERFIL)
        extra = {k: ov.pop(k) for k in ("f3_n", "f3_modo", "f3_estrito", "f3_acao") if k in ov}
        kw.update(ov)
        p = params_from(L.PRESET, **kw)
        for k, v in extra.items():
            setattr(p, k, v)
        data = add_indicators(L.BARRAS, p)
        todos = []
        for _, d in data.groupby("date", sort=True):
            todos.extend(run_x(d, p))
        return trades_to_df(todos)


def rodar_x_extra(extra, **ov):
    return rodar_x(**{**extra, **ov})


def _run(item):
    nome, ov = item
    tr = rodar_x(**dict(ov))
    return nome, L.metricas(tr), L.por_ano(tr), L.metricas(tr, ate="2023-12-31"), L.metricas(tr, de="2024-01-01")


if __name__ == "__main__":
    t0 = time.time()
    with Pool(5, initializer=_init) as pool:
        res = pool.map(_run, list(V.items()), chunksize=1)
    pickle.dump(res, open(os.path.join(CACHE, "formacao.pkl"), "wb"))
    print(f"{len(res)} variantes em {time.time()-t0:.0f}s\n")
    print(f"{'variante':30s} {'R$':>7s} {'DD':>7s} {'R/DD':>6s} {'ops':>5s} {'m+':>5s} | {'2021':>6s} {'2022':>6s} {'2023':>6s} {'2024':>6s} {'2025':>6s} | {'R/DD<=23':>8s} {'R/DD 24-25':>10s}")
    for nome, m, ya, A, B in res:
        print(f"{nome:30s} {m['total']:7.0f} {m['dd']:7.0f} {m['ret_dd']:6.1f} {m['n']:5d} {m['meses_pos']:2d}/{m['meses']:2d} | "
              + " ".join(f"{ya.get(a, 0):6.0f}" for a in (2021, 2022, 2023, 2024, 2025)) + f" | {A['ret_dd']:8.1f} {B['ret_dd']:10.1f}")
