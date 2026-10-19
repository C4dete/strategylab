"""Etapa 3 (modo de entrada "próximo candle" e "sair ao tocar a MM") contra o simulador independente.

O simulador (`oraculo_ref_simulador.py`) foi escrito à parte do motor: lê minuto a minuto, calcula a EMA por recursão em
Python puro e resolve a ordem dos eventos dentro do minuto com ramos explícitos de compra e venda. Aqui os dois precisam
gerar os MESMOS trades (lado, minutos, preços, pontos e o motivo da saída), em dados sintéticos (rápido) e no BD real (lento).
Cobre também as reversões (Etapa 5). O oráculo só cobre book "cont" e não tem "parar após N losses": é o recorte que a comparação alcança.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategylab.engine import data
from strategylab.engine.params import Params, hhmm_para_min
from strategylab.engine.runner import rodar_trades
from tests import oraculo_ref_simulador as ref
from tests.conftest import BD_PADRAO, csv_sintetico


def cfg_oraculo(p: Params) -> "ref.Cfg":
    c = ref.Cfg()
    c.rev_max = p.reversoes
    c.rev_s, c.rev_g = p.rev_stop_x_media, p.rev_alvo_x_media
    c.trail = p.trailing_inicio_r
    c.esc = ((p.escada_contratos, p.escada_ganho_acao, p.escada_ganho_qtd, p.escada_perda_acao, p.escada_perda_qtd, p.escada_min, p.escada_max)
             if p.escada_contratos > 0 else None)
    c.filtro3 = "off"
    c.rangemin = 0.0
    assert p.book == "cont" and p.parar_apos_losses == 0, "o oráculo só cobre book cont e sem parar por losses"
    c.Wmm, c.Wop, c.k = p.candles_gatilho, p.candles_media, p.bracket_fracao
    c.stop, c.gain, c.pen_ticks, c.max_cycles = p.stop_x_media, p.alvo_x_media, p.penetracao_ticks, p.operacoes_por_dia
    c.start, c.end = hhmm_para_min(p.janela_inicio), hhmm_para_min(p.janela_fim)
    c.ent_end = hhmm_para_min(p.ultima_entrada) if p.ultima_entrada else c.end
    c.afast = p.filtro_afast_mm_x_media if p.filtro_afast_mm_ativo else 0.0
    c.afast_p = p.mm_periodo
    c.entry_mode = "next_open" if p.modo_entrada == "proximo_candle" else "limit"
    c.mm_exit = p.sair_ao_tocar_mm
    c.rastrear = p.rastrear_mm
    c.stop_day, c.tmax = p.parar_dia_perda_x_media, p.tempo_max_min
    c.gap_max = p.filtro_gap_max_x_media if p.filtro_gap_ativo else None
    c.vol_max = p.filtro_vol_ontem_max if p.filtro_vol_ontem_ativo else None
    c.bb = (p.bb_periodo, p.bb_desvio, p.filtro_bb_largura_min_pct, p.filtro_bb_largura_max_pct) if p.filtro_bb_ativo else None
    c.disc = p.filtro_candle_discrepante_x if p.filtro_candle_discrepante_ativo else 0.0
    c.incl = (p.filtro_inclinacao_max_x_media, p.filtro_inclinacao_barras) if p.filtro_inclinacao_ativo else None
    return c


def comparar(raw: pd.DataFrame, barras: pd.DataFrame, sub: int, p: Params) -> pd.DataFrame:
    """Roda os dois e exige trades idênticos. Devolve os trades do motor (para o chamador conferir que o cenário exercita a regra)."""
    ref_tr = ref.run(raw.assign(vfin=1.0), cfg_oraculo(p))
    novo = rodar_trades(barras, p, sub)
    assert len(ref_tr) == len(novo), f"{p}: {len(ref_tr)} trades no oráculo, {len(novo)} no motor"
    if len(novo):
        minutos = lambda s: pd.to_datetime(s).dt.hour * 60 + pd.to_datetime(s).dt.minute
        assert ref_tr["side"].tolist() == novo["lado"].tolist()
        assert ref_tr["entry_min"].tolist() == minutos(novo["entrada_ts"]).tolist()
        assert ref_tr["exit_min"].tolist() == minutos(novo["saida_ts"]).tolist()
        assert ref_tr["entry_fill"].tolist() == novo["preco_entrada"].tolist()
        assert ref_tr["exit_fill"].tolist() == novo["preco_saida"].tolist()
        assert ref_tr["pts"].tolist() == novo["pts"].tolist()
        assert ref_tr["contracts"].tolist() == novo["contratos"].tolist()
        assert np.allclose(ref_tr["rs"].to_numpy(), novo["rs"].to_numpy(), atol=1e-9)
        esperado = ref_tr["by"].where(~((ref_tr["by"] == "stop") & ref_tr["via_prot"]), "trailing")       # stop no nivel protegido = trailing
        assert esperado.tolist() == novo["saida_por"].tolist()
        assert ref_tr["leg"].tolist() == novo["reversao"].tolist()
    return novo


CENARIOS = {
    "só próximo candle": dict(modo_entrada="proximo_candle"),
    "só sair na MM": dict(sair_ao_tocar_mm=True),
    "os dois": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True),
    "os dois + filtro": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True,
                             filtro_afast_mm_x_media=0.3),
    "sair na MM + filtro, várias operações": dict(sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True,
                                                  filtro_afast_mm_x_media=0.2, operacoes_por_dia=4),
    "próximo candle, penetração 0, várias operações": dict(modo_entrada="proximo_candle", penetracao_ticks=0, operacoes_por_dia=5),
    "próximo candle, penetração 3": dict(modo_entrada="proximo_candle", penetracao_ticks=3, operacoes_por_dia=2),
    "MM curta e stop curto": dict(sair_ao_tocar_mm=True, mm_periodo=5, stop_x_media=0.5, alvo_x_media=1.5, operacoes_por_dia=3),
    "MM longa e alvo longo": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, mm_periodo=40, alvo_x_media=6.0,
                                  stop_x_media=2.0, operacoes_por_dia=2),
    "zona de 1 candle": dict(candles_gatilho=1, candles_media=2, operacoes_por_dia=3),
    "zona de 1 candle, penetração 0, bracket largo": dict(candles_gatilho=1, bracket_fracao=0.3, penetracao_ticks=0, operacoes_por_dia=4),
    "zona de 1 candle + próximo candle + sair na MM + rastrear + reversões": dict(candles_gatilho=1, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                                                  rastrear_mm=True, reversoes=2, operacoes_por_dia=3),
    "trailing 0,8": dict(trailing_inicio_r=0.8, operacoes_por_dia=3),
    "trailing 0,5 + reversões (stop/alvo próprios)": dict(trailing_inicio_r=0.5, reversoes=3, rev_stop_x_media=0.7, rev_alvo_x_media=2.0,
                                                           stop_x_media=1.2, alvo_x_media=3.0, operacoes_por_dia=2),
    "trailing 0,6 + próximo candle + sair na MM + rastrear + reversões": dict(trailing_inicio_r=0.6, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                                            rastrear_mm=True, reversoes=2, operacoes_por_dia=3),
    "trailing 0,7 + candle discrepante + filtro": dict(trailing_inicio_r=0.7, filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.4,
                                                       filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.1, operacoes_por_dia=3),
    "escada de contratos (ganho +1, perda −1)": dict(escada_contratos=2, escada_ganho_acao="somar", escada_ganho_qtd=1, escada_perda_acao="subtrair",
                                                      escada_perda_qtd=1, escada_min=1, escada_max=4, operacoes_por_dia=4),
    "escada + reversões (perda +2, ganho −1) + trailing": dict(escada_contratos=3, escada_ganho_acao="subtrair", escada_ganho_qtd=1, escada_perda_acao="somar",
                                                              escada_perda_qtd=2, escada_min=1, escada_max=6, reversoes=3, trailing_inicio_r=0.8,
                                                              operacoes_por_dia=3),
    "só rastrear MM": dict(rastrear_mm=True),
    "rastrear MM + próximo candle + sair na MM": dict(rastrear_mm=True, modo_entrada="proximo_candle", sair_ao_tocar_mm=True,
                                                      operacoes_por_dia=3),
    "rastrear MM + filtro, várias operações": dict(rastrear_mm=True, filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.2,
                                                   operacoes_por_dia=4, mm_periodo=9),
    "1 reversão (herda stop/alvo)": dict(reversoes=1),
    "3 reversões com stop/alvo próprios, várias operações": dict(reversoes=3, rev_stop_x_media=0.6, rev_alvo_x_media=2.5, operacoes_por_dia=3),
    "reversões + próximo candle + sair na MM + rastrear": dict(reversoes=2, rev_stop_x_media=0.8, modo_entrada="proximo_candle",
                                                               sair_ao_tocar_mm=True, rastrear_mm=True, operacoes_por_dia=2),
    "5 reversões + filtro + penetração 0": dict(reversoes=5, rev_alvo_x_media=1.0, filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.2,
                                                penetracao_ticks=0, operacoes_por_dia=4),
    "janela customizada": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, rastrear_mm=True, reversoes=2, janela_inicio="09:30", janela_fim="16:30",
                               ultima_entrada="15:00", candles_gatilho=8, candles_media=3, bracket_fracao=0.3, operacoes_por_dia=2),
    "sem última entrada": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, ultima_entrada=None, operacoes_por_dia=3),
    "última entrada colada na barra": dict(modo_entrada="proximo_candle", ultima_entrada="10:30", operacoes_por_dia=3),
}


@pytest.mark.parametrize("semente, dias", [
    (21, 30),
    pytest.param(5, 60, marks=pytest.mark.lento),         # outra série, mais longa
])
@pytest.mark.parametrize("nome", list(CENARIOS))
def test_motor_confere_com_o_simulador_independente_nos_dados_sinteticos(nome, semente, dias):
    raw, _ = data.carregar_csv(csv_sintetico(dias=dias, semente=semente).encode())
    barras, sub = data.preparar_barras(raw, 10)
    novo = comparar(raw, barras, sub, Params(**CENARIOS[nome]))
    assert len(novo) > 10, "o cenário precisa operar para a comparação significar algo"


def test_os_cenarios_exercitam_as_saidas_pela_mm_e_as_entradas_na_abertura():
    """Garante que a comparação acima não é vazia: há saídas por MM, em ganho e em perda, e entradas na abertura da barra."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=45, semente=21).encode())
    barras, sub = data.preparar_barras(raw, 10)
    tr = rodar_trades(barras, Params(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, operacoes_por_dia=3), sub)
    mm = tr[tr["saida_por"] == "mm"]
    assert len(mm) > 15 and (mm["pts"] > 0).any() and (mm["pts"] <= 0).any()
    assert (pd.to_datetime(tr["entrada_ts"]).dt.minute % 10 == 0).all()                 # sempre na abertura de uma barra de 10 min
    assert set(tr["saida_por"]) >= {"mm", "stop", "alvo"}


@pytest.mark.lento
@pytest.mark.parametrize("nome", ["só próximo candle", "só sair na MM", "os dois + filtro", "sair na MM + filtro, várias operações", "só rastrear MM",
                                  "3 reversões com stop/alvo próprios, várias operações",
                                  "reversões + próximo candle + sair na MM + rastrear",
                                  "filtro candle discrepante + reversões + próximo candle",
                                  "trailing 0,5 + reversões (stop/alvo próprios)",
                                  "escada + reversões (perda +2, ganho −1) + trailing"])
def test_motor_confere_com_o_simulador_independente_no_bd_real(barras_reais, nome):
    df, barras, sub = barras_reais
    novo = comparar(df, barras, sub, Params(**{**CENARIOS, **REGIME}[nome]))
    assert len(novo) > 300
    print(f"\n{nome}: {len(novo)} trades, R$ {novo['rs'].sum():.2f}")


def test_os_cenarios_exercitam_o_trailing():
    """Garante que as comparações com trailing não são vazias: há saídas no nível protegido, em ganho e em perda, nos dois modos de entrada."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=45, semente=21).encode())
    barras, sub = data.preparar_barras(raw, 10)
    for nome in ("trailing 0,8", "trailing 0,5 + reversões (stop/alvo próprios)", "trailing 0,6 + próximo candle + sair na MM + rastrear + reversões"):
        tr = rodar_trades(barras, Params(**CENARIOS[nome]), sub)
        t = tr[tr["saida_por"] == "trailing"]
        assert len(t) > 8 and (t["pts"] > 0).any(), nome
    assert (t["pts"] <= 0).any()                                                      # o último cenário tem trailing com perda (e então reverte)


def test_os_cenarios_exercitam_as_reversoes():
    """Garante que as comparações com reversão não são vazias: há pernas revertidas, em ganho e em perda, até a 3ª."""
    raw, _ = data.carregar_csv(csv_sintetico(dias=45, semente=21).encode())
    barras, sub = data.preparar_barras(raw, 10)
    tr = rodar_trades(barras, Params(reversoes=3, rev_stop_x_media=0.6, rev_alvo_x_media=2.5, operacoes_por_dia=3), sub)
    rev = tr[tr["reversao"] > 0]
    assert len(rev) > 15 and (rev["pts"] > 0).any() and (rev["pts"] <= 0).any() and rev["reversao"].max() >= 2
    assert tr["ciclo"].nunique() < len(tr) and (tr.groupby(["data", "ciclo"]).size() > 1).any()


# ------------------------------------------------------------------ Etapa 6: controle de cauda e filtros de regime
def com_saltos(raw: pd.DataFrame, semente: int = 4, amplitude: float = 200.0) -> pd.DataFrame:
    """O BD sintético é contínuo (sem gaps). Soma um salto aleatório acumulado por pregão: cria gaps de abertura e dias de amplitude variada."""
    import numpy as np

    rng = np.random.RandomState(semente)
    dias = sorted(raw["date"].unique())
    desloc = dict(zip(dias, np.cumsum(rng.normal(0, amplitude, len(dias)))))
    out = raw.copy()
    off = out["date"].map(desloc).astype(float)
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].astype(float) + off
    return out


REGIME = {
    "só cauda: parar o dia por perda": dict(parar_dia_perda_x_media=1.0, operacoes_por_dia=5),
    "só cauda: tempo máximo": dict(tempo_max_min=30, operacoes_por_dia=3),
    "cauda + reversões": dict(parar_dia_perda_x_media=0.8, tempo_max_min=60, reversoes=3, operacoes_por_dia=4),
    "só gap do dia": dict(filtro_gap_ativo=True, filtro_gap_max_x_media=0.3, operacoes_por_dia=2),
    "só amplitude de ontem": dict(filtro_vol_ontem_ativo=True, filtro_vol_ontem_max=1.1, operacoes_por_dia=2),
    "só largura das bandas": dict(filtro_bb_ativo=True, filtro_bb_largura_min_pct=0.15, filtro_bb_largura_max_pct=0.3, operacoes_por_dia=3),
    "filtro candle discrepante": dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.4, operacoes_por_dia=3),
    "filtro candle discrepante + reversões + próximo candle": dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.3,
                                                                  reversoes=2, modo_entrada="proximo_candle", operacoes_por_dia=3),
    "só inclinação da MM": dict(filtro_inclinacao_ativo=True, filtro_inclinacao_barras=5, filtro_inclinacao_max_x_media=0.3, operacoes_por_dia=3),
    "inclinação com MM e barras próprias": dict(filtro_inclinacao_ativo=True, filtro_inclinacao_barras=8, filtro_inclinacao_max_x_media=0.2,
                                                mm_periodo=9, operacoes_por_dia=3),
    "tudo junto": dict(parar_dia_perda_x_media=1.0, tempo_max_min=90, filtro_gap_ativo=True, filtro_gap_max_x_media=0.5,
                       filtro_vol_ontem_ativo=True, filtro_vol_ontem_max=1.5, filtro_bb_ativo=True, filtro_bb_largura_min_pct=0.1,
                       filtro_bb_largura_max_pct=0.4, filtro_inclinacao_ativo=True, filtro_inclinacao_max_x_media=0.5,
                       reversoes=2, modo_entrada="proximo_candle", sair_ao_tocar_mm=True, rastrear_mm=True,
                       filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.1, filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.4,
                       operacoes_por_dia=4),
}


@pytest.mark.parametrize("nome", list(REGIME))
def test_regime_e_cauda_conferem_com_o_simulador_independente(nome):
    raw, _ = data.carregar_csv(csv_sintetico(dias=70, semente=21).encode())
    raw = com_saltos(raw)
    barras, sub = data.preparar_barras(raw, 10)
    p = Params(**REGIME[nome])
    novo = comparar(raw, barras, sub, p)
    assert len(novo) > 8, "o cenário precisa operar"
    sem = rodar_trades(barras, Params(**{k: v for k, v in REGIME[nome].items() if k in ("operacoes_por_dia", "reversoes", "modo_entrada",
                                                                                          "sair_ao_tocar_mm", "rastrear_mm", "filtro_afast_mm_ativo",
                                                                                          "filtro_afast_mm_x_media")}), sub)
    assert len(novo) != len(sem) or novo["rs"].sum() != sem["rs"].sum(), "o controle não mudou nada: o teste não exercita a regra"


def test_medidas_de_regime_do_motor_iguais_as_do_simulador_independente():
    """Compara as MEDIDAS (não só os trades): gap e amplitude de ontem de cada dia, largura das bandas e inclinação da MM de cada barra."""
    import numpy as np

    from strategylab.engine.runner import preparar_mercado

    raw, _ = data.carregar_csv(csv_sintetico(dias=60, semente=9).encode())
    raw = com_saltos(raw, semente=2)
    barras, sub = data.preparar_barras(raw, 10)
    mercado = preparar_mercado(barras, sub)
    c = ref.Cfg()
    c.afast_p = 15
    c.bb = (15, 2.0, 0.0, 1.0)
    c.incl = (0.5, 5)
    c.emad = ref.montar_ema(raw.assign(vfin=1.0), c)
    ref.montar_regime(raw.assign(vfin=1.0), c)
    # medidas do dia
    assert set(mercado.feat) == set(c.diaf)
    for dia, (g, v) in mercado.feat.items():
        og, ov = c.diaf[dia]
        for a, b in ((g, og), (v, ov)):
            assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-12), (dia, a, b)
    assert sum(1 for g, v in mercado.feat.values() if g == g) > 30 and sum(1 for g, v in mercado.feat.values() if v == v) > 30
    # medidas da barra
    bbw, slope = mercado.bbw(15, 2.0), mercado.slope(15, 5)
    tempos = list(barras["datetime"])
    for k, t in enumerate(tempos):
        ob, os_ = c.bbd.get(t, float("nan")), c.incld.get(t, float("nan"))
        assert (np.isnan(bbw[k]) and np.isnan(ob)) or bbw[k] == pytest.approx(ob, rel=1e-9), (t, bbw[k], ob)
        assert (np.isnan(slope[k]) and np.isnan(os_)) or slope[k] == pytest.approx(os_, rel=1e-9, abs=1e-9), (t, slope[k], os_)
    assert np.isfinite(bbw).sum() > 1000 and np.isfinite(slope).sum() > 1000
