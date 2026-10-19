"""Prova de ausência de look-ahead no motor inteiro (indicadores + filtro + gatilho + ordem).

Método: roda o backtest nos dados reais/sintéticos e de novo com TODO o futuro depois de um instante `corte` destruído
(preços aleatórios, longe do original). Qualquer decisão tomada até `corte` precisa sair idêntica: se o motor (ou um
indicador, ou o filtro) espiasse algo posterior, as entradas até o corte mudariam.

Só as ENTRADAS são comparadas (lado, minuto, preço): a saída de uma posição depende, legitimamente, do que vem depois.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategylab.engine import data
from strategylab.engine.params import Params
from strategylab.engine.runner import rodar_trades
from tests.conftest import BD_PADRAO, csv_sintetico


def _rodar(raw: pd.DataFrame, p: Params) -> pd.DataFrame:
    barras, sub = data.preparar_barras(raw, 10)
    return rodar_trades(barras, p, sub)


def _entradas(tr: pd.DataFrame, corte: pd.Timestamp) -> list[tuple]:
    t = tr[tr["entrada_ts"] <= corte]
    return [(r.lado, r.entrada_ts, round(r.preco_entrada, 6)) for r in t.itertuples(index=False)]


def _destroi_o_futuro(raw: pd.DataFrame, corte: pd.Timestamp, semente: int) -> pd.DataFrame:
    rng = np.random.RandomState(semente)
    out = raw.copy()
    out[["open", "high", "low", "close"]] = out[["open", "high", "low", "close"]].astype(float)
    m = (out["datetime"] > corte).to_numpy()
    n = int(m.sum())
    base = rng.uniform(50_000, 300_000, n)
    o = base + rng.normal(0, 400, n)
    c = base + rng.normal(0, 400, n)
    out.loc[m, "open"] = o
    out.loc[m, "close"] = c
    out.loc[m, "high"] = np.maximum(o, c) + np.abs(rng.normal(0, 300, n))
    out.loc[m, "low"] = np.minimum(o, c) - np.abs(rng.normal(0, 300, n))
    return out


def _cortes(raw: pd.DataFrame, n: int, semente: int) -> list[pd.Timestamp]:
    """Instantes aleatórios dentro do horário de operação (inclui meio de barra), espalhados pelo período."""
    rng = np.random.RandomState(semente)
    dias = sorted(raw["date"].unique())
    out = []
    for d in rng.choice(dias[3:-1], size=n, replace=False):
        minuto = int(rng.randint(9 * 60 + 40, 16 * 60 + 30))
        out.append(pd.Timestamp(d) + pd.Timedelta(minutes=minuto))
    return sorted(out)


CASOS = {
    "filtro ligado, book cont": dict(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.1),
    "filtro ligado, book ambas, várias operações": dict(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.05,
                                                         book="ambas", operacoes_por_dia=4, mm_periodo=9),
    "filtro ligado, book recuo (ordem espera barras)": dict(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.05,
                                                             book="recuo", operacoes_por_dia=3),
    "filtro desligado": dict(operacoes_por_dia=3),
    "zona de 1 candle": dict(candles_gatilho=1, candles_media=2, operacoes_por_dia=3),
}


@pytest.mark.parametrize("nome", list(CASOS))
def test_futuro_destruido_nao_muda_as_entradas_sinteticas(nome):
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(**CASOS[nome])
    base = _rodar(raw, p)
    assert len(base) > 5, "o cenário precisa gerar entradas para o teste significar algo"
    verificados = 0
    for i, corte in enumerate(_cortes(raw, 14, semente=3)):
        alterado = _rodar(_destroi_o_futuro(raw, corte, semente=100 + i), p)
        assert _entradas(base, corte) == _entradas(alterado, corte), f"{nome}: entrada mudou com futuro destruído após {corte}"
        verificados += len(_entradas(base, corte))
    assert verificados > 20


@pytest.mark.lento
@pytest.mark.parametrize("nome", ["filtro ligado, book cont", "filtro ligado, book ambas, várias operações"])
def test_futuro_destruido_nao_muda_as_entradas_no_bd_real(nome):
    raw, _ = data.carregar_csv(str(BD_PADRAO))
    dias = sorted(raw["date"].unique())[:120]                 # os primeiros ~120 pregões bastam (a EMA já está formada)
    raw = raw[raw["date"].isin(dias)].reset_index(drop=True)
    p = Params(**CASOS[nome])
    base = _rodar(raw, p)
    assert len(base) > 20
    for i, corte in enumerate(_cortes(raw, 10, semente=8)):
        alterado = _rodar(_destroi_o_futuro(raw, corte, semente=500 + i), p)
        assert _entradas(base, corte) == _entradas(alterado, corte), f"{nome}: entrada mudou após {corte}"


def _forca_ema_para_dentro_do_candle_de_referencia(raw: pd.DataFrame, entrada: pd.Timestamp, mm_periodo: int) -> pd.DataFrame | None:
    """Troca o fechamento da barra da ENTRADA (o último minuto dela, que vem DEPOIS da entrada) por um valor que faz a EMA
    daquela barra cair no meio do candle anterior. Quem usasse a EMA da própria barra (look-ahead) passaria a reprovar a entrada."""
    from strategylab.engine.indicators import ema

    barras, _ = data.preparar_barras(raw, 10)
    inicio = entrada.floor("10min")
    ultimo_minuto = inicio + pd.Timedelta(minutes=9)
    if ultimo_minuto <= entrada:
        return None
    pos = np.flatnonzero((barras["datetime"] == inicio).to_numpy())
    achou = np.flatnonzero((raw["datetime"] == ultimo_minuto).to_numpy())
    if len(pos) != 1 or len(achou) != 1 or pos[0] < 2:
        return None
    i = int(pos[0])
    mmv = ema(barras["close"].to_numpy(float), mm_periodo)
    alfa = 2.0 / (mm_periodo + 1)
    meio = (float(barras["high"].iloc[i - 1]) + float(barras["low"].iloc[i - 1])) / 2.0
    x = (meio - (1 - alfa) * mmv[i - 1]) / alfa
    out = raw.copy()
    out[["open", "high", "low", "close"]] = out[["open", "high", "low", "close"]].astype(float)
    out.loc[achou[0], ["open", "high", "low", "close"]] = x
    return out


def _entradas_ate_a_propria_entrada(base: pd.DataFrame, p: Params, raw: pd.DataFrame, n: int, monkeypatch=None) -> tuple[int, int]:
    """Devolve (casos testados, casos em que a entrada mudou) ao perturbar o fechamento da barra de cada entrada."""
    testados = mudaram = 0
    for r in base.itertuples(index=False):
        if testados >= n:
            break
        alterado = _forca_ema_para_dentro_do_candle_de_referencia(raw, r.entrada_ts, p.mm_periodo)
        if alterado is None:
            continue
        testados += 1
        novo = _rodar(alterado, p)
        mudaram += _entradas(base, r.entrada_ts) != _entradas(novo, r.entrada_ts)
    return testados, mudaram


def test_o_fechamento_da_barra_da_entrada_nao_influencia_a_entrada():
    """Perturbação cirúrgica: mexe só no último minuto da barra da entrada, que acontece DEPOIS da entrada."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.3, operacoes_por_dia=4, book="ambas")
    base = _rodar(raw, p)
    testados, mudaram = _entradas_ate_a_propria_entrada(base, p, raw, n=25)
    assert testados >= 15 and mudaram == 0


def test_controle_o_teste_detecta_uma_espiada_intencional(monkeypatch):
    """Controle do próprio teste: se o motor lesse a EMA do fechamento da barra do gatilho (mm[i] em vez de mm[i-1]),
    a perturbação acima mudaria entradas. Se isto não falhar, os testes de look-ahead não valem nada."""
    import strategylab.engine.runner as runner

    original = runner.run_day_prep

    def espiando(dp, cfg, mm=None, ctx=None):
        mm = np.append(mm[1:], np.nan)             # o \"valor de i-1\" passa a ser a EMA do fechamento de i (shift(-1) no pregão)
        return original(dp, cfg, mm, ctx)

    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.3, operacoes_por_dia=4, book="ambas")
    monkeypatch.setattr(runner, "run_day_prep", espiando)
    base = _rodar(raw, p)
    testados, mudaram = _entradas_ate_a_propria_entrada(base, p, raw, n=25)
    assert testados >= 15 and mudaram > 0


@pytest.mark.lento
def test_o_fechamento_da_barra_da_entrada_nao_influencia_a_entrada_no_bd_real():
    raw, _ = data.carregar_csv(str(BD_PADRAO))
    dias = sorted(raw["date"].unique())[:80]
    raw = raw[raw["date"].isin(dias)].reset_index(drop=True)
    p = Params(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.7)
    base = _rodar(raw, p)
    testados, mudaram = _entradas_ate_a_propria_entrada(base, p, raw, n=30)
    assert testados >= 20 and mudaram == 0


# ------------------------------------------------------------------ Etapa 3: próximo candle e sair ao tocar a MM
# Aqui comparam-se também as SAÍDAS: com a MM envolvida, a saída de uma posição já fechada antes do corte só pode depender
# de dados até o corte. (Mais abaixo, a perturbação cirúrgica mexe no que vem DEPOIS da saída, dentro da mesma barra.)
CASOS_ETAPA3 = {
    "próximo candle": dict(modo_entrada="proximo_candle", operacoes_por_dia=3),
    "sair na MM": dict(sair_ao_tocar_mm=True, operacoes_por_dia=3),
    "próximo candle + sair na MM": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, operacoes_por_dia=3),
    "rastrear MM": dict(rastrear_mm=True, operacoes_por_dia=3),
    "rastrear MM + próximo candle + sair na MM": dict(rastrear_mm=True, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                      operacoes_por_dia=3),
    "reversões (stop/alvo próprios)": dict(reversoes=3, rev_stop_x_media=0.7, rev_alvo_x_media=2.0, operacoes_por_dia=2),
    "reversões + próximo candle + sair na MM + rastrear": dict(reversoes=2, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                               rastrear_mm=True, operacoes_por_dia=3),
    "zona de 1 candle + tudo ligado": dict(candles_gatilho=1, candles_media=2, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                           rastrear_mm=True, reversoes=2, operacoes_por_dia=3),
    "trailing + reversões": dict(trailing_inicio_r=0.5, reversoes=2, operacoes_por_dia=3),
    "trailing + próximo candle + sair na MM + rastrear": dict(trailing_inicio_r=0.6, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                              rastrear_mm=True, reversoes=1, operacoes_por_dia=3),
    "tudo ligado, book ambas": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True,
                                    filtro_afast_mm_x_media=0.1, book="ambas", operacoes_por_dia=4, mm_periodo=9, rastrear_mm=True, reversoes=2),
}


def _fechados(tr: pd.DataFrame, corte: pd.Timestamp) -> list[tuple]:
    t = tr[tr["saida_ts"] <= corte]
    return [(r.lado, r.entrada_ts, round(r.preco_entrada, 6), r.saida_ts, round(r.preco_saida, 6), r.saida_por, r.reversao)
            for r in t.itertuples(index=False)]


@pytest.mark.parametrize("nome", list(CASOS_ETAPA3))
def test_futuro_destruido_nao_muda_entradas_nem_saidas_etapa3(nome):
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(**CASOS_ETAPA3[nome])
    base = _rodar(raw, p)
    assert len(base) > 20
    if p.sair_ao_tocar_mm:
        assert (base["saida_por"] == "mm").sum() > 5, "o cenário precisa ter saídas pela MM"
    verificados = 0
    for i, corte in enumerate(_cortes(raw, 8, semente=3)):
        alterado = _rodar(_destroi_o_futuro(raw, corte, semente=100 + i), p)
        assert _entradas(base, corte) == _entradas(alterado, corte), f"{nome}: entrada mudou com futuro destruído após {corte}"
        assert _fechados(base, corte) == _fechados(alterado, corte), f"{nome}: saída mudou com futuro destruído após {corte}"
        verificados += len(_fechados(base, corte))
    assert verificados > 10


def _perturba_o_resto_da_barra_da_saida(raw: pd.DataFrame, saida: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp] | None:
    """Joga o ÚLTIMO minuto da barra de 10 min da saída para longe. Ele vem depois da saída, mas entra no fechamento/máxima/mínima
    da barra (e portanto na EMA dela). Quem usasse a MM da própria barra da saída (look-ahead) mudaria a saída."""
    inicio = saida.floor("10min")
    ultimo = inicio + pd.Timedelta(minutes=9)
    if ultimo <= saida:
        return None
    achou = np.flatnonzero((raw["datetime"] == ultimo).to_numpy())
    if len(achou) != 1:
        return None
    out = raw.copy()
    out[["open", "high", "low", "close"]] = out[["open", "high", "low", "close"]].astype(float)
    out.loc[achou[0], ["open", "high", "low", "close"]] = float(out.loc[achou[0], "close"]) + 4000.0
    return out, ultimo


def _saidas_mm_ate_a_propria_saida(base: pd.DataFrame, p: Params, raw: pd.DataFrame, n: int, por: str = "mm") -> tuple[int, int]:
    """(casos testados, casos em que algo fechado antes do minuto perturbado mudou)."""
    testados = mudaram = 0
    for r in base[base["saida_por"] == por].itertuples(index=False):
        if testados >= n:
            break
        pert = _perturba_o_resto_da_barra_da_saida(raw, r.saida_ts)
        if pert is None:
            continue
        alterado, ultimo = pert
        testados += 1
        novo = _rodar(alterado, p)
        corte = ultimo - pd.Timedelta(minutes=1)
        mudaram += _fechados(base, corte) != _fechados(novo, corte)
    return testados, mudaram


def test_a_mm_da_propria_barra_nao_influencia_a_saida():
    """Perturbação cirúrgica: mexe só no último minuto da barra da saída pela MM, que acontece DEPOIS da saída."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(sair_ao_tocar_mm=True, operacoes_por_dia=3)
    base = _rodar(raw, p)
    testados, mudaram = _saidas_mm_ate_a_propria_saida(base, p, raw, n=14)
    assert testados >= 10 and mudaram == 0


def test_o_trailing_da_propria_barra_nao_influencia_a_saida():
    """Perturbação cirúrgica: mexe só no último minuto da barra da saída pelo trailing (depois da saída). A proteção só pode ler barras FECHADAS."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(trailing_inicio_r=0.5, reversoes=2, operacoes_por_dia=3)
    base = _rodar(raw, p)
    testados, mudaram = _saidas_mm_ate_a_propria_saida(base, p, raw, n=14, por="trailing")
    assert testados >= 8 and mudaram == 0


def test_controle_o_teste_detecta_uma_espiada_na_saida_pela_mm(monkeypatch):
    """Controle: se o motor lesse a EMA do fechamento da PRÓPRIA barra (mm[j] em vez de mm[j-1]) ao sair, a perturbação mudaria saídas."""
    import strategylab.engine.runner as runner

    original = runner.run_day_prep

    def espiando(dp, cfg, mm=None, ctx=None):
        mm = np.append(mm[1:], np.nan)             # o \"valor de i-1\" passa a ser a EMA do fechamento de i (shift(-1) no pregão)
        return original(dp, cfg, mm, ctx)

    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(sair_ao_tocar_mm=True, operacoes_por_dia=3)
    monkeypatch.setattr(runner, "run_day_prep", espiando)
    base = _rodar(raw, p)
    testados, mudaram = _saidas_mm_ate_a_propria_saida(base, p, raw, n=14)
    assert testados >= 10 and mudaram > 0


def test_a_abertura_da_barra_seguinte_nao_decide_se_ha_sinal():
    """No próximo candle o preço da entrada é a abertura seguinte, mas o SINAL (e se a entrada existe) já está decidido antes dela:
    trocar a abertura da barra seguinte por qualquer valor não pode criar nem remover sinais, só mudar o preço dessa entrada."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(modo_entrada="proximo_candle", operacoes_por_dia=1)
    base = _rodar(raw, p)
    assert len(base) > 20
    for r in list(base.itertuples(index=False))[:15]:
        abertura = r.entrada_ts
        idx = np.flatnonzero((raw["datetime"] == abertura).to_numpy())
        assert len(idx) == 1
        alterado = raw.copy()
        alterado[["open", "high", "low", "close"]] = alterado[["open", "high", "low", "close"]].astype(float)
        alterado.loc[idx[0], "open"] = float(alterado.loc[idx[0], "open"]) + 25.0     # só o PREÇO da abertura
        alterado.loc[idx[0], "high"] = max(float(alterado.loc[idx[0], "high"]), float(alterado.loc[idx[0], "open"]))
        novo = _rodar(alterado, p)
        assert novo["entrada_ts"].tolist() == base["entrada_ts"].tolist()
        assert novo["lado"].tolist() == base["lado"].tolist()


def test_o_fechamento_da_barra_da_entrada_nao_influencia_o_rastrear_mm():
    """Perturbação cirúrgica: o último minuto da barra da entrada (depois da entrada) vai para longe; o Rastrear MM lê só a barra anterior."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=21).encode())
    p = Params(rastrear_mm=True, operacoes_por_dia=3)
    base = _rodar(raw, p)
    testados = mudaram = 0
    for r in base.itertuples(index=False):
        pert = _perturba_o_resto_da_barra_da_saida(raw, r.entrada_ts)
        if pert is None or testados >= 14:
            continue
        alterado, ultimo = pert
        testados += 1
        mudaram += _entradas(base, ultimo - pd.Timedelta(minutes=1)) != _entradas(_rodar(alterado, p), ultimo - pd.Timedelta(minutes=1))
    assert testados >= 10 and mudaram == 0


# ------------------------------------------------------------------ Etapa 6: filtros de regime e controle de cauda
CASOS_REGIME = {
    "gap + amplitude de ontem": dict(filtro_gap_ativo=True, filtro_gap_max_x_media=0.4, filtro_vol_ontem_ativo=True,
                                      filtro_vol_ontem_max=1.3, operacoes_por_dia=3),
    "bandas + inclinação da MM": dict(filtro_bb_ativo=True, filtro_bb_largura_min_pct=0.1, filtro_bb_largura_max_pct=0.4,
                                       filtro_inclinacao_ativo=True, filtro_inclinacao_max_x_media=0.4, operacoes_por_dia=3),
    "cauda: parar o dia + tempo máximo": dict(parar_dia_perda_x_media=1.0, tempo_max_min=60, reversoes=2, operacoes_por_dia=5),
    "candle discrepante": dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.3, reversoes=1, operacoes_por_dia=3),
    "tudo junto": dict(filtro_gap_ativo=True, filtro_gap_max_x_media=0.6, filtro_vol_ontem_ativo=True, filtro_vol_ontem_max=1.6,
                       filtro_bb_ativo=True, filtro_bb_largura_max_pct=0.5, filtro_inclinacao_ativo=True,
                       filtro_inclinacao_max_x_media=0.6, parar_dia_perda_x_media=1.5, tempo_max_min=120, reversoes=1,
                       modo_entrada="proximo_candle", operacoes_por_dia=4),
}


def _mercado_com_gaps(dias=50, semente=21):
    from tests.test_modos_vs_oraculo import com_saltos

    raw, _ = data.carregar_csv(csv_sintetico(dias=dias, semente=semente).encode())
    return com_saltos(raw)


@pytest.mark.parametrize("nome", list(CASOS_REGIME))
def test_futuro_destruido_nao_muda_entradas_nem_saidas_regime(nome):
    raw = _mercado_com_gaps()
    p = Params(**CASOS_REGIME[nome])
    base = _rodar(raw, p)
    assert len(base) > 15
    verificados = 0
    for i, corte in enumerate(_cortes(raw, 8, semente=3)):
        alterado = _rodar(_destroi_o_futuro(raw, corte, semente=100 + i), p)
        assert _entradas(base, corte) == _entradas(alterado, corte), f"{nome}: entrada mudou com futuro destruído após {corte}"
        assert _fechados(base, corte) == _fechados(alterado, corte), f"{nome}: saída mudou com futuro destruído após {corte}"
        verificados += len(_fechados(base, corte))
    assert verificados > 10


def test_o_resto_da_barra_da_entrada_nao_influencia_bandas_nem_inclinacao():
    """Perturbação cirúrgica: o último minuto da barra da entrada (depois dela) entra no fechamento/EMA/bandas DA PRÓPRIA barra e não pode decidir."""
    raw = _mercado_com_gaps()
    p = Params(**CASOS_REGIME["bandas + inclinação da MM"])
    base = _rodar(raw, p)
    testados = mudaram = 0
    for r in base.itertuples(index=False):
        pert = _perturba_o_resto_da_barra_da_saida(raw, r.entrada_ts)
        if pert is None or testados >= 14:
            continue
        alterado, ultimo = pert
        testados += 1
        corte = ultimo - pd.Timedelta(minutes=1)
        mudaram += _entradas(base, corte) != _entradas(_rodar(alterado, p), corte)
    assert testados >= 10 and mudaram == 0


def test_controle_detecta_espiada_na_largura_das_bandas(monkeypatch):
    """Controle: se o motor lesse a largura das bandas do fechamento da PRÓPRIA barra (bbw[i] em vez de bbw[i-1]), a perturbação mudaria entradas."""
    import strategylab.engine.runner as runner

    original = runner.run_day_prep

    def espiando(dp, cfg, mm=None, ctx=None):
        ctx = runner.Ctx(bbw=np.append(ctx.bbw[1:], np.nan), slope=ctx.slope, gap=ctx.gap, volp=ctx.volp)
        return original(dp, cfg, mm, ctx)

    raw = _mercado_com_gaps()
    p = Params(filtro_bb_ativo=True, filtro_bb_largura_min_pct=0.1, filtro_bb_largura_max_pct=0.35, operacoes_por_dia=3)
    monkeypatch.setattr(runner, "run_day_prep", espiando)
    base = _rodar(raw, p)
    testados = mudaram = 0
    for r in base.itertuples(index=False):
        pert = _perturba_o_resto_da_barra_da_saida(raw, r.entrada_ts)
        if pert is None or testados >= 25:
            continue
        alterado, ultimo = pert
        testados += 1
        corte = ultimo - pd.Timedelta(minutes=1)
        mudaram += _entradas(base, corte) != _entradas(_rodar(alterado, p), corte)
    assert testados >= 10 and mudaram > 0
