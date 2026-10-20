"""Validação dos parâmetros e métricas (drawdown, sequências, mensal)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from strategylab.engine import metrics
from strategylab.engine.params import Params, hhmm_para_min, params_padrao


def test_padrao_equivale_ao_v6_10min_nos_12_campos():
    p = params_padrao()
    assert (p.janela_inicio, p.janela_fim, p.ultima_entrada) == ("09:00", "17:30", "16:00")
    assert (p.candles_gatilho, p.candles_media, p.bracket_fracao) == (5, 5, 0.05)
    assert (p.book, p.penetracao_ticks, p.parar_apos_losses, p.contagem_losses) == ("cont", 1, 0, "dia")
    assert (p.operacoes_por_dia, p.stop_x_media, p.alvo_x_media) == (1, 1.0, 3.0)


def test_campos_ausentes_assumem_o_padrao_e_extras_sao_ignorados():
    p = Params.model_validate({"stop_x_media": 2.0, "campo_futuro": 1})
    assert p.stop_x_media == 2.0 and p.candles_gatilho == 5


@pytest.mark.parametrize("campo, valor", [
    ("candles_gatilho", 0), ("candles_gatilho", 31), ("bracket_fracao", 0.01), ("penetracao_ticks", 6),
    ("parar_apos_losses", -1), ("operacoes_por_dia", 0), ("stop_x_media", 0.0), ("alvo_x_media", 9.0),
    ("book", "tudo"), ("contagem_losses", "mes"), ("janela_inicio", "9:00"), ("janela_fim", "24:00"),
])
def test_recusa_valores_fora_da_faixa(campo, valor):
    with pytest.raises(ValidationError):
        Params(**{campo: valor})


def test_coerencia_dos_horarios():
    with pytest.raises(ValidationError, match="início da janela"):
        Params(janela_inicio="17:30", janela_fim="09:00")
    with pytest.raises(ValidationError, match="depois do início"):
        Params(ultima_entrada="08:00")
    with pytest.raises(ValidationError, match="depois da zeragem"):
        Params(ultima_entrada="18:00")
    assert Params(ultima_entrada=None).ultima_entrada is None


def test_arredonda_passos_de_0_05():
    assert Params(bracket_fracao=0.1 + 0.05).bracket_fracao == 0.15
    assert hhmm_para_min("16:30") == 990


def _diario(valores):
    d = pd.DataFrame({"data": [date(2024, 1, 1 + i) for i in range(len(valores))],
                      "rs": valores, "pts": [v * 5 for v in valores],
                      "operacoes": 1, "ganhos": [int(v > 0) for v in valores],
                      "perdas": [int(v < 0) for v in valores], "zeradas": 0})
    d["acumulado"] = d["rs"].cumsum()
    return d


def test_drawdown_pico_fundo_e_dias():
    d = _diario([100, -50, -80, 30, 200, -300, -100])     # topo 330 (dia 5) -> fundo -70...
    dd = metrics.drawdown(d)
    assert dd["rs"] == -400.0
    assert dd["pico"] == date(2024, 1, 5) and dd["fundo"] == date(2024, 1, 7)
    assert dd["pregoes"] == 2 and dd["pts"] == -2000.0


def test_drawdown_sem_queda():
    assert metrics.drawdown(_diario([10, 20]))["rs"] == 0.0
    assert metrics.drawdown(_diario([]))["pico"] is None


def test_sequencias_e_desempate_pelo_valor():
    d = _diario([10, 20, -5, 5, 30, -1, -9, -2])
    s = metrics.sequencias(d)
    assert s["ganho"]["dias"] == 2 and s["ganho"]["total"] == 35.0     # empate (10+20 x 5+30): o maior valor ganha
    assert s["perda"]["dias"] == 3 and s["perda"]["total"] == -12.0


def test_metricas_globais_e_win_rate_por_operacao():
    d = _diario([100, -50, 30])
    g = metrics.metricas_globais(d)
    assert g["total_rs"] == 80 and g["pregoes"] == 3
    assert g["win_rate"] == pytest.approx(2 / 3 * 100)
    assert g["melhor_dia"]["rs"] == 100 and g["pior_dia"]["rs"] == -50


def test_resumo_mensal():
    d = _diario([10, -5, 20])
    d.loc[2, "data"] = date(2024, 2, 1)
    m = metrics.resumo_mensal(d)
    assert list(m["mes"]) == ["2024-01", "2024-02"]
    assert list(m["rs"]) == [5, 20] and list(m["dias_positivos"]) == [1, 1]
    assert list(m["operado"]) == [True, True]


def test_resumo_mensal_acrescenta_os_meses_sem_operacao_sem_mudar_os_totais():
    d = _diario([10, -5, 20])
    d.loc[2, "data"] = date(2024, 3, 1)                       # janeiro e março operados; fevereiro, não
    sem = metrics.resumo_mensal(d)
    com = metrics.resumo_mensal(d, meses_bd=["2023-12", "2024-01", "2024-02", "2024-03", "2024-04"])
    assert list(com["mes"]) == ["2023-12", "2024-01", "2024-02", "2024-03", "2024-04"]      # ordem cronológica, bordas incluídas
    assert list(com["operado"]) == [False, True, False, True, False]
    vazios = com[~com["operado"]]
    assert (vazios[["rs", "pts", "dias", "dias_positivos"]] == 0).all().all()               # zerados
    assert com["rs"].sum() == sem["rs"].sum() and com["dias"].sum() == sem["dias"].sum()   # os totais não mudam
    pd.testing.assert_frame_equal(com[com["operado"]].reset_index(drop=True)[["mes", "rs", "dias"]], sem[["mes", "rs", "dias"]], check_dtype=False)


def test_resumo_mensal_sem_nenhuma_operacao_lista_todos_os_meses_do_bd():
    m = metrics.resumo_mensal(metrics.resumo_diario(metrics.trades_para_df([])), meses_bd=["2024-01", "2024-02"])
    assert list(m["mes"]) == ["2024-01", "2024-02"] and not m["operado"].any()


# ------------------------------------------------------------------ Etapa 2: indicadores e filtro
def test_padrao_da_etapa_2():
    p = params_padrao()
    assert (p.mm_periodo, p.bb_periodo, p.bb_desvio) == (15, 15, 2.0)
    assert p.filtro_afast_mm_ativo is False and p.filtro_afast_mm_x_media == 0.7


@pytest.mark.parametrize("campo, valor", [
    ("mm_periodo", 1), ("mm_periodo", 201), ("bb_periodo", 1), ("bb_desvio", 0.4), ("bb_desvio", 5.5),
    ("filtro_afast_mm_x_media", 0.0), ("filtro_afast_mm_x_media", 10.5),
])
def test_recusa_indicadores_e_filtro_fora_da_faixa(campo, valor):
    with pytest.raises(ValidationError):
        Params(**{campo: valor})


def test_arquivo_da_etapa_1_continua_valido_e_com_filtro_desligado():
    antigo = {"janela_inicio": "09:00", "janela_fim": "17:30", "stop_x_media": 1.0}
    p = Params.model_validate(antigo)
    assert p.filtro_afast_mm_ativo is False and p.mm_periodo == 15


def test_chave_do_cache_so_muda_com_o_que_muda_o_resultado():
    base = Params()
    assert base.chave_motor() == Params(bb_periodo=30, bb_desvio=3.0).chave_motor()         # Bollinger: só gráfico
    assert base.chave_motor() == Params(mm_periodo=50).chave_motor()                        # MM sem filtro: nada muda
    assert base.chave_motor() == Params(filtro_afast_mm_x_media=2.0).chave_motor()          # valor do filtro desligado
    assert base.chave_motor() != Params(filtro_afast_mm_ativo=True).chave_motor()
    ligado = Params(filtro_afast_mm_ativo=True)
    assert ligado.chave_motor() != Params(filtro_afast_mm_ativo=True, mm_periodo=50).chave_motor()
    assert ligado.chave_motor() != Params(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=1.0).chave_motor()
    assert ligado.chave_motor() == Params(filtro_afast_mm_ativo=True, bb_periodo=40).chave_motor()


# ------------------------------------------------------------------ Etapa 3: modo de entrada e saída na MM
def test_padrao_da_etapa_3():
    p = params_padrao()
    assert p.modo_entrada == "padrao" and p.sair_ao_tocar_mm is False


def test_recusa_modo_de_entrada_desconhecido():
    with pytest.raises(ValidationError):
        Params(modo_entrada="abertura")
    assert Params(modo_entrada="proximo_candle").modo_entrada == "proximo_candle"


def test_arquivo_das_etapas_1_e_2_continua_valido_com_os_controles_novos_desligados():
    antigo = {"janela_inicio": "09:00", "mm_periodo": 20, "filtro_afast_mm_ativo": True}
    p = Params.model_validate(antigo)
    assert p.modo_entrada == "padrao" and p.sair_ao_tocar_mm is False and p.mm_periodo == 20


def test_chave_do_cache_com_modo_de_entrada_e_saida_na_mm():
    base = Params()
    assert base.chave_motor() != Params(modo_entrada="proximo_candle").chave_motor()
    assert base.chave_motor() != Params(sair_ao_tocar_mm=True).chave_motor()
    # a saída na MM passa a depender do período da MM, mesmo com o filtro de afastamento desligado
    com_saida = Params(sair_ao_tocar_mm=True)
    assert com_saida.chave_motor() != Params(sair_ao_tocar_mm=True, mm_periodo=50).chave_motor()
    # ...mas não do valor do filtro desligado, nem das Bandas de Bollinger
    assert com_saida.chave_motor() == Params(sair_ao_tocar_mm=True, filtro_afast_mm_x_media=2.0).chave_motor()
    assert com_saida.chave_motor() == Params(sair_ao_tocar_mm=True, bb_periodo=40, bb_desvio=3.0).chave_motor()
    # sem a saída e sem o filtro, o período da MM continua sem importar
    assert base.chave_motor() == Params(mm_periodo=50).chave_motor()
    assert Params(modo_entrada="proximo_candle").chave_motor() == Params(modo_entrada="proximo_candle", mm_periodo=50).chave_motor()


def test_trades_para_df_leva_o_motivo_da_saida():
    from datetime import datetime

    from strategylab.engine.fills import Trade

    t = Trade(ciclo=1, lado="sell", entrada_ts=datetime(2024, 1, 2, 10, 0), preco_entrada=100.0,
              saida_ts=datetime(2024, 1, 2, 10, 5), preco_saida=95.0, contratos=1, pts=5.0, rs=1.0,
              desfecho="gain", saida_por="mm")
    assert metrics.trades_para_df([t])["saida_por"].tolist() == ["mm"]
    assert "saida_por" in metrics.trades_para_df([]).columns


# ------------------------------------------------------------------ Etapa 4: Rastrear MM
def test_rastrear_mm_padrao_e_arquivo_antigo():
    assert params_padrao().rastrear_mm is False
    assert Params.model_validate({"modo_entrada": "proximo_candle"}).rastrear_mm is False


def test_chave_do_cache_com_rastrear_mm():
    base = Params()
    assert base.chave_motor() != Params(rastrear_mm=True).chave_motor()
    assert Params(rastrear_mm=True).chave_motor() != Params(rastrear_mm=True, mm_periodo=50).chave_motor()   # a MM passa a importar
    assert Params(rastrear_mm=True).chave_motor() == Params(rastrear_mm=True, bb_periodo=40).chave_motor()
    assert base.chave_motor() == Params(mm_periodo=50).chave_motor()


# ------------------------------------------------------------------ Etapa 5: reversões
def test_padrao_das_reversoes_e_arquivo_antigo():
    p = params_padrao()
    assert (p.reversoes, p.rev_stop_x_media, p.rev_alvo_x_media) == (0, 0.0, 0.0)
    assert Params.model_validate({"stop_x_media": 2}).reversoes == 0


@pytest.mark.parametrize("campo, valor", [("reversoes", -1), ("reversoes", 6), ("rev_stop_x_media", -0.1),
                                          ("rev_stop_x_media", 10.5), ("rev_alvo_x_media", -1), ("rev_alvo_x_media", 11)])
def test_recusa_reversoes_fora_da_faixa(campo, valor):
    with pytest.raises(ValidationError):
        Params(**{campo: valor})
    assert Params(reversoes=5).reversoes == 5                      # o máximo são 5


def test_chave_do_cache_com_reversoes():
    base = Params()
    assert base.chave_motor() != Params(reversoes=1).chave_motor()
    assert base.chave_motor() == Params(rev_stop_x_media=2.0, rev_alvo_x_media=3.0).chave_motor()   # sem reversões, stop/alvo da reversão não importam
    assert Params(reversoes=2).chave_motor() != Params(reversoes=2, rev_stop_x_media=1.0).chave_motor()
    assert Params(reversoes=2).chave_motor() != Params(reversoes=2, rev_alvo_x_media=1.0).chave_motor()


# ------------------------------------------------------------------ Etapa 6: cauda e filtros de regime
def test_padrao_da_etapa_6_e_neutro():
    p = params_padrao()
    assert (p.parar_dia_perda_x_media, p.tempo_max_min) == (0.0, 0)
    assert not (p.filtro_gap_ativo or p.filtro_vol_ontem_ativo or p.filtro_bb_ativo or p.filtro_inclinacao_ativo)
    assert Params.model_validate({"stop_x_media": 2}).filtro_bb_ativo is False          # arquivo antigo continua válido


@pytest.mark.parametrize("campo, valor", [
    ("parar_dia_perda_x_media", -1), ("parar_dia_perda_x_media", 21), ("tempo_max_min", -1), ("tempo_max_min", 481),
    ("filtro_gap_max_x_media", 0.04), ("filtro_gap_max_x_media", 5.1), ("filtro_vol_ontem_max", 0.4), ("filtro_vol_ontem_max", 5.1),
    ("filtro_bb_largura_min_pct", -0.1), ("filtro_bb_largura_max_pct", 0.0), ("filtro_inclinacao_barras", 1),
    ("filtro_inclinacao_barras", 31), ("filtro_inclinacao_max_x_media", 0.0), ("escada_contratos", -1), ("escada_contratos", 101), ("escada_ganho_qtd", 0), ("escada_perda_qtd", 21), ("escada_min", 0), ("escada_max", 101),
    ("trailing_inicio_r", -0.1), ("trailing_inicio_r", 10.1), ("filtro_candle_discrepante_x", 0.9), ("filtro_candle_discrepante_x", 10.1),
])
def test_recusa_cauda_e_regime_fora_da_faixa(campo, valor):
    with pytest.raises(ValidationError):
        Params(**{campo: valor})


def test_escada_de_contratos_coerencia_e_chave():
    with pytest.raises(ValidationError, match="mínimo"):
        Params(escada_contratos=2, escada_min=4, escada_max=3)
    with pytest.raises(ValidationError, match="iniciais"):
        Params(escada_contratos=7, escada_min=1, escada_max=5)
    with pytest.raises(ValidationError):
        Params(escada_contratos=2, escada_ganho_acao="dobrar")
    Params(escada_contratos=0, escada_min=4, escada_max=3)                              # desligada não valida os detalhes
    assert Params().chave_motor() == Params(escada_min=2, escada_max=9, escada_perda_acao="somar").chave_motor()    # sem escada, nada disso importa
    assert Params().chave_motor() != Params(escada_contratos=2).chave_motor()
    assert Params(escada_contratos=2).chave_motor() != Params(escada_contratos=2, escada_perda_acao="subtrair").chave_motor()
    assert Params(escada_contratos=2).chave_motor() != Params(escada_contratos=2, escada_max=4).chave_motor()


def test_largura_das_bandas_minimo_precisa_ser_menor_que_o_maximo():
    with pytest.raises(ValidationError, match="mínimo"):
        Params(filtro_bb_ativo=True, filtro_bb_largura_min_pct=1.0, filtro_bb_largura_max_pct=0.8)
    Params(filtro_bb_ativo=True, filtro_bb_largura_min_pct=0.0, filtro_bb_largura_max_pct=0.8)       # 0 = sem mínimo
    Params(filtro_bb_ativo=False, filtro_bb_largura_min_pct=1.0, filtro_bb_largura_max_pct=0.8)      # desligado não valida


def test_chave_do_cache_com_cauda_e_regime():
    base = Params()
    assert base.chave_motor() != Params(parar_dia_perda_x_media=1.0).chave_motor()
    assert base.chave_motor() != Params(tempo_max_min=30).chave_motor()
    # o valor de cada filtro só importa com o filtro ligado
    assert base.chave_motor() != Params(trailing_inicio_r=1.0).chave_motor()
    assert Params(trailing_inicio_r=1.0).chave_motor() != Params(trailing_inicio_r=1.6).chave_motor()
    assert base.chave_motor() == Params(filtro_candle_discrepante_x=3.0).chave_motor()
    assert Params(filtro_candle_discrepante_ativo=True).chave_motor() != Params(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=3.0).chave_motor()
    assert base.chave_motor() != Params(filtro_candle_discrepante_ativo=True).chave_motor()
    assert base.chave_motor() == Params(filtro_gap_max_x_media=2.0, filtro_vol_ontem_max=3.0, filtro_bb_largura_max_pct=3.0,
                                        filtro_inclinacao_barras=9, filtro_inclinacao_max_x_media=2.0).chave_motor()
    assert Params(filtro_gap_ativo=True).chave_motor() != Params(filtro_gap_ativo=True, filtro_gap_max_x_media=1.0).chave_motor()
    assert Params(filtro_vol_ontem_ativo=True).chave_motor() != Params(filtro_vol_ontem_ativo=True, filtro_vol_ontem_max=2.0).chave_motor()
    # as bandas (período e desvio) passam a importar COM o filtro ligado e continuam irrelevantes sem ele
    assert base.chave_motor() == Params(bb_periodo=30, bb_desvio=3.0).chave_motor()
    assert Params(filtro_bb_ativo=True).chave_motor() != Params(filtro_bb_ativo=True, bb_periodo=30).chave_motor()
    assert Params(filtro_bb_ativo=True).chave_motor() != Params(filtro_bb_ativo=True, bb_desvio=3.0).chave_motor()
    # a inclinação depende da MM: o período da MM entra com ela ligada
    assert base.chave_motor() == Params(mm_periodo=50).chave_motor()
    assert Params(filtro_inclinacao_ativo=True).chave_motor() != Params(filtro_inclinacao_ativo=True, mm_periodo=50).chave_motor()
    assert Params(filtro_inclinacao_ativo=True).chave_motor() != Params(filtro_inclinacao_ativo=True, filtro_inclinacao_barras=9).chave_motor()
