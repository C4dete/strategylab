"""Indicadores: média móvel exponencial (EMA) e Bandas de Bollinger sobre a EMA.

REGRA DE OURO (sem look-ahead): cada função devolve, para a barra `t`, o valor que existe **no fechamento de `t`**
(ele usa o close de `t`). Quem decide algo na barra `i` só pode ler a posição `i - 1`. O motor faz isso explicitamente
em `ghost.py`; nada aqui é deslocado, para o gráfico mostrar o mesmo que as plataformas mostram.

A série é CONTÍNUA: a EMA atravessa os pregões (como no gráfico do Profit), então o primeiro candle de um dia já
tem EMA. Só os primeiros `periodo - 1` candles do BD ficam sem valor (NaN).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(close, periodo: int) -> np.ndarray:
    """EMA com alfa = 2/(periodo+1), semeada no primeiro close (`adjust=False`). NaN até haver `periodo` candles."""
    s = pd.Series(np.asarray(close, dtype=float))
    return s.ewm(span=int(periodo), adjust=False, min_periods=int(periodo)).mean().to_numpy()


def bollinger(close, periodo: int, k: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(central, superior, inferior): EMA(periodo) ± k × desvio-padrão populacional do close nos últimos `periodo` candles."""
    s = pd.Series(np.asarray(close, dtype=float))
    mid = s.ewm(span=int(periodo), adjust=False, min_periods=int(periodo)).mean().to_numpy()
    std = s.rolling(int(periodo)).std(ddof=0).to_numpy()
    return mid, mid + float(k) * std, mid - float(k) * std
