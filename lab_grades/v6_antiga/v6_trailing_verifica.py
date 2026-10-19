"""Verificação do TRAILING da v6 antiga: motor antigo x simulador independente (puro Python, minuto a minuto), dados até 2025.

    python lab_grades/v6_antiga/v6_trailing_verifica.py

Cada configuração roda nos dois e exige trades idênticos (data, lado, preço de entrada, preço de saída, pontos). Depois descreve o que o
trailing faz (quantas saídas pelo nível protegido, quantas armaram, resultado dessas pernas). Não altera nada do projeto.
"""
import os
import sys
import time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

CONFIGS = {
    # nome: (overrides do motor antigo, overrides do simulador independente)
    "v6 (trailing 1,6; 1 reversão)": ({}, {}),
    "trailing 1,0": (dict(ghost_trail_start_r=1.0), dict(trail=1.0)),
    "trailing 2,5": (dict(ghost_trail_start_r=2.5), dict(trail=2.5)),
    "trailing 1,0, sem reversão": (dict(ghost_trail_start_r=1.0, ff2_max_reversals=0), dict(trail=1.0, rev_max=0)),
    "trailing 1,0, 3 reversões (stop 0,7 / alvo 2)": (dict(ghost_trail_start_r=1.0, ff2_max_reversals=3, ghost_rev_stop_mult=0.7, ghost_rev_gain_mult=2.0),
                                                       dict(trail=1.0, rev_max=3, rev_s=0.7, rev_g=2.0)),
    "trailing 0,5, stop 2 / alvo 6": (dict(ghost_trail_start_r=0.5, ff2_stop_mult=2.0, ff2_gain_mult=6.0), dict(trail=0.5, stop=2.0, gain=6.0)),
}


def _init():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass


def _run(item):
    nome, (ov_antigo, ov_ref) = item
    import v6lab as L
    from strategylab.engine import data
    from tests import oraculo_ref_simulador as ref

    antigo = L.rodar(**ov_antigo)
    raw, _ = data.carregar_csv(str(L.CSV))
    c = ref.Cfg()
    for k, v in ov_ref.items():
        setattr(c, k, v)
    c.filtro3 = "ambos"
    r = ref.run(raw.assign(vfin=1.0), c)
    r = r.to_dict('records') if hasattr(r, 'to_dict') else r
    a = [(str(x.entry_time.date()), x.side, float(x.entry_price), float(x.exit_price), float(x.pts)) for x in antigo.itertuples(index=False)]
    b = [(str(t["date"]), t["side"], float(t["entry_fill"]), float(t["exit_fill"]), float(t["pts"])) for t in r]
    ok = a == b
    prim = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    n_prot = sum(1 for t in r if t["via_prot"] and t["by"] == "stop")
    n_armou = sum(1 for t in r if t["armed"])
    pts_prot = [t["pts"] for t in r if t["via_prot"] and t["by"] == "stop"]
    return nome, ok, len(a), len(b), prim, n_prot, n_armou, pts_prot, float(antigo["result_rs"].sum()), len(r)


if __name__ == "__main__":
    t0 = time.time()
    with Pool(3, initializer=_init) as pool:
        res = pool.map(_run, list(CONFIGS.items()), chunksize=1)
    print(f"{len(res)} configurações em {time.time() - t0:.0f}s\n")
    for nome, ok, na, nb, prim, n_prot, n_armou, pts_prot, rs, n in res:
        ganho = sum(1 for p in pts_prot if p > 0)
        med = sum(pts_prot) / len(pts_prot) if pts_prot else float("nan")
        print(f"[{'OK ' if ok else 'ERRO'}] {nome:48s} trades {na:5d}/{nb:5d}  R$ {rs:9.2f}  | saídas pelo nível protegido: {n_prot:4d} ({n_prot / max(n, 1) * 100:4.1f}% dos trades, "
              f"{ganho} com pts>0, média {med:6.1f} pts) | pernas que armaram o trailing: {n_armou}")
        if not ok:
            print(f"      primeira divergência no trade {prim}")
