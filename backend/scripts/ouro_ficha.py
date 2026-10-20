"""Ficha de conferência de um pregão (cenários-ouro): o que o motor faz no dia, com os candles de 1 min para o Ricardo conferir à mão.

    python backend/scripts/ouro_ficha.py 2021-10-08 [2021-11-26 ...] [--estrategia short_stop_longo_b | --padrao] [--sub-candles]

Só LÊ o BD do projeto (dados/WIN_1M_21_25.csv, até 2025) e o JSON da estratégia; não grava nada. Datas depois de 2025-12-31 são recusadas.
Uma ficha NÃO é gabarito: o gabarito só nasce depois que o Ricardo confere e diz OK (backend/tests/ouro/cenarios_ouro.json).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
sys.dont_write_bytecode = True

from strategylab.engine.params import Params                        # noqa: E402
from strategylab.engine.runner import rodar_trades                  # noqa: E402
from strategylab.lab.executor import carregar_bd                    # noqa: E402
from strategylab.paths import BD_PADRAO, DATA_LIMITE_PESQUISA       # noqa: E402


def carregar_params(estrategia: str | None) -> tuple[str, Params]:
    if not estrategia:
        return "inicial_default (padrão)", Params()
    caminho = RAIZ / "estrategias" / f"{estrategia}.json"
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return f"{bruto.get('name', estrategia)} ({estrategia}.json)", Params(**bruto["params"])


def difere_do_padrao(p: Params) -> dict:
    padrao = Params().model_dump()
    return {k: v for k, v in p.model_dump().items() if padrao.get(k) != v}


def hm(ts) -> str:
    return pd.Timestamp(ts).strftime("%H:%M")


def sub_candles(barras: pd.DataFrame, ini, fim) -> list[tuple]:
    """Candles de 1 min entre `ini` e `fim` (inclusive), remontados das colunas so/sh/sl/sc de cada barra de 10 min."""
    n = 0
    while f"so{n}" in barras.columns:          # colunas so0..so{n-1}: o k-ésimo minuto da barra (k = deslocamento em minutos)
        n += 1
    linhas = []
    for _, b in barras.iterrows():
        for k in range(n):
            t = pd.Timestamp(b["datetime"]) + pd.Timedelta(minutes=k)
            if ini <= t <= fim and pd.notna(b[f"so{k}"]):
                linhas.append((t, b[f"so{k}"], b[f"sh{k}"], b[f"sl{k}"], b[f"sc{k}"]))
    return linhas


def media_op(dia: pd.DataFrame, j: int, p: Params) -> float:
    """media_operacao da barra j (índice dentro do pregão): média de (máx − mín) das `candles_media` barras FECHADAS antes dela.
    Com o filtro de candle discrepante ligado, o maior sai se for > X × o 2º maior. Conta independente do motor."""
    n = p.candles_media
    if j < n:
        return 0.0
    rr = sorted((dia["high"].to_numpy(float)[j - n:j] - dia["low"].to_numpy(float)[j - n:j]).tolist())
    if p.filtro_candle_discrepante_ativo and len(rr) >= 2 and rr[-1] > p.filtro_candle_discrepante_x * rr[-2]:
        rr = rr[:-1]
    return sum(rr) / len(rr) if rr else 0.0


def niveis(t, p: Params, dia: pd.DataFrame, ts) -> tuple[float, float, float]:
    """(media_op, stop, alvo) vigentes no minuto `ts`: o motor recalcula stop/alvo a cada barra com a media_operacao da barra corrente."""
    j = int((dia["datetime"] <= ts).sum()) - 1
    sm, am = (p.rev_stop_x_media, p.rev_alvo_x_media) if t.reversao > 0 else (p.stop_x_media, p.alvo_x_media)
    mop = media_op(dia, j, p)
    d = 1 if t.lado == "buy" else -1
    return mop, t.preco_entrada - d * sm * mop, t.preco_entrada + d * am * mop


def ficha(data: str, barras: pd.DataFrame, trades: pd.DataFrame, p: Params, com_sub: bool) -> None:
    dia = barras[barras["date"].astype(str) == data]
    print(f"\n{'=' * 100}\nPREGÃO {data}  ({len(dia)} barras de 10 min)\n{'=' * 100}")
    if dia.empty:
        print("(sem candles neste dia no BD)")
        return
    print(f"\nBarras de 10 min (hora = abertura da barra). Zona = máx/mín das {p.candles_gatilho} barra(s) FECHADA(S) antes dela;")
    print(f"media_op = média da amplitude das {p.candles_media} barras fechadas antes; ordem (fade) = zona ± {p.bracket_fracao} × media_op:")
    print("  hora     abertura   máxima   mínima  fechamento  amplit. | zona máx  zona mín  media_op  ordem VENDA  ordem COMPRA")
    dia = dia.reset_index(drop=True)
    hi, lo = dia["high"].to_numpy(float), dia["low"].to_numpy(float)
    for j, b in dia.iterrows():
        z = ""
        if j >= max(p.candles_gatilho, p.candles_media):
            zmax, zmin, mop = hi[j - p.candles_gatilho:j].max(), lo[j - p.candles_gatilho:j].min(), media_op(dia, j, p)
            z = f"| {zmax:8.0f} {zmin:9.0f} {mop:9.1f} {zmax + p.bracket_fracao * mop:12.0f} {zmin - p.bracket_fracao * mop:13.0f}"
        print(f"  {hm(b['datetime'])}  {b['open']:9.0f} {b['high']:8.0f} {b['low']:8.0f} {b['close']:10.0f} {b['high'] - b['low']:8.0f} {z}")
    t_dia = trades[trades["data"].astype(str) == data]
    if t_dia.empty:
        print("\nO motor NÃO operou neste pregão (nenhuma ordem executada).")
        return
    for i, (_, t) in enumerate(t_dia.iterrows(), 1):
        perna = "entrada original" if t.reversao == 0 else f"reversão nº {t.reversao}"
        print(f"\n--- Operação {i} ({perna}) · {'COMPRA' if t.lado == 'buy' else 'VENDA'} · {t.contratos} contrato(s) ---")
        print(f"  entrada {hm(t.entrada_ts)} a {t.preco_entrada:.0f}  →  saída {hm(t.saida_ts)} a {t.preco_saida:.0f}  ·  motivo: {t.saida_por}")
        print(f"  resultado: {t.pts:+.0f} pts = R$ {t.rs:+.2f}   (desfecho: {t.desfecho})")
        print(f"  media_operacao ao armar a ordem: {t.media_op:.1f} pts (stop e alvo usam a media_operacao de CADA barra: ver abaixo)")
        if p.trailing_inicio_r > 0:
            print("  ATENÇÃO: trailing ligado; os níveis abaixo NÃO incluem a proteção do trailing.")
        if pd.notna(t.ref_barra):
            print(f"  filtro de afastamento: candle de {hm(t.ref_barra)}, MM {t.ref_mm:.0f}, afastamento {t.ref_afast:.0f} pts")
        if com_sub:
            print("  candles de 1 min (abertura/máxima/mínima/fechamento | media_op da barra, stop e alvo vigentes; * = tocou stop, ^ = tocou alvo):")
            for ts, o, h, l, c in sub_candles(dia, pd.Timestamp(t.entrada_ts), pd.Timestamp(t.saida_ts)):
                d = 1 if t.lado == "buy" else -1
                mop, stop, alvo = niveis(t, p, dia, ts)
                toque_stop = mop > 0 and ((l <= stop) if d == 1 else (h >= stop))
                toque_alvo = mop > 0 and ((h >= alvo) if d == 1 else (l <= alvo))
                marca = ("*" if toque_stop else " ") + ("^" if toque_alvo else " ")
                print(f"    {hm(ts)}  {o:7.0f} {h:7.0f} {l:7.0f} {c:7.0f} | {mop:6.1f} {stop:8.0f} {alvo:8.0f}  {marca}")
    print(f"\nTotal do dia: {len(t_dia)} operação(ões), R$ {t_dia['rs'].sum():+.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datas", nargs="+", help="AAAA-MM-DD (até 2025-12-31)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--estrategia", help="id do arquivo em estrategias/ (ex.: short_stop_longo_b)")
    g.add_argument("--padrao", action="store_true", help="parâmetros do inicial_default")
    ap.add_argument("--sub-candles", action="store_true", help="imprime os candles de 1 min de cada operação")
    a = ap.parse_args()
    for d in a.datas:
        if d > DATA_LIMITE_PESQUISA:
            print(f"RECUSADO: {d} é depois de {DATA_LIMITE_PESQUISA} (hold-out do Ricardo).")
            return 2
    nome, p = carregar_params(None if a.padrao else a.estrategia)
    bd = carregar_bd(BD_PADRAO, RAIZ / "lab_cache")                    # recusa BD com datas > 2025
    import pickle
    with open(bd.caminho_mercado, "rb") as fh:
        mercado = pickle.load(fh)
    trades = rodar_trades(None, p, bd.sub_min, mercado)
    print(f"Estratégia: {nome}\nParâmetros diferentes do padrão: {json.dumps(difere_do_padrao(p), ensure_ascii=False)}")
    for d in a.datas:
        ficha(d, bd.barras, trades, p, a.sub_candles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
