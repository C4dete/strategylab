"""Modelo de execução: preço de preenchimento, gap de stop e a estrutura de um trade.

Ordem LIMITE (passiva) preenche no nível, sem custo. Ordem a MERCADO (agressiva: stop e zeragem)
paga `slippage + spread/2` contra você e arredonda para a grade do tick, também contra você.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .ghost import Cfg


@dataclass
class Trade:
    ciclo: int
    lado: str                  # "buy" | "sell"
    entrada_ts: pd.Timestamp   # início do sub-candle em que a ordem encheu
    preco_entrada: float
    saida_ts: pd.Timestamp
    preco_saida: float
    contratos: int
    pts: float
    rs: float
    desfecho: str              # "gain" | "loss" | "time_close" | "eod"
    reversao: int = 0          # 0 = entrada original do ciclo; n = n-ésima reversão (mesmo `ciclo`)
    saida_por: str = ""        # "stop" | "trailing" | "alvo" | "mm" | "zeragem" | "fim_dados" | "tempo": o que encerrou a operação
    # Candle de referência do filtro "Afastamento da MM" (só preenchido com o filtro ligado):
    ref_barra: Optional[pd.Timestamp] = None   # início da barra fechada anterior à do gatilho
    ref_mm: float = float("nan")               # EMA no fechamento dessa barra
    ref_afast: float = float("nan")            # pts entre o candle e a MM (0 = toca/cruza a MM)
    media_op: float = float("nan")             # media_operacao vigente na decisão


def make_trade(ciclo, lado, entrada_ts, preco_entrada, saida_ts, preco_saida, desfecho, cfg: "Cfg",
               saida_por: str = "", reversao: int = 0) -> Trade:
    pts = (preco_saida - preco_entrada) if lado == "buy" else (preco_entrada - preco_saida)
    return Trade(
        ciclo=ciclo,
        lado=lado,
        entrada_ts=pd.Timestamp(entrada_ts),
        preco_entrada=float(preco_entrada),
        saida_ts=pd.Timestamp(saida_ts),
        preco_saida=float(preco_saida),
        contratos=cfg.contratos,
        pts=float(pts),
        rs=float(pts * cfg.contratos * cfg.valor_ponto),
        desfecho=desfecho,
        saida_por=saida_por,
        reversao=reversao,
    )


def _round_to_tick(price: float, tick: float, action: str, aggressive: bool) -> float:
    if not tick or tick <= 0:
        return price
    q = price / tick
    if aggressive:                       # arredonda contra: compra para cima, venda para baixo
        q = np.ceil(q) if action == "buy" else np.floor(q)
    else:
        q = np.round(q)
    return float(q) * tick


def fill(level: float, action: str, aggressive: bool, cfg: "Cfg") -> float:
    """Preço de execução. `action` é a ação de mercado desta ordem ('buy' | 'sell')."""
    price = float(level)
    if aggressive and (cfg.slippage or cfg.spread):
        adv = cfg.slippage + cfg.spread / 2.0
        price = price + adv if action == "buy" else price - adv
    return _round_to_tick(price, cfg.tick, action, aggressive)


def close_action(lado: str) -> str:
    return "sell" if lado == "buy" else "buy"


def gap_level(level: float, bar_open: float, action: str) -> float:
    """Nível real de um STOP disparado num sub-candle que já ABRIU além do nível: executa na abertura.

    Vale só para stops (disparados por rompimento adverso). Alvo e ordem limite descansam no nível.
    """
    o = float(bar_open)
    if np.isnan(o):
        return level
    return max(level, o) if action == "buy" else min(level, o)
