"""Fixtures compartilhadas e geradores de dados sintéticos."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]
BD_PADRAO = RAIZ / "dados" / "WIN_1M_21_25.csv"


def csv_sintetico(dias: int = 12, base_min: int = 1, semente: int = 7, inicio: str = "2024-03-04",
                  extra_vazias: int = 0, virgula: bool = False) -> str:
    """CSV no formato do BD (CANDLE;OPEN;HIGH;LOW;CLOSE;VFIN;VNEG) com passeio aleatório determinístico."""
    rng = np.random.RandomState(semente)
    linhas = ["CANDLE;OPEN;HIGH;LOW;CLOSE;VFIN;VNEG"]
    d = datetime.fromisoformat(inicio)
    preco = 130000.0
    feitos = 0
    while feitos < dias:
        if d.weekday() < 5:
            t = d.replace(hour=9, minute=0)
            while t.hour * 60 + t.minute < 17 * 60 + 55:
                o = preco
                passo = rng.normal(0, 25 * base_min ** 0.5)
                c = round((o + passo) / 5) * 5
                h = max(o, c) + abs(rng.normal(0, 15)) // 5 * 5
                l = min(o, c) - abs(rng.normal(0, 15)) // 5 * 5
                fmt = (lambda x: f"{x:.1f}".replace(".", ",")) if virgula else (lambda x: f"{x:.0f}")
                linhas.append(f"{t:%d/%m/%Y %H:%M};{fmt(o)};{fmt(h)};{fmt(l)};{fmt(c)};1000;100")
                preco = c
                t += timedelta(minutes=base_min)
            feitos += 1
        d += timedelta(days=1)
    linhas += [";;;;;;"] * extra_vazias
    return "\n".join(linhas) + "\n"


@pytest.fixture
def csv_pequeno() -> bytes:
    return csv_sintetico().encode("utf-8")


@pytest.fixture
def bd_sintetico_path(tmp_path) -> Path:
    p = tmp_path / "bd_padrao.csv"
    p.write_text(csv_sintetico(dias=15), encoding="utf-8")
    return p


@pytest.fixture(scope="session")
def barras_reais():
    """BD padrão inteiro, preparado uma vez por sessão de testes (~6 s)."""
    from strategylab.engine import data
    df, _ = data.carregar_csv(str(BD_PADRAO))
    barras, sub = data.preparar_barras(df, 10)
    return df, barras, sub
