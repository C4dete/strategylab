"""Números-âncora no BD padrão inteiro (WIN_1M_21_25.csv, 1.073 pregões).

Os valores vieram de `scripts/paridade_motor_antigo.py`: o motor antigo (ghostcandle_v6, validado) e o
novo geraram trades IDÊNTICOS nestes 12 cenários. Se um destes testes quebrar, o motor mudou de comportamento.
"""

from __future__ import annotations

import pytest

from strategylab.engine.params import Params
from strategylab.engine.runner import executar, rodar_trades

pytestmark = pytest.mark.lento

# nome -> (parâmetros, nº de trades, resultado em R$)
CENARIOS = {
    "base": ({}, 1054, 7391.0),
    "book ambas": (dict(book="ambas"), 1073, -2071.0),
    "book recuo": (dict(book="recuo"), 1053, -13704.0),
    "book acima": (dict(book="acima"), 1059, 1404.0),
    "book abaixo": (dict(book="abaixo"), 1048, -7717.0),
    "penetracao 0": (dict(penetracao_ticks=0), 1057, 8045.0),
    "penetracao 3": (dict(penetracao_ticks=3), 1045, 4920.0),
    "5 ops, parar 2 dia": (dict(operacoes_por_dia=5, parar_apos_losses=2), 2592, -4820.0),
    "5 ops, parar 2 seguidos": (dict(operacoes_por_dia=5, parar_apos_losses=2, contagem_losses="seguidos"),
                                2712, -5853.0),
    "3 ops, stop 0,5, alvo 1,5": (dict(operacoes_por_dia=3, stop_x_media=0.5, alvo_x_media=1.5), 3117, 4550.0),
    "janela custom": (dict(janela_inicio="09:30", janela_fim="16:30", ultima_entrada="15:00", candles_gatilho=8,
                           candles_media=3, bracket_fracao=0.3, operacoes_por_dia=2), 1722, -8838.0),
    "sem ultima entrada": (dict(ultima_entrada=None, stop_x_media=2.0, alvo_x_media=6.0, book="ambas",
                                operacoes_por_dia=2), 1979, -8797.0),
}


@pytest.mark.parametrize("nome", list(CENARIOS))
def test_cenario_identico_ao_motor_antigo(barras_reais, nome):
    _, barras, sub = barras_reais
    over, n, total = CENARIOS[nome]
    tr = rodar_trades(barras, Params(**over), sub)
    assert len(tr) == n
    assert tr["rs"].sum() == pytest.approx(total)


def test_inicial_default_resumo_completo(barras_reais):
    _, barras, sub = barras_reais
    r = executar(barras, Params(), sub)["resumo"]
    assert r["total_rs"] == 7391.0 and r["total_pts"] == 36955.0
    assert r["operacoes"] == r["pregoes_operados"] == 1054
    assert (r["ganhos"], r["perdas"], r["zeradas"]) == (287, 763, 4)
    assert r["win_rate"] == pytest.approx(27.3333, abs=1e-3)
    assert r["drawdown"] == {"rs": -4730.0, "pts": -23650.0, "pico": "2022-11-30", "fundo": "2024-10-04",
                             "pregoes": 453}
    assert r["melhor_dia"] == {"data": "2022-11-18", "rs": 544.0}
    assert r["pior_dia"] == {"data": "2022-10-31", "rs": -191.0}
    assert r["seq_ganho"]["dias"] == 5 and r["seq_perda"]["dias"] == 19


def test_confere_com_o_simulador_independente(barras_reais):
    """Oráculo escrito do zero (sem reutilizar o motor): mesmos trades no cenário base."""
    from tests import oraculo_ref_simulador as ref

    df, barras, sub = barras_reais
    bruto = df.assign(vfin=1.0)
    c = ref.Cfg()
    c.rev_max = 0
    c.trail = 0.0
    c.filtro3 = "off"
    c.rangemin = 0.0
    ref_tr = ref.run(bruto, c)

    novo = rodar_trades(barras, Params(), sub)
    assert len(ref_tr) == len(novo) == 1054
    assert ref_tr["pts"].tolist() == novo["pts"].tolist()
    assert ref_tr["rs"].sum() == pytest.approx(novo["rs"].sum())


# ------------------------------------------------------------------ filtro "Afastamento da MM" (Etapa 2)
# (afastamento mínimo em x media_operacao, período da MM) -> (trades, R$). Valores conferidos contra o simulador independente.
FILTRO = {
    (0.7, 15): (926, 2220.0),
    (1.5, 15): (486, 2228.0),
    (0.3, 30): (1044, 5800.0),
}


@pytest.mark.parametrize("x, periodo", list(FILTRO))
def test_filtro_afastamento_confere_com_o_simulador_independente(barras_reais, x, periodo):
    """O simulador independente calcula a EMA por recursão própria e lê sempre a barra anterior (i-1) e a EMA do fechamento dela."""
    from tests import oraculo_ref_simulador as ref

    df, barras, sub = barras_reais
    c = ref.Cfg()
    c.rev_max = 0
    c.trail = 0.0
    c.filtro3 = "off"
    c.rangemin = 0.0
    c.afast, c.afast_p = x, periodo
    ref_tr = ref.run(df.assign(vfin=1.0), c)

    novo = rodar_trades(barras, Params(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=x, mm_periodo=periodo), sub)
    assert len(ref_tr) == len(novo)
    assert ref_tr["pts"].tolist() == novo["pts"].tolist()
    assert ref_tr["rs"].sum() == pytest.approx(novo["rs"].sum())
    assert 0 < len(novo) < 1054                              # o filtro realmente corta entradas
    print(f"\nfiltro x={x} mm={periodo}: {len(novo)} trades, R$ {novo['rs'].sum():.2f}")


# ------------------------------------------------------------------ Etapa 3: próximo candle e sair ao tocar a MM
# nome -> (parâmetros, trades, R$, saídas pela MM). Conferidos contra o simulador independente em
# `test_modos_vs_oraculo.py` (trade a trade, no BD inteiro). Com os dois controles desligados vale o cenário "base" acima.
MODOS = {
    "próximo candle": (dict(modo_entrada="proximo_candle"), 1054, 625.0, 0),
    "sair na MM": (dict(sair_ao_tocar_mm=True), 1054, 4365.0, 616),
    "os dois": (dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True), 1054, -1152.0, 636),
    "os dois + filtro 0,3": (dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True,
                                  filtro_afast_mm_x_media=0.3), 1033, -3043.0, 520),
    "sair na MM + filtro 0,2, 4 ops": (dict(sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.2,
                                            operacoes_por_dia=4), 3459, -4714.0, 1662),
    "1 reversão": (dict(reversoes=1), 1817, 6318.0, 0),
    "2 reversões, stop 0,5, alvo 2, 2 ops": (dict(reversoes=2, rev_stop_x_media=0.5, rev_alvo_x_media=2.0, operacoes_por_dia=2), 4693, 3188.0, 0),
    "rastrear MM": (dict(rastrear_mm=True), 1058, -909.0, 0),
    "rastrear MM + book ambas": (dict(rastrear_mm=True, book="ambas"), 1057, 376.0, 0),
    "rastrear MM + próximo candle + sair na MM, 3 ops": (dict(rastrear_mm=True, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                               operacoes_por_dia=3), 3103, -10966.0, 1734),
}


@pytest.mark.parametrize("nome", list(MODOS))
def test_modos_da_etapa_3_numeros_ancora(barras_reais, nome):
    _, barras, sub = barras_reais
    over, n, total, saidas_mm = MODOS[nome]
    tr = rodar_trades(barras, Params(**over), sub)
    assert len(tr) == n
    assert tr["rs"].sum() == pytest.approx(total)
    assert (tr["saida_por"] == "mm").sum() == saidas_mm


def test_controles_novos_desligados_nao_mudam_o_cenario_base(barras_reais):
    """Passar explicitamente os valores padrão dos controles novos é o mesmo que não passá-los: 1.054 trades, R$ 7.391."""
    _, barras, sub = barras_reais
    tr = rodar_trades(barras, Params(modo_entrada="padrao", sair_ao_tocar_mm=False), sub)
    assert len(tr) == 1054 and tr["rs"].sum() == pytest.approx(7391.0)
    assert set(tr["saida_por"]) <= {"stop", "alvo", "zeragem"}                      # sem MM, sem saída pela MM
