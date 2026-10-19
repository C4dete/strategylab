"""Leitura e preparação do BD."""

from __future__ import annotations

import pytest

from strategylab.engine import data
from tests.conftest import csv_sintetico


def test_le_o_formato_do_bd_padrao(csv_pequeno):
    df, avisos = data.carregar_csv(csv_pequeno)
    info = data.informacoes(df, avisos)
    assert info.pregoes == 12
    assert info.timeframe_min == 1
    assert avisos == []
    assert list(df.columns) == ["datetime", "open", "high", "low", "close", "date"]


def test_ignora_linhas_vazias_no_fim():
    df, _ = data.carregar_csv(csv_sintetico(extra_vazias=30).encode())
    assert len(df) == len(data.carregar_csv(csv_sintetico().encode())[0])


def test_aceita_virgula_decimal_e_bom():
    texto = "﻿" + csv_sintetico(virgula=True)
    df, _ = data.carregar_csv(texto.encode("utf-8"))
    assert df["open"].notna().all()


def test_ordena_arquivo_em_ordem_decrescente():
    linhas = csv_sintetico().strip().split("\n")
    invertido = "\n".join([linhas[0]] + linhas[:0:-1]) + "\n"
    df, _ = data.carregar_csv(invertido.encode())
    assert df["datetime"].is_monotonic_increasing


def test_descarta_horarios_repetidos_com_aviso():
    linhas = csv_sintetico().strip().split("\n")
    texto = "\n".join(linhas + [linhas[5]]) + "\n"
    df, avisos = data.carregar_csv(texto.encode())
    assert any("repetido" in a for a in avisos)
    assert not df["datetime"].duplicated().any()


@pytest.mark.parametrize("texto, trecho", [
    ("", "vazio"),
    ("A;B;C\n1;2;3\n", "Cabeçalho"),
    ("CANDLE;OPEN;HIGH;LOW;CLOSE\n2024-03-04 09:00;1;2;1;1\n", "dd/mm/aaaa"),
    ("CANDLE;OPEN;HIGH;LOW;CLOSE\n04/03/2024 09:00;abc;2;1;1\n", "ilegível"),
])
def test_recusa_arquivos_fora_do_padrao(texto, trecho):
    with pytest.raises(data.DadosInvalidos, match=trecho):
        data.carregar_csv(texto.encode())


def test_recusa_poucos_dados():
    linhas = csv_sintetico().strip().split("\n")[:50]
    with pytest.raises(data.DadosInvalidos, match="Poucos dados"):
        data.carregar_csv("\n".join(linhas).encode())


def test_recusa_ohlc_impossivel_em_massa():
    linhas = csv_sintetico().strip().split("\n")
    ruins = [l.split(";") for l in linhas[1:]]
    for r in ruins:                       # máxima menor que a mínima
        r[2], r[3] = "100", "200"
    texto = "\n".join([linhas[0]] + [";".join(r) for r in ruins]) + "\n"
    with pytest.raises(data.DadosInvalidos, match="incoerente"):
        data.carregar_csv(texto.encode())


def test_prepara_barras_de_10_min_com_sub_candles(csv_pequeno):
    df, _ = data.carregar_csv(csv_pequeno)
    barras, sub = data.preparar_barras(df, 10)
    assert sub == 1
    assert (barras["datetime"].dt.minute % 10 == 0).all()
    cheias = barras[[f"sh{k}" for k in range(10)]].notna().all(axis=1)
    b = barras[cheias]
    assert (b[[f"sh{k}" for k in range(10)]].max(axis=1) == b["high"]).all()
    assert (b[[f"sl{k}" for k in range(10)]].min(axis=1) == b["low"]).all()
    assert (b["so0"] == b["open"]).all() and (b["sc9"] == b["close"]).all()


def test_aceita_base_de_5_minutos_e_recusa_o_que_nao_divide_10():
    df5, _ = data.carregar_csv(csv_sintetico(base_min=5).encode())
    _, sub = data.preparar_barras(df5, 10)
    assert sub == 5
    df3, _ = data.carregar_csv(csv_sintetico(base_min=3).encode())
    with pytest.raises(data.DadosInvalidos, match="candles de 3 min"):
        data.preparar_barras(df3, 10)
    df15, _ = data.carregar_csv(csv_sintetico(base_min=15).encode())
    with pytest.raises(data.DadosInvalidos, match="candles de 15 min"):
        data.preparar_barras(df15, 10)
