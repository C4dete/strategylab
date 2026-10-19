"""Indicadores: definição exata e ausência de dependência do futuro."""

from __future__ import annotations

import numpy as np
import pytest

from strategylab.engine.indicators import bollinger, ema


def _serie(n=300, semente=5):
    rng = np.random.RandomState(semente)
    return 130000 + np.cumsum(rng.normal(0, 40, n))


def _ema_manual(x, p):
    """EMA por recursão em Python puro: alfa = 2/(p+1), semeada no 1º valor; só vale a partir do p-ésimo candle."""
    a = 2.0 / (p + 1)
    e, out = None, []
    for k, v in enumerate(x):
        e = v if e is None else a * v + (1 - a) * e
        out.append(e if k >= p - 1 else float("nan"))
    return np.array(out)


@pytest.mark.parametrize("p", [2, 9, 15, 50])
def test_ema_bate_com_a_recursao_manual(p):
    x = _serie()
    assert np.allclose(ema(x, p), _ema_manual(x, p), equal_nan=True)


def test_ema_nao_tem_valor_antes_de_periodo_candles():
    e = ema(_serie(40), 15)
    assert np.isnan(e[:14]).all() and not np.isnan(e[14:]).any()


def test_ema_reage_mais_rapido_que_a_media_simples():
    x = np.r_[np.full(30, 100.0), np.full(10, 200.0)]
    e = ema(x, 15)
    sma = np.array([np.nan] * 14 + [x[k - 14:k + 1].mean() for k in range(14, len(x))])
    assert e[-1] > sma[-1] > 100          # pesa os candles recentes (a EMA já andou mais que a simples)


def test_bollinger_definicao():
    x = _serie()
    mid, sup, inf = bollinger(x, 15, 2.0)
    assert np.allclose(mid, _ema_manual(x, 15), equal_nan=True)
    k = 200
    desvio = x[k - 14:k + 1].std(ddof=0)                  # populacional, janela = periodo
    assert sup[k] == pytest.approx(mid[k] + 2.0 * desvio)
    assert inf[k] == pytest.approx(mid[k] - 2.0 * desvio)
    assert np.isnan(sup[:14]).all()
    assert (sup[14:] >= mid[14:]).all() and (inf[14:] <= mid[14:]).all()


def test_bollinger_periodo_e_desvio_independentes():
    x = _serie()
    m1, s1, _ = bollinger(x, 15, 2.0)
    m2, s2, _ = bollinger(x, 30, 2.0)
    m3, s3, _ = bollinger(x, 15, 3.0)
    assert not np.allclose(m1[40:], m2[40:])
    assert np.allclose(m1, m3, equal_nan=True) and ((s3 - m3)[40:] == pytest.approx(1.5 * (s1 - m1)[40:]))


@pytest.mark.parametrize("p", [9, 15, 30])
def test_valor_de_t_nao_depende_de_nada_depois_de_t(p):
    """Sem look-ahead: truncar a série no candle t não muda nenhum valor até t, nem trocar todo o futuro por lixo."""
    x = _serie()
    cheio_e = ema(x, p)
    cheio_b = bollinger(x, p, 2.0)
    rng = np.random.RandomState(1)
    for t in (20, 77, 150, 299):
        assert np.allclose(ema(x[: t + 1], p), cheio_e[: t + 1], equal_nan=True)
        y = x.copy()
        y[t + 1:] = rng.uniform(1, 1e6, len(x) - t - 1)                # futuro destruído
        assert np.allclose(ema(y, p)[: t + 1], cheio_e[: t + 1], equal_nan=True)
        for a, b in zip(bollinger(y, p, 2.0), cheio_b):
            assert np.allclose(a[: t + 1], b[: t + 1], equal_nan=True)
