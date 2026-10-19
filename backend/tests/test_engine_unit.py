"""Regras do motor, em cenários montados à mão.

Barras de 15 min com 3 sub-candles de 5 min embutidos (so0/sh0/sl0/sc0 ...). Isso isola a decisão de
entrada da reamostragem. O motor é sempre FADE: a ponta de cima VENDE, a de baixo COMPRA.
"""

from __future__ import annotations

import pandas as pd
import pytest

from strategylab.engine.fills import close_action, fill, gap_level
from strategylab.engine.ghost import Cfg, run_day


def cfg(**over) -> Cfg:
    base = dict(inicio_min=0, fim_min=23 * 60 + 59, ult_entrada_min=23 * 60 + 59, n_zona=3, n_media=3,
                k=0.5, book="ambas", penetracao=0.0, parar_n=0, parar_modo="dia", max_ops=1,
                stop_mult=1.0, gain_mult=1.0, sub_min=5, slippage=0.0, spread=0.0, tick=0.0,
                valor_ponto=0.20, contratos=1)
    base.update(over)
    return Cfg(**base)


def make_day(bars, subs, day="2023-01-02", first="09:00"):
    """bars = [(o,h,l,c)] de 15 min; subs = [[(o,h,l,c) x3]] alinhado com bars."""
    n = len(bars)
    times = pd.date_range(f"{day} {first}", periods=n, freq="15min")
    d = {"datetime": times, "date": times.date}
    for j, nome in enumerate(("open", "high", "low", "close")):
        d[nome] = [b[j] for b in bars]
    for s in range(3):
        for j, pre in enumerate(("so", "sh", "sl", "sc")):
            d[f"{pre}{s}"] = [subs[i][s][j] if subs[i][s] else float("nan") for i in range(n)]
    return pd.DataFrame(d)


def plano(o, h, l, c):
    """3 sub-candles iguais que somam ao candle de 15 min."""
    return [(o, h, l, c), (o, h, l, c), (o, h, l, c)]


AQUECE = [(95, 100, 90, 96)] * 3                    # zona 90-100, media_op = 10
SUB_AQUECE = [plano(95, 100, 90, 96)] * 3

# Barra 3 cruza 100 e alcança 106: a ponta de cima (100 + 0,5 x 10 = 105) executa -> VENDE a 105.
B_CIMA = AQUECE + [(99, 106, 98, 105), (105, 120, 104, 119)]
S_CIMA = SUB_AQUECE + [
    [(99, 101, 98, 100), (100, 106, 99, 105), (105, 106, 104, 105)],
    plano(105, 120, 104, 119)]

# Barra 3 cruza 100 mas só recua até 94: a ponta de baixo (100 - 5 = 95) executa -> COMPRA a 95.
B_BAIXO = AQUECE + [(99, 102, 94, 95), (95, 96, 80, 81)]
S_BAIXO = SUB_AQUECE + [
    [(99, 102, 99, 101), (101, 101, 97, 98), (98, 98, 94, 95)],
    plano(95, 96, 80, 81)]


def rodar(bars, subs, **over):
    return run_day(make_day(bars, subs), cfg(**over))


# ------------------------------------------------------------------ pontas e fade
def test_ponta_de_cima_vende_no_gatilho_mais_meia_media():
    tr = rodar(B_CIMA, S_CIMA)
    assert len(tr) == 1
    assert tr[0].lado == "sell"
    assert tr[0].preco_entrada == pytest.approx(105.0)


def test_ponta_de_baixo_compra_ao_recuar_meia_media():
    tr = rodar(B_BAIXO, S_BAIXO)
    assert len(tr) == 1
    assert tr[0].lado == "buy"
    assert tr[0].preco_entrada == pytest.approx(95.0)


def test_entrada_e_carimbada_no_sub_candle_que_encheu():
    tr = rodar(B_CIMA, S_CIMA)
    # barra 3 = 09:45; a ordem encheu no 2º sub-candle (slot 1) = 09:50
    assert tr[0].entrada_ts == pd.Timestamp("2023-01-02 09:50")


def test_sem_subcandles_o_motor_nao_opera():
    df = make_day(B_CIMA, S_CIMA)
    df = df.drop(columns=[c for c in df.columns if c[:2] in ("so", "sh", "sl", "sc")])
    assert run_day(df, cfg()) == []


# ------------------------------------------------------------------ zona de 1 candle
def test_zona_de_um_candle_usa_so_a_maxima_e_a_minima_da_barra_anterior():
    # duas barras largas (80-120) e uma estreita (90-100) logo antes da barra do gatilho; media_op = (40+40+10)/3 = 30
    bars = [(95, 120, 80, 96), (95, 120, 80, 96), (95, 100, 90, 96), (99, 120, 98, 118), (105, 110, 100, 105)]
    subs = [plano(*b) for b in bars]
    tr = rodar(bars, subs, n_zona=1, book="cont")
    assert len(tr) == 1 and tr[0].lado == "sell"
    assert tr[0].preco_entrada == pytest.approx(100 + 0.5 * 30)      # gatilho 100 (máxima SÓ da barra anterior) + meia media_op
    # com 3 barras a zona seria 80-120: o gatilho vai a 120 e a ponta (135) nunca é alcançada
    assert rodar(bars, subs, n_zona=3, book="cont") == []


def test_zona_de_um_candle_mantem_a_espera_pela_media():
    # n_zona=1 não antecipa a 1ª entrada: ela só começa depois de max(n_zona, n_media) barras
    bars = [(95, 120, 80, 96), (95, 100, 90, 96), (99, 120, 98, 118), (105, 110, 100, 105)]
    subs = [plano(*b) for b in bars]
    tr = rodar(bars, subs, n_zona=1, n_media=3, book="cont")
    assert all(t.entrada_ts >= pd.Timestamp("2023-01-02 09:45") for t in tr)


# ------------------------------------------------------------------ book
def test_book_cont_so_arma_a_ponta_alem_do_gatilho():
    assert rodar(B_BAIXO, S_BAIXO, book="cont") == []      # o preço só recuou: nada a executar
    tr = rodar(B_CIMA, S_CIMA, book="cont")
    assert len(tr) == 1 and tr[0].lado == "sell"


def test_book_recuo_so_arma_a_ponta_dentro_da_zona():
    assert rodar(B_CIMA, S_CIMA, book="recuo") == []        # só continuou: a de recuo nunca encheu
    tr = rodar(B_BAIXO, S_BAIXO, book="recuo")
    assert len(tr) == 1 and tr[0].lado == "buy"


def test_book_acima_e_abaixo_fixam_a_ponta():
    assert rodar(B_BAIXO, S_BAIXO, book="acima") == []
    assert rodar(B_CIMA, S_CIMA, book="abaixo") == []
    assert rodar(B_CIMA, S_CIMA, book="acima")[0].preco_entrada == pytest.approx(105.0)
    assert rodar(B_BAIXO, S_BAIXO, book="abaixo")[0].preco_entrada == pytest.approx(95.0)


def test_continuacao_enche_no_proprio_sub_candle_do_cruzamento():
    bars = AQUECE + [(99, 106, 98, 105), (105, 120, 104, 119)]
    subs = SUB_AQUECE + [[(99, 106, 98, 105), (105, 105, 104, 105), (105, 105, 104, 105)],
                         plano(105, 120, 104, 119)]
    tr = rodar(bars, subs, book="cont")
    assert len(tr) == 1
    assert tr[0].entrada_ts == pd.Timestamp("2023-01-02 09:45")


def test_recuo_nao_enche_se_o_sub_candle_ja_abriu_alem_dele():
    # O sub-candle que cruza o topo ABRE em 94 (<= 95): o nível de recuo foi tocado antes de a ordem
    # existir. A ponta segue armada e só executa no sub-candle seguinte (09:50).
    bars = AQUECE + [(94, 101, 93, 100), (100, 101, 90, 91)]
    subs = SUB_AQUECE + [[(94, 101, 93, 100), (100, 101, 94, 95), (95, 96, 94, 95)],
                         plano(100, 101, 90, 91)]
    tr = rodar(bars, subs, book="recuo")
    assert len(tr) == 1
    assert tr[0].lado == "buy"
    assert tr[0].entrada_ts == pd.Timestamp("2023-01-02 09:50")


# ------------------------------------------------------------------ penetração (fila no book)
def test_penetracao_exige_atravessar_o_nivel():
    # nível 105; a barra 3 (09:45) chega a 106 e a barra 4 (10:00) a 120. A ordem não expira.
    assert rodar(B_CIMA, S_CIMA, penetracao=0.0)[0].entrada_ts == pd.Timestamp("2023-01-02 09:50")
    assert rodar(B_CIMA, S_CIMA, penetracao=1.0)[0].entrada_ts == pd.Timestamp("2023-01-02 09:50")   # 106 >= 106
    assert rodar(B_CIMA, S_CIMA, penetracao=2.0)[0].entrada_ts == pd.Timestamp("2023-01-02 10:00")   # 106 < 107: espera
    assert rodar(B_CIMA[:4], S_CIMA[:4], penetracao=2.0) == []                                       # sem mais barras


def test_penetracao_nao_muda_o_preco_do_fill():
    bars = AQUECE + [(99, 111, 98, 105), (105, 120, 104, 119)]
    subs = SUB_AQUECE + [[(99, 101, 98, 100), (100, 111, 99, 105), (105, 106, 104, 105)],
                         plano(105, 120, 104, 119)]
    tr = rodar(bars, subs, penetracao=5.0)
    assert tr[0].preco_entrada == pytest.approx(105.0)


# ------------------------------------------------------------------ janela, última entrada, zeragem
def test_ultima_entrada_bloqueia_novas_ordens():
    # a barra do sinal começa 09:45; com última entrada 09:45 o motor não procura mais gatilho
    assert rodar(B_CIMA, S_CIMA, ult_entrada_min=9 * 60 + 45) == []
    assert rodar(B_CIMA, S_CIMA, ult_entrada_min=10 * 60)


def test_ordem_armada_nao_enche_depois_da_ultima_entrada():
    # gatilho cruzado às 09:45; a ponta de cima só alcança 105 no sub-candle de 09:50, mas a última entrada é 09:48
    assert rodar(B_CIMA, S_CIMA, ult_entrada_min=9 * 60 + 48) == []


def test_posicao_aberta_depois_da_ultima_entrada_segue_ate_a_zeragem():
    # entra vendido a 105 e o preço fica de lado até a zeragem às 10:30: sai a mercado ("time_close")
    lado = [plano(105, 107, 103, 105)] * 6
    bars = AQUECE + [(99, 106, 98, 105)] + [(105, 107, 103, 105)] * 6
    subs = SUB_AQUECE + [[(99, 101, 98, 100), (100, 106, 99, 105), (105, 106, 104, 105)]] + lado
    tr = rodar(bars, subs, stop_mult=5.0, gain_mult=5.0, ult_entrada_min=9 * 60 + 55,
               fim_min=10 * 60 + 30)
    assert len(tr) == 1
    assert tr[0].desfecho == "time_close"
    assert tr[0].saida_ts == pd.Timestamp("2023-01-02 10:30")


def test_nao_entra_antes_do_inicio_da_janela():
    assert rodar(B_CIMA, S_CIMA)[0].entrada_ts == pd.Timestamp("2023-01-02 09:50")
    # com início às 10:00 a barra das 09:45 é ignorada; o próximo sinal só nasce na barra das 10:00
    assert rodar(B_CIMA, S_CIMA, inicio_min=10 * 60)[0].entrada_ts >= pd.Timestamp("2023-01-02 10:00")
    assert rodar(B_CIMA, S_CIMA, inicio_min=10 * 60 + 30) == []


# ------------------------------------------------------------------ stop, alvo, custos
def test_stop_a_mercado_paga_slippage_e_alvo_limite_nao():
    # vende a 105; barra 4 sobe até 120: stop = 105 + media_op(9,33) = 114,33 -> mercado, arredonda contra (compra p/ cima)
    tr = rodar(B_CIMA, S_CIMA, slippage=5.0, spread=5.0, tick=5.0)
    assert tr[0].desfecho == "loss"
    # 114,33 + 5 + 2,5 = 121,83 -> teto na grade de 5 = 125 ; entrada limite 105 arredondada ao tick = 105
    assert tr[0].preco_saida == pytest.approx(125.0)
    assert tr[0].pts == pytest.approx(-20.0)


def test_alvo_enche_no_nivel_sem_custo():
    bars = AQUECE + [(99, 106, 98, 105), (105, 106, 90, 91)]
    subs = SUB_AQUECE + [[(99, 101, 98, 100), (100, 106, 99, 105), (105, 106, 104, 105)],
                         plano(105, 106, 90, 91)]
    tr = rodar(bars, subs, slippage=5.0, spread=5.0, tick=5.0)
    # alvo = 105 - 1,0 x 9,33 = 95,67 -> limite, só arredonda ao tick mais próximo = 95
    assert tr[0].desfecho == "gain"
    assert tr[0].preco_saida == pytest.approx(95.0)


def test_resultado_em_reais_usa_valor_do_ponto_e_contratos():
    tr = rodar(B_CIMA, S_CIMA, valor_ponto=0.20, contratos=3)
    assert tr[0].rs == pytest.approx(tr[0].pts * 3 * 0.20)


def test_fill_e_gap_level():
    c = cfg(slippage=5.0, spread=5.0, tick=5.0)
    assert fill(100, "buy", True, c) == 110.0              # 107,5 -> teto da grade
    assert fill(100, "sell", True, c) == 90.0              # 92,5 -> piso da grade
    assert fill(102, "buy", False, c) == 100.0             # limite: só arredonda ao tick mais próximo
    assert gap_level(100, 108, "buy") == 108               # stop de compra, sub-candle abriu acima: abertura
    assert gap_level(100, 98, "buy") == 100
    assert gap_level(100, 92, "sell") == 92
    assert close_action("buy") == "sell" and close_action("sell") == "buy"


# ------------------------------------------------------------------ operações por dia e parada por losses
# Dia com dois sinais seguidos, os dois terminando em stop (loss).
B_DOIS = AQUECE + [
    (99, 106, 98, 105),                    # 3: vende 105
    (105, 125, 104, 124),                  # 4: stop (loss 1)
    (124, 135, 120, 128),                  # 5: cruza 125 e vende 131,5
    (134, 150, 133, 149)]                  # 6: stop (loss 2)
S_DOIS = SUB_AQUECE + [
    [(99, 101, 98, 100), (100, 106, 99, 105), (105, 106, 104, 105)],
    plano(105, 125, 104, 124),
    [(124, 126, 120, 125), (125, 135, 124, 134), (134, 135, 133, 134)],
    plano(134, 150, 133, 149)]


def test_uma_operacao_por_dia_por_padrao():
    assert len(rodar(B_DOIS, S_DOIS, max_ops=1)) == 1


def test_varias_operacoes_por_dia():
    tr = rodar(B_DOIS, S_DOIS, max_ops=5)
    assert len(tr) == 2
    assert [t.desfecho for t in tr] == ["loss", "loss"]
    assert [t.ciclo for t in tr] == [1, 2]


def test_parar_apos_losses_interrompe_o_dia():
    assert len(rodar(B_DOIS, S_DOIS, max_ops=5, parar_n=1)) == 1
    assert len(rodar(B_DOIS, S_DOIS, max_ops=5, parar_n=2)) == 2


def test_parar_apos_losses_zero_esta_desligado():
    assert len(rodar(B_DOIS, S_DOIS, max_ops=5, parar_n=0)) == 2


# ------------------------------------------------------------------ filtro "Afastamento da MM"
# No cenário B_CIMA a barra do gatilho é a 3 (09:45); a barra de referência é a 2 (09:30) = (95, 100, 90, 96):
# topo 100, fundo 90. media_operacao = 10. `mm[t]` = EMA NO FECHAMENTO da barra t (o motor lê mm[i-1] = mm[2]).
# Se o filtro reprova a barra 3, a busca segue e a barra 4 pode gerar OUTRA entrada (com outra referência): por isso
# os testes olham de qual candle de referência a entrada saiu, e não só se houve trade.
REF_BARRA_3 = pd.Timestamp("2023-01-02 09:30")


def com_mm(bars, subs, mm):
    df = make_day(bars, subs)
    df["mm"] = mm
    return df


def filtro(mm, mult=1.0, bars=B_CIMA, subs=S_CIMA, **over):
    return run_day(com_mm(bars, subs, mm), cfg(afast_ativo=True, afast_mult=mult, **over))


def passou_na_barra_3(trades) -> bool:
    return any(t.ref_barra == REF_BARRA_3 for t in trades)


def test_candle_acima_da_mm_mede_do_fundo_ate_a_mm():
    # fundo 90, MM 80 -> afastamento 10 = 1,0 x media_operacao
    assert passou_na_barra_3(filtro([80] * 5, mult=1.0))                 # 10 >= 10 (limite inclusivo)
    assert passou_na_barra_3(filtro([80] * 5, mult=0.5))
    assert not passou_na_barra_3(filtro([80] * 5, mult=1.1))             # 10 < 11


def test_candle_abaixo_da_mm_mede_do_topo_ate_a_mm():
    # topo 100, MM 110 -> afastamento 10
    assert passou_na_barra_3(filtro([110] * 5, mult=1.0))
    assert not passou_na_barra_3(filtro([110] * 5, mult=1.1))
    # e NÃO é medido pelo fundo (seriam 20): com mult 1,5 reprova
    assert not passou_na_barra_3(filtro([110] * 5, mult=1.5))


def test_candle_que_toca_ou_cruza_a_mm_e_reprovado():
    assert not passou_na_barra_3(filtro([95] * 5, mult=0.05))            # cruza (90 < 95 < 100)
    assert not passou_na_barra_3(filtro([100] * 5, mult=0.05))           # o topo encosta na MM
    assert not passou_na_barra_3(filtro([90] * 5, mult=0.05))            # o fundo encosta na MM


def test_filtro_nao_usa_o_candle_do_proprio_gatilho_nem_o_anterior_ao_de_referencia():
    # A EMA da barra do gatilho (mm[3], já com o close dele) e a da barra 1 NÃO podem valer:
    # só mm[2] decide. Aqui mm[2] = 95 (cruza) e as vizinhas estão "perfeitas".
    assert not passou_na_barra_3(filtro([50, 50, 95, 50, 50], mult=0.5))
    # e o inverso: mm[2] perfeita, vizinhas ruins (cruzando o candle) -> passa, com a MM certa registrada
    tr = filtro([95, 95, 80, 95, 95], mult=0.5)
    ref = [t for t in tr if t.ref_barra == REF_BARRA_3]
    assert len(ref) == 1 and ref[0].ref_mm == 80


def test_filtro_usa_a_maxima_e_a_minima_da_barra_de_referencia_e_nao_as_da_barra_do_gatilho():
    # A barra do gatilho (3) vai de 98 a 106; a de referência (2), de 90 a 100.
    assert passou_na_barra_3(filtro([108] * 5, mult=0.8))                # 108 - 100 = 8 >= 8 (referência), não 108 - 106 = 2
    assert not passou_na_barra_3(filtro([108] * 5, mult=0.9))            # 8 < 9
    assert passou_na_barra_3(filtro([80] * 5, mult=1.0))                 # 90 - 80 = 10 (referência), não 98 - 80 = 18
    assert not passou_na_barra_3(filtro([80] * 5, mult=1.1))


def test_filtro_exige_ema_formada():
    assert filtro([float("nan")] * 5, mult=0.1) == []                    # sem EMA em nenhuma barra: nunca opera
    assert passou_na_barra_3(filtro([float("nan"), float("nan"), 80, 80, 80], mult=0.1))


def test_registra_o_que_o_filtro_viu():
    t = [t for t in filtro([80] * 5, mult=0.5) if t.ref_barra == REF_BARRA_3][0]
    assert (t.ref_mm, t.ref_afast, t.media_op) == (80.0, 10.0, 10.0)


def test_filtro_desligado_ignora_a_mm_e_nao_registra_referencia():
    df = com_mm(B_CIMA, S_CIMA, [95] * 5)                                # MM cruzando o candle: reprovaria se estivesse ligado
    tr = run_day(df, cfg())
    assert len(tr) == 1 and tr[0].ref_barra is None and tr[0].entrada_ts == pd.Timestamp("2023-01-02 09:50")


def test_filtro_ligado_sem_a_coluna_mm_falha_alto():
    with pytest.raises(ValueError, match="mm"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(afast_ativo=True, afast_mult=1.0))


def test_reprovado_no_gatilho_a_busca_segue_na_barra_seguinte():
    # barra 3: gatilho cruzado, mas mm[2] cruza o candle de referência -> não arma.
    # barra 4 (10:00): referência = barra 3 (99, 106, 98, 105) com MM 70 -> afastamento 28; a entrada nasce na barra 4.
    tr = filtro([95, 95, 95, 70, 70], mult=1.0)
    assert len(tr) == 1
    assert tr[0].ref_barra == pd.Timestamp("2023-01-02 09:45") and tr[0].entrada_ts >= pd.Timestamp("2023-01-02 10:00")


# ------------------------------------------------------------------ Etapa 3: modo de entrada "próximo candle"
# No cenário B_CIMA o sinal (ordem executada) nasce na barra 3 (09:45), sub-candle de 09:50. No modo padrão a entrada é aí.
# No modo "próximo candle" ela só acontece na ABERTURA da barra 4 (10:00): a mercado, com custo cheio.
PROX = dict(modo_entrada="proximo_candle")
B3 = (99, 106, 98, 105)
S3 = S_CIMA[3]                                      # sub-candles da barra 3: o sinal sai no de 09:50


def barra_de(subs):
    """Candle da barra a partir dos sub-candles (o motor lê os sub-candles; a barra só alimenta zona e media_op)."""
    return (subs[0][0], max(s[1] for s in subs), min(s[2] for s in subs), subs[-1][3])


def depois_do_sinal(sub4, **over):
    """B_CIMA com a barra 4 trocada por `sub4` (3 sub-candles)."""
    return rodar(AQUECE + [B3, barra_de(sub4)], SUB_AQUECE + [S3, sub4], **over)


def ts(hhmm):
    return pd.Timestamp(f"2023-01-02 {hhmm}")


def test_proximo_candle_entra_na_abertura_da_barra_seguinte_a_mercado_com_custo():
    sub4 = plano(108, 112, 107, 110)
    sub5 = plano(110, 111, 100, 101)
    bars = AQUECE + [B3, barra_de(sub4), barra_de(sub5)]
    subs = SUB_AQUECE + [S3, sub4, sub5]
    custo = dict(slippage=5.0, spread=5.0, tick=5.0, stop_mult=5.0, gain_mult=5.0)
    pad = rodar(bars, subs, **custo)[0]
    assert (pad.entrada_ts, pad.preco_entrada) == (ts("09:50"), 105.0)             # limite no nível, sem custo
    pro = rodar(bars, subs, **PROX, **custo)[0]
    assert pro.lado == "sell" and pro.entrada_ts == ts("10:00")                      # abertura da barra 4
    assert pro.preco_entrada == pytest.approx(100.0)                                 # 108 - (5 + 2,5) = 100,5 -> piso da grade de 5


def test_proximo_candle_sem_custo_entra_exatamente_na_abertura():
    tr = depois_do_sinal(plano(108, 112, 107, 110), **PROX, stop_mult=5.0, gain_mult=5.0)
    assert tr[0].preco_entrada == pytest.approx(108.0)


def test_proximo_candle_stop_e_alvo_contam_a_partir_da_abertura():
    # media_op da barra 4 = (10 + 10 + 8) / 3 = 9,333. Abre em 108: stop = 117,33 (e não 105 + 9,33 = 114,33 do modo padrão).
    sub4 = plano(108, 118, 107, 117)
    pad = depois_do_sinal(sub4)[0]
    assert pad.entrada_ts == ts("09:50") and pad.preco_saida == pytest.approx(105 + 28 / 3)
    pro = depois_do_sinal(sub4, **PROX)[0]
    assert pro.preco_entrada == pytest.approx(108.0)
    assert pro.desfecho == "loss" and pro.saida_por == "stop"
    assert pro.preco_saida == pytest.approx(108 + 28 / 3)
    assert pro.pts == pytest.approx(-28 / 3)


def test_proximo_candle_o_minuto_da_abertura_nao_e_imune():
    # a entrada acontece no INÍCIO do sub-candle das 10:00: stop (e alvo) valem nele mesmo
    tr = depois_do_sinal(plano(108, 118, 107, 117), **PROX)[0]
    assert tr.entrada_ts == tr.saida_ts == ts("10:00")


def test_modo_padrao_continua_com_o_minuto_da_entrada_imune():
    # entra às 09:50 e a gestão só começa no minuto seguinte
    tr = rodar(B_CIMA, S_CIMA)[0]
    assert tr.entrada_ts == ts("09:50") and tr.saida_ts > tr.entrada_ts


def test_proximo_candle_na_ponta_de_baixo_compra_na_abertura_seguinte():
    # sinal de compra às 09:55 (barra 3); a barra 4 abre em 95: compra a 95; stop = 95 - 9,333 = 85,67 estoura no mesmo minuto
    tr = rodar(B_BAIXO, S_BAIXO, **PROX)[0]
    assert tr.lado == "buy" and tr.entrada_ts == ts("10:00") and tr.preco_entrada == pytest.approx(95.0)
    assert tr.saida_ts == ts("10:00") and tr.preco_saida == pytest.approx(95 - 28 / 3)


def test_proximo_candle_sem_barra_seguinte_o_sinal_morre():
    assert rodar(B_CIMA[:4], S_CIMA[:4], **PROX) == []                     # sinal na última barra: não há abertura para entrar
    assert len(rodar(B_CIMA[:4], S_CIMA[:4])) == 1                          # o modo padrão já teria entrado (e fecha no fim dos dados)


def test_proximo_candle_abertura_na_ultima_entrada_ou_depois_nao_entra():
    # a abertura da barra 4 é 10:00: com última entrada 10:00 o sinal morre; com 10:01 ainda entra
    assert rodar(B_CIMA, S_CIMA, **PROX, ult_entrada_min=10 * 60) == []
    assert rodar(B_CIMA, S_CIMA, **PROX, ult_entrada_min=10 * 60 + 1)[0].entrada_ts == ts("10:00")
    assert rodar(B_CIMA, S_CIMA, ult_entrada_min=10 * 60)[0].entrada_ts == ts("09:50")      # no modo padrão a ordem já tinha enchido


def test_proximo_candle_com_varias_operacoes_por_dia():
    tr = rodar(B_DOIS, S_DOIS, **PROX, max_ops=5)
    assert [t.ciclo for t in tr] == [1, 2]
    assert [t.entrada_ts for t in tr] == [ts("10:00"), ts("10:30")]                    # aberturas das barras 4 e 6
    assert [t.preco_entrada for t in tr] == [105.0, 134.0]
    assert [t.desfecho for t in tr] == ["loss", "loss"]


def test_proximo_candle_respeita_o_limite_de_losses_e_o_de_operacoes():
    assert len(rodar(B_DOIS, S_DOIS, **PROX, max_ops=1)) == 1
    assert len(rodar(B_DOIS, S_DOIS, **PROX, max_ops=5, parar_n=1)) == 1


def test_proximo_candle_funciona_com_cada_book():
    for book in ("ambas", "cont", "recuo", "acima", "abaixo"):
        for bars, subs in ((B_CIMA, S_CIMA), (B_BAIXO, S_BAIXO)):
            pad = rodar(bars, subs, book=book)
            pro = rodar(bars, subs, book=book, **PROX)
            assert len(pad) == len(pro)                                  # o modo muda onde/quando entra, não se há sinal
            for a, b in zip(pad, pro):
                assert a.lado == b.lado and b.entrada_ts > a.entrada_ts


# ------------------------------------------------------------------ Etapa 3: sair ao tocar a MM
# Vende a 105 (barra 3, 09:50). `mm[t]` = EMA NO FECHAMENTO da barra t; a barra 4 (10:00) lê mm[3], a barra 3 lê mm[2].
# media_op da barra 4 = 9,333: stop = 114,33 e alvo = 95,67 (vendido).
LONGE = 1000.0


def sai_mm(sub4, mm3, mm2=LONGE, mm4=LONGE, **over):
    mm = [LONGE, LONGE, mm2, mm3, mm4]
    return run_day(com_mm(AQUECE + [B3, barra_de(sub4)], SUB_AQUECE + [S3, sub4], mm), cfg(sair_mm=True, **over))


def test_tocar_a_mm_a_favor_encerra_no_nivel_da_mm():
    sub4 = [(105, 106, 101, 102), (102, 103, 99, 100.5), (100.5, 101, 95, 96)]
    tr = sai_mm(sub4, 100.0)
    assert len(tr) == 1
    assert tr[0].saida_por == "mm" and tr[0].saida_ts == ts("10:05")      # 10:00 não alcança 100; 10:05 toca
    assert tr[0].preco_saida == pytest.approx(100.0) and tr[0].pts == pytest.approx(5.0) and tr[0].desfecho == "gain"
    # sem o controle ligado a posição segue até o alvo
    sem = run_day(com_mm(AQUECE + [B3, barra_de(sub4)], SUB_AQUECE + [S3, sub4], [LONGE, LONGE, LONGE, 100.0, LONGE]), cfg())
    assert sem[0].saida_por == "alvo" and sem[0].saida_ts == ts("10:10")


def test_saida_na_mm_paga_custo_de_ordem_a_mercado():
    sub4 = [(105, 106, 101, 102), (102, 103, 99, 100.5), (100.5, 101, 95, 96)]
    tr = sai_mm(sub4, 100.0, slippage=5.0, spread=5.0, tick=5.0)[0]
    # compra para cobrir: 100 + 5 + 2,5 = 107,5 -> teto da grade = 110. Tocar a MM "a favor" virou prejuízo por causa do custo.
    assert tr.preco_saida == pytest.approx(110.0) and tr.pts == pytest.approx(-5.0) and tr.desfecho == "loss"


def test_toque_da_mm_contra_a_posicao_com_abertura_alem_sai_na_abertura():
    # MM 110 acima da entrada vendida (contra). O sub-candle das 10:00 abre em 112 (já além da MM): sai em 112, como um stop em gap.
    tr = sai_mm(plano(112, 113, 111, 112), 110.0)[0]
    assert tr.saida_por == "mm" and tr.preco_saida == pytest.approx(112.0) and tr.pts == pytest.approx(-7.0)


def test_toque_da_mm_contra_a_posicao_sem_gap_sai_no_nivel():
    tr = sai_mm(plano(108, 111, 107, 109), 110.0)[0]
    assert tr.saida_por == "mm" and tr.preco_saida == pytest.approx(110.0) and tr.pts == pytest.approx(-5.0)


def test_gap_que_pula_a_mm_a_favor_tambem_conta_como_toque():
    # o sub-candle das 10:00 abre em 98 e fica entre 96 e 99: nunca "negocia" 100, mas o preço passou por ela vindo de 105
    tr = sai_mm(plano(98, 99, 96, 97), 100.0)[0]
    assert tr.saida_por == "mm" and tr.saida_ts == ts("10:00") and tr.preco_saida == pytest.approx(100.0)


def test_mesmo_minuto_mm_adversa_mais_perto_que_o_stop_sai_na_mm():
    tr = sai_mm(plano(108, 120, 107, 119), 110.0)[0]                      # stop 114,33 e MM 110 no mesmo minuto
    assert tr.saida_por == "mm" and tr.preco_saida == pytest.approx(110.0)


def test_mesmo_minuto_stop_mais_perto_que_a_mm_adversa_sai_no_stop():
    tr = sai_mm(plano(108, 120, 107, 119), 118.0)[0]
    assert tr.saida_por == "stop" and tr.preco_saida == pytest.approx(105 + 28 / 3)


def test_mesmo_minuto_mm_a_favor_antes_do_alvo_sai_na_mm():
    tr = sai_mm(plano(104, 105, 90, 91), 100.0)[0]                        # alvo 95,67 e MM 100 no mesmo minuto
    assert tr.saida_por == "mm" and tr.preco_saida == pytest.approx(100.0)


def test_mesmo_minuto_alvo_antes_da_mm_a_favor_mais_longe_sai_no_alvo():
    tr = sai_mm(plano(104, 105, 90, 91), 92.0)[0]
    assert tr.saida_por == "alvo" and tr.preco_saida == pytest.approx(105 - 28 / 3)


def test_mesmo_minuto_stop_vem_antes_da_mm_a_favor():
    tr = sai_mm(plano(105, 115, 99, 100), 100.0)[0]                       # o minuto vai a 115 (stop 114,33) e a 99 (MM 100)
    assert tr.saida_por == "stop" and tr.preco_saida == pytest.approx(105 + 28 / 3)


def test_mesmo_minuto_mm_adversa_vem_antes_do_alvo():
    tr = sai_mm(plano(104, 109, 90, 91), 108.0)[0]                        # alvo 95,67 também foi tocado, mas pessimista: MM primeiro
    assert tr.saida_por == "mm" and tr.preco_saida == pytest.approx(108.0)


def test_compra_toca_a_mm_acima_a_favor_e_abaixo_contra():
    # B_BAIXO: compra a 95 às 09:55. A barra 4 (10:00) lê mm[3]. stop = 85,67; alvo = 104,33.
    def sai_compra(sub4, mm3):
        mm = [LONGE, LONGE, LONGE, mm3, LONGE]
        return run_day(com_mm(AQUECE + [(99, 102, 94, 95), barra_de(sub4)], SUB_AQUECE + [S_BAIXO[3], sub4], mm), cfg(sair_mm=True))[0]

    a_favor = sai_compra([(95, 101, 94, 100)] * 3, 100.0)
    assert a_favor.lado == "buy" and a_favor.saida_por == "mm" and a_favor.preco_saida == pytest.approx(100.0)
    contra = sai_compra(plano(93, 94, 88, 89), 90.0)
    assert contra.saida_por == "mm" and contra.preco_saida == pytest.approx(90.0) and contra.pts == pytest.approx(-5.0)
    gap = sai_compra(plano(88, 89, 86, 87), 90.0)                         # abre abaixo da MM, contra a posição: sai na abertura
    assert gap.saida_por == "mm" and gap.preco_saida == pytest.approx(88.0) and gap.pts == pytest.approx(-7.0)


def test_o_minuto_da_entrada_e_imune_a_mm_no_modo_padrao():
    sub4 = plano(105, 120, 104, 119)
    # mm[2] = 99,5 está dentro do sub-candle da entrada (09:50: 99 a 106), mas ali a posição ainda não é gerida
    tr = sai_mm(sub4, LONGE, mm2=99.5)[0]
    assert tr.saida_por == "stop"
    # mm[2] = 104,5 também está no minuto da entrada; o minuto seguinte (09:55: 104 a 106) toca e aí sim sai
    tr = sai_mm(sub4, LONGE, mm2=104.5)[0]
    assert tr.saida_por == "mm" and tr.saida_ts == ts("09:55") and tr.preco_saida == pytest.approx(104.5)


def test_proximo_candle_checa_a_mm_ja_no_minuto_da_abertura():
    tr = sai_mm(plano(105, 120, 104, 119), 110.0, **PROX)[0]
    assert tr.entrada_ts == tr.saida_ts == ts("10:00") and tr.saida_por == "mm" and tr.preco_saida == pytest.approx(110.0)


def test_a_saida_so_olha_a_mm_do_fechamento_da_barra_anterior():
    # A barra 4 lê mm[3]. Com mm[3] longe e as vizinhas (mm[2], mm[4]) "perfeitas", NÃO pode haver saída pela MM.
    sub4 = plano(105, 106, 99, 100)
    tr = sai_mm(sub4, LONGE, mm2=100.0, mm4=100.0)[0]
    assert tr.saida_por == "fim_dados"
    # e o inverso: só mm[3] perfeita
    tr = sai_mm(sub4, 100.0)[0]
    assert tr.saida_por == "mm" and tr.saida_ts == ts("10:00") and tr.preco_saida == pytest.approx(100.0)


def test_mm_ainda_sem_historico_nao_sai():
    mm = [float("nan")] * 5
    tr = run_day(com_mm(AQUECE + [B3, barra_de(plano(105, 106, 99, 100))], SUB_AQUECE + [S3, plano(105, 106, 99, 100)], mm), cfg(sair_mm=True))
    assert tr[0].saida_por == "fim_dados"


def test_com_o_controle_desligado_a_mm_nao_interfere():
    sub4 = plano(105, 106, 99, 100)
    mm = [LONGE, LONGE, LONGE, 100.0, LONGE]
    bars, subs = AQUECE + [B3, barra_de(sub4)], SUB_AQUECE + [S3, sub4]
    assert run_day(com_mm(bars, subs, mm), cfg())[0].saida_por == "fim_dados"
    # o filtro de afastamento sozinho lê a MM, mas não gera saída por ela
    tr = run_day(com_mm(bars, subs, [80, 80, 80, 100.0, 80]), cfg(afast_ativo=True, afast_mult=0.5))
    assert tr and all(t.saida_por != "mm" for t in tr)


def test_saida_na_mm_ligada_sem_a_coluna_mm_falha_alto():
    with pytest.raises(ValueError, match="mm"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(sair_mm=True))


def test_saida_por_registra_o_motivo_de_cada_saida():
    assert rodar(B_CIMA, S_CIMA)[0].saida_por == "stop"
    bars = AQUECE + [(99, 106, 98, 105), (105, 106, 90, 91)]
    subs = SUB_AQUECE + [S3, plano(105, 106, 90, 91)]
    assert rodar(bars, subs)[0].saida_por == "alvo"
    lado = [plano(105, 107, 103, 105)] * 6
    assert rodar(AQUECE + [B3] + [(105, 107, 103, 105)] * 6, SUB_AQUECE + [S3] + lado,
                 stop_mult=5.0, gain_mult=5.0, fim_min=10 * 60 + 30)[0].saida_por == "zeragem"
    assert rodar(AQUECE + [B3, (105, 107, 103, 105)], SUB_AQUECE + [S3, plano(105, 107, 103, 105)],
                 stop_mult=5.0, gain_mult=5.0)[0].saida_por == "fim_dados"


# ------------------------------------------------------------------ Etapa 4: Rastrear MM (acima só vende, abaixo só compra)
# Referência: fechamento da barra FECHADA anterior à do gatilho (barra 2: fecha em 96) contra a EMA do fechamento dessa mesma barra (mm[2]).
def rastro(mm, bars=B_CIMA, subs=S_CIMA, **over):
    return run_day(com_mm(bars, subs, mm), cfg(rastrear=True, **over))


def test_rastrear_acima_da_mm_so_vende():
    tr = rastro([80] * 5)                                     # fecha em 96 > 80
    assert len(tr) == 1 and tr[0].lado == "sell" and tr[0].entrada_ts == ts("09:50")
    assert [t.lado for t in rastro([80] * 5, B_BAIXO, S_BAIXO)] == []       # só havia compra (95): bloqueada


def test_rastrear_abaixo_da_mm_so_compra():
    tr = rastro([110] * 5, B_BAIXO, S_BAIXO)                  # fecha em 96 < 110
    assert len(tr) == 1 and tr[0].lado == "buy"
    assert rastro([110] * 5) == []                            # a venda (105) é bloqueada e a compra (95) nunca executa


def test_rastrear_igual_a_mm_ou_sem_mm_nao_opera():
    nan = float("nan")
    assert rastro([nan, nan, 96, nan, nan]) == []             # fechamento de i-1 (96) igual à MM de i-1; a barra 4 não tem EMA
    assert rastro([nan] * 5) == []


def test_rastrear_com_book_cont_bloqueado_segue_procurando_nas_barras_seguintes():
    # a barra 3 cruza o topo (venda), mas o fechamento de i-1 está abaixo da MM: bloqueia. A barra 4 também é avaliada (mm[3]).
    tr = rastro([110, 110, 110, 90, 90], book="cont")
    assert len(tr) == 1 and tr[0].lado == "sell" and tr[0].entrada_ts >= ts("10:00")


def test_rastrear_so_olha_o_fechamento_e_a_mm_da_barra_anterior():
    # mm[2] = 80 libera a venda; as MMs vizinhas "contra" não interferem
    assert rastro([200, 200, 80, 200, 200])[0].lado == "sell"
    # mm[2] = 110 bloqueia; as vizinhas "a favor" não liberam
    assert rastro([50, 50, 110, 50, 50]) == []
    # o fechamento da barra do gatilho (105) NÃO conta: com mm[2] = 100,5 o fechamento de i-1 (96) está abaixo -> só compra
    assert rastro([100.5] * 5) == []


def test_rastrear_com_book_ambas_arma_so_a_ordem_permitida():
    # acima da MM só a de venda: a compra (95) nunca executa mesmo que o preço a alcançasse
    bars = AQUECE + [(99, 106, 94, 95), (95, 96, 80, 81)]
    subs = SUB_AQUECE + [[(99, 102, 99, 101), (101, 106, 97, 105), (105, 105, 94, 95)], plano(95, 96, 80, 81)]
    sem = rodar(bars, subs, book="ambas")
    assert sem[0].lado == "sell"                              # sem o filtro, a venda a 105 vem primeiro
    assert rastro([110] * 5, bars, subs, book="ambas")[0].lado == "buy"      # abaixo da MM: só a compra a 95
    assert rastro([80] * 5, bars, subs, book="ambas")[0].lado == "sell"


def test_rastrear_desligado_ignora_a_mm():
    assert run_day(com_mm(B_CIMA, S_CIMA, [110] * 5), cfg())[0].lado == "sell"


def test_rastrear_ligado_sem_a_coluna_mm_falha_alto():
    with pytest.raises(ValueError, match="mm"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(rastrear=True))


# ------------------------------------------------------------------ a saída na MM é só mais uma condição: a saída normal segue valendo
def test_stop_antes_do_toque_na_mm_sai_no_stop():
    sub4 = [(105, 115, 104, 114), (114, 114, 99, 100), (100, 101, 99, 100)]        # 10:00 estoura o stop (114,33); 10:05 tocaria a MM 100
    tr = sai_mm(sub4, 100.0)[0]
    assert tr.saida_por == "stop" and tr.saida_ts == ts("10:00")


def test_alvo_antes_do_toque_na_mm_sai_no_alvo():
    sub4 = [(105, 106, 95, 96), (96, 97, 93, 94), (94, 95, 93, 94)]                # 10:00 faz o alvo (95,67); 10:05 tocaria a MM 94
    tr = sai_mm(sub4, 94.0)[0]
    assert tr.saida_por == "alvo" and tr.saida_ts == ts("10:00")


# ------------------------------------------------------------------ Etapa 5: reversões (stop-and-reverse)
# Vende a 105 (09:50). Na barra 4 o stop (114,33) estoura e a posição reverte a COMPRA no preço do stop. media_op(4) = 9,333.
SUB4_REV = [(105, 120, 104, 119), (119, 130, 118, 129), (129, 135, 128, 134)]


def com_rev(sub4=SUB4_REV, mm=None, **over):
    bars, subs = AQUECE + [B3, barra_de(sub4)], SUB_AQUECE + [S3, sub4]
    df = make_day(bars, subs) if mm is None else com_mm(bars, subs, mm)
    return run_day(df, cfg(**over))


def test_sem_reversoes_o_stop_encerra_a_operacao():
    tr = com_rev()
    assert len(tr) == 1 and tr[0].saida_por == "stop" and tr[0].reversao == 0


def test_stop_com_perda_reverte_no_preco_do_stop_e_a_perna_nova_sai_no_alvo():
    tr = com_rev(max_rev=1)
    assert [t.lado for t in tr] == ["sell", "buy"] and [t.ciclo for t in tr] == [1, 1] and [t.reversao for t in tr] == [0, 1]
    assert tr[0].preco_saida == pytest.approx(105 + 28 / 3)                      # stop da entrada original
    assert tr[1].preco_entrada == pytest.approx(105 + 28 / 3)                    # reverte NO preço do stop
    assert tr[1].entrada_ts == tr[0].saida_ts == ts("10:00")
    # herda stop/alvo da entrada (1,0 / 1,0 neste cfg): alvo = 114,33 + 9,33 = 123,67 -> batido às 10:05 (máxima 130)
    assert tr[1].saida_por == "alvo" and tr[1].saida_ts == ts("10:05") and tr[1].pts == pytest.approx(28 / 3)


def test_o_sub_candle_da_reversao_e_imune():
    # no sub-candle de 10:00 a mínima (104) ficaria abaixo do stop da perna revertida (105), mas ali ela acabou de nascer
    tr = com_rev(max_rev=1)
    assert tr[1].saida_ts == ts("10:05")


def test_stop_e_alvo_proprios_da_reversao():
    tr = com_rev(max_rev=1, rev_stop_mult=0.5, rev_gain_mult=2.0)
    # alvo = 114,33 + 2,0 x 9,33 = 133,0: só o sub-candle de 10:10 (máxima 135) alcança
    assert tr[1].saida_por == "alvo" and tr[1].saida_ts == ts("10:10") and tr[1].preco_saida == pytest.approx(105 + 28 / 3 + 56 / 3)
    # stop próprio mais curto: 114,33 - 0,5 x 9,33 = 109,67
    sub = [(105, 120, 104, 119), (119, 119, 108, 110), (110, 111, 100, 101)]
    tr = com_rev(sub, max_rev=1, rev_stop_mult=0.5)
    assert tr[1].saida_por == "stop" and tr[1].preco_saida == pytest.approx(105 + 28 / 3 - 14 / 3)


def test_zero_herda_stop_e_alvo_da_entrada():
    assert com_rev(max_rev=1, rev_stop_mult=0.0, rev_gain_mult=0.0)[1].saida_ts == ts("10:05")


CADEIA = [(105, 120, 104, 119), (119, 119, 104, 110), (110, 111, 100, 101)]    # stop, stop da reversão, fim dos dados


def test_numero_maximo_de_reversoes():
    n = lambda k: [(t.lado, t.reversao, t.saida_por) for t in com_rev(CADEIA, max_rev=k)]
    assert n(0) == [("sell", 0, "stop")]
    assert n(1) == [("sell", 0, "stop"), ("buy", 1, "stop")]                       # a 2ª perna perde mas não há mais reversões
    assert n(2) == [("sell", 0, "stop"), ("buy", 1, "stop"), ("sell", 2, "fim_dados")]
    assert n(5) == n(2)                                                            # a cadeia termina sozinha


def test_reversoes_contam_no_mesmo_ciclo_e_nao_consomem_operacoes_por_dia():
    tr = com_rev(CADEIA, max_rev=2, max_ops=1)
    assert [t.ciclo for t in tr] == [1, 1, 1]


def test_so_o_stop_reverte():
    # alvo
    bars = AQUECE + [B3, (105, 106, 90, 91)]
    assert len(run_day(make_day(bars, SUB_AQUECE + [S3, plano(105, 106, 90, 91)]), cfg(max_rev=3))) == 1
    # saída ao tocar a MM (mesmo com perda) e zeragem não revertem
    mm = [LONGE, LONGE, LONGE, 110.0, LONGE]
    tr = com_rev(plano(108, 111, 107, 109), mm=mm, max_rev=3, sair_mm=True)
    assert len(tr) == 1 and tr[0].saida_por == "mm" and tr[0].pts < 0
    lado = [plano(105, 107, 103, 105)] * 6
    tr = rodar(AQUECE + [B3] + [(105, 107, 103, 105)] * 6, SUB_AQUECE + [S3] + lado, stop_mult=5.0, gain_mult=5.0, fim_min=10 * 60 + 30, max_rev=3)
    assert len(tr) == 1 and tr[0].saida_por == "zeragem"


def test_a_perna_revertida_entra_a_mercado_com_custo():
    custo = dict(slippage=5.0, spread=5.0, tick=5.0)
    tr = com_rev(max_rev=1, **custo)
    # compra a mercado no stop 114,33: + 7,5 = 121,83 -> teto da grade = 125 (o mesmo preço da saída da perna vendida)
    assert tr[0].preco_saida == pytest.approx(125.0) and tr[1].preco_entrada == pytest.approx(125.0)


def test_reversao_no_modo_proximo_candle_e_imediata_no_preco_do_stop():
    tr = com_rev(max_rev=1, **PROX)
    assert [t.entrada_ts for t in tr] == [ts("10:00"), ts("10:00")]                 # a reversão não espera a abertura seguinte
    assert tr[1].lado == "buy" and tr[1].preco_entrada == pytest.approx(105 + 28 / 3)


def test_reversao_ignora_a_ultima_entrada():
    # última entrada 10:00: a entrada (09:50) é válida e o stop só vem às 10:00, mas a reversão vale mesmo assim
    tr = com_rev(max_rev=1, ult_entrada_min=10 * 60)
    assert len(tr) == 2


def test_reversao_ignora_o_rastrear_mm():
    # acima da MM só vende; a reversão compra mesmo assim
    tr = rastro([80] * 5, B_CIMA, S_CIMA, max_rev=1)
    assert [t.lado for t in tr] == ["sell", "buy"]


def test_saida_na_mm_vale_para_a_perna_revertida():
    mm = [LONGE, LONGE, LONGE, 120.0, LONGE]            # a MM (120) fica além do stop da venda: o stop vem primeiro e reverte
    tr = com_rev(mm=mm, max_rev=1, sair_mm=True)
    assert [t.saida_por for t in tr] == ["stop", "mm"] and tr[1].preco_saida == pytest.approx(120.0) and tr[1].saida_ts == ts("10:05")


# ------------------------------------------------------------------ Etapa 6: controle de cauda e filtros de regime
NAN = float("nan")


def com_ctx(bars=B_CIMA, subs=S_CIMA, **colunas):
    """B_CIMA com colunas de contexto: `bbw`/`slope` (por barra, valor no FECHAMENTO dela) e `gap_dia`/`vol_ontem` (escalares do dia)."""
    df = make_day(bars, subs)
    for k, v in colunas.items():
        df[k] = v
    return df


def entrou_as_0950(tr):
    return len(tr) >= 1 and tr[0].entrada_ts == ts("09:50")


def test_filtro_de_gap_bloqueia_o_dia_no_limite_ou_acima():
    f = lambda gap, **o: run_day(com_ctx(gap_dia=gap), cfg(gap_ativo=True, gap_max=0.5, **o))
    assert entrou_as_0950(f(0.3)) and entrou_as_0950(f(0.49))
    assert f(0.5) == [] and f(2.0) == []                          # >= bloqueia
    assert f(NAN) == []                                           # sem história de 20 pregões: bloqueia
    assert entrou_as_0950(run_day(com_ctx(gap_dia=9.0), cfg()))   # desligado ignora a coluna


def test_filtro_de_amplitude_de_ontem_bloqueia_o_dia_no_limite_ou_acima():
    f = lambda v: run_day(com_ctx(vol_ontem=v), cfg(vol_ativo=True, vol_max=1.5))
    assert entrou_as_0950(f(1.0)) and entrou_as_0950(f(1.49))
    assert f(1.5) == [] and f(NAN) == []


def test_filtros_do_dia_ligados_sem_a_coluna_falham_alto():
    with pytest.raises(ValueError, match="gap_dia"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(gap_ativo=True, gap_max=0.5))
    with pytest.raises(ValueError, match="vol_ontem"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(vol_ativo=True, vol_max=1.5))
    with pytest.raises(ValueError, match="bbw"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(bb_ativo=True, bb_max=1.0))
    with pytest.raises(ValueError, match="slope"):
        run_day(make_day(B_CIMA, S_CIMA), cfg(incl_ativo=True, incl_max=0.5))


def test_largura_das_bandas_so_a_barra_anterior_decide():
    # a barra 3 (gatilho) lê bbw[2]; se reprovar, a barra 4 lê bbw[3]
    bb = lambda w, **o: run_day(com_ctx(bbw=w), cfg(bb_ativo=True, bb_max=1.0, **o))
    assert entrou_as_0950(bb([9, 9, 0.8, 9, 9]))                  # só bbw[2] conta: as vizinhas "ruins" não bloqueiam
    assert bb([0.8, 0.8, 9, 9, 0.8]) == []                        # só bbw[2] e bbw[3] contam: as "boas" não liberam
    assert entrou_as_0950(bb([9, 9, 1.0, 9, 9]))                  # igual ao máximo passa (bloqueia só acima)
    assert bb([9, 9, 1.01, 9, 9]) == [] and bb([NAN] * 5) == []


def test_largura_das_bandas_minimo():
    mn = lambda w: run_day(com_ctx(bbw=w), cfg(bb_ativo=True, bb_min=0.5, bb_max=2.0))
    assert entrou_as_0950(mn([9, 9, 0.5, 9, 9]))                  # igual ao mínimo passa
    assert mn([9, 9, 0.49, 0.49, 9]) == []                        # estreita demais
    assert run_day(com_ctx(bbw=[9, 9, 0.1, 9, 9]), cfg(bb_ativo=True, bb_min=0.0, bb_max=2.0)) != []      # mínimo 0 = sem mínimo
    assert run_day(com_ctx(bbw=[9, 9, 0.8, 9, 9]), cfg()) != []   # desligado ignora a coluna


def test_inclinacao_da_mm_so_a_barra_anterior_decide():
    # media_op da barra 3 = 10: com incl_max 0,5 o limite é 5 pontos (|inclinação| >= 5 bloqueia)
    inc = lambda s: run_day(com_ctx(slope=s), cfg(incl_ativo=True, incl_max=0.5))
    assert entrou_as_0950(inc([0, 0, 4.9, 9, 0])) and entrou_as_0950(inc([9, 9, -4.9, 9, 9]))
    assert inc([0, 0, 5.0, 9, 0]) == [] and inc([0, 0, -5.0, 9, 0]) == []                 # em módulo; na barra 4 o limite é 4,67 e 9 também reprova
    assert inc([NAN] * 5) == []


# ------------------------------------------------------------------ candle discrepante (descarte na media_operacao)
# Janela de 3 barras fechadas com um candle largo no meio (range 80 contra 10 e 10). A ZONA usa as 3 barras (máx 160, mín 80).
BARRAS_DISC = [(95, 100, 90, 96), (95, 160, 80, 96), (95, 100, 90, 96), (150, 170, 149, 168)]
SUBS_DISC = [plano(*b) for b in BARRAS_DISC]


def disc(x, **o):
    return run_day(make_day(BARRAS_DISC, SUBS_DISC), cfg(descarte_x=x, book="cont", **o))


def test_candle_discrepante_sai_da_media_operacao_e_nao_da_zona():
    # sem o descarte: media_op = (10 + 80 + 10) / 3 = 33,33 e a ponta de cima (160 + 16,67) nunca é alcançada (máxima da barra 3 = 170)
    assert disc(0.0) == []
    # com o descarte (80 > 2 x 10): media_op = (10 + 10) / 2 = 10; ponta = 160 + 5 = 165, alcançada; a zona continua 80-160
    tr = disc(2.0)
    assert len(tr) == 1 and tr[0].lado == "sell"
    assert tr[0].preco_entrada == pytest.approx(165.0)


def test_candle_discrepante_so_acima_do_limite_estrito():
    # janela 10, 10, 20: 20 não é MAIS que 2 x 10 -> não descarta (média 13,33); com 1,99 descarta (média 10)
    bars = [(95, 100, 90, 96), (95, 100, 90, 96), (95, 110, 90, 96), (150, 170, 149, 168)]
    subs = [plano(*b) for b in bars]
    f = lambda x: run_day(make_day(bars, subs), cfg(descarte_x=x, book="cont"))
    assert f(2.0)[0].preco_entrada == pytest.approx(110 + 0.5 * (40 / 3))
    assert f(1.99)[0].preco_entrada == pytest.approx(110 + 0.5 * 10)


def test_candle_discrepante_descarta_um_so_candle():
    # 10, 40, 40: o maior (40) não passa de 2 x o 2º maior (40): nada sai
    bars = [(95, 100, 90, 96), (95, 130, 90, 96), (95, 130, 90, 96), (150, 170, 149, 168)]
    subs = [plano(*b) for b in bars]
    tr = run_day(make_day(bars, subs), cfg(descarte_x=2.0, book="cont"))
    assert tr[0].preco_entrada == pytest.approx(130 + 0.5 * 30)           # media_op = (10 + 40 + 40) / 3 = 30
    # 10, 10, 10, 90 (n_media = 4): 90 > 2 x 10 -> sai um candle só; media_op = 10
    bars4 = [(95, 100, 90, 96)] * 3 + [(95, 180, 90, 96)] + [(150, 190, 149, 188)]
    subs4 = [plano(*b) for b in bars4]
    tr4 = run_day(make_day(bars4, subs4), cfg(descarte_x=2.0, n_media=4, n_zona=4, book="cont"))
    assert tr4[0].preco_entrada == pytest.approx(180 + 0.5 * 10)


def test_candle_discrepante_vale_tambem_para_stop_e_alvo_da_posicao():
    # entrada a 165 (media_op 10 com o descarte). Na barra seguinte a janela é 80, 10, 21: o 80 é descartado (> 2 x 21) e
    # media_op = (10 + 21) / 2 = 15,5, então o stop fica a 165 + 15,5 = 180,5 (sem o descarte seria 165 + 37).
    bars = BARRAS_DISC + [(168, 181, 160, 170)]
    subs = SUBS_DISC + [plano(168, 181, 160, 170)]
    tr = run_day(make_day(bars, subs), cfg(descarte_x=2.0, book="cont", stop_mult=1.0, gain_mult=100.0))
    assert tr[0].saida_por == "stop"
    assert tr[0].pts == pytest.approx(-15.5)


def test_cauda_para_o_dia_quando_o_realizado_passa_do_limite():
    # B_DOIS: o 1º ciclo perde 9,33 pts. A barra seguinte (índice 5) tem media_op = (10 + 8 + 21) / 3 = 13.
    um = lambda x: len(rodar(B_DOIS, S_DOIS, max_ops=5, parar_dia_x=x))
    assert um(0.5) == 1                                           # limite 6,5 < 9,33: acabou o dia
    assert um(1.0) == 2                                           # limite 13 > 9,33: ainda opera
    assert um(0.8) == 2                                           # 0,8 x 13 = 10,4 > 9,33: usa a media_operacao da barra ATUAL (13), não a da anterior (9,33)
    assert um(0.0) == 2                                           # desligado


def test_cauda_tambem_barra_a_reversao():
    assert [t.reversao for t in com_rev(max_rev=1, parar_dia_x=0.9)] == [0]              # perda 9,33 >= 0,9 x 9,33: não reverte
    assert [t.reversao for t in com_rev(max_rev=1, parar_dia_x=1.5)] == [0, 1]           # 9,33 < 14: reverte


LADO6 = [plano(105, 107, 103, 105)] * 6
BARRAS6 = AQUECE + [B3] + [(105, 107, 103, 105)] * 6
SUBS6 = SUB_AQUECE + [S3] + LADO6


def test_tempo_maximo_sai_a_mercado_na_abertura_do_sub_candle():
    tm = lambda minutos, **o: rodar(BARRAS6, SUBS6, stop_mult=5.0, gain_mult=5.0, tempo_max=minutos, **o)[0]
    t5 = tm(5)                                                    # entrou 09:50: 09:55 é o primeiro sub-candle a >= 5 min
    assert t5.saida_por == "tempo" and t5.saida_ts == ts("09:55") and t5.preco_saida == pytest.approx(105.0)
    assert tm(10).saida_ts == ts("10:00") and tm(7).saida_ts == ts("10:00")               # 09:57 não existe: o 1º >= é 10:00
    assert tm(5).desfecho == "loss"                                                        # pontos 0: loss (≤ 0), como o stop
    com_custo = tm(5, slippage=5.0, spread=5.0, tick=5.0)
    assert com_custo.preco_saida == pytest.approx(115.0) and com_custo.pts == pytest.approx(-10.0)     # a mercado paga custo


def test_tempo_maximo_a_zeragem_vem_primeiro_e_desligado_nao_interfere():
    t = rodar(BARRAS6, SUBS6, stop_mult=5.0, gain_mult=5.0, tempo_max=10, fim_min=9 * 60 + 57)[0]
    assert t.saida_por == "zeragem"
    assert rodar(BARRAS6, SUBS6, stop_mult=5.0, gain_mult=5.0)[0].saida_por == "fim_dados"             # sem tempo máximo, segue até o fim


def test_tempo_maximo_no_proximo_candle_conta_da_abertura():
    tr = depois_do_sinal(plano(108, 112, 107, 110), **PROX, stop_mult=5.0, gain_mult=5.0, tempo_max=10)[0]
    assert tr.entrada_ts == ts("10:00") and tr.saida_por == "tempo" and tr.saida_ts == ts("10:10")


def test_tempo_maximo_nao_reverte_e_cada_perna_tem_o_seu_relogio():
    # a perna vendida (09:50) sai por TEMPO às 09:55, antes de qualquer stop: não há reversão
    assert [t.saida_por for t in com_rev(max_rev=2, tempo_max=5)] == ["tempo"]
    # tempo 11: o stop estoura às 10:00 (antes de 10:01) e reverte; a perna nova nasce às 10:00 e sai por TEMPO no 1º sub-candle >= 10:11 (10:15)
    sub4 = [(105, 120, 104, 119), (119, 119, 117, 118), (118, 119, 117, 118)]
    sub5 = plano(119, 121, 117, 120)
    bars = AQUECE + [B3, barra_de(sub4), barra_de(sub5)]
    subs = SUB_AQUECE + [S3, sub4, sub5]
    tr = run_day(make_day(bars, subs), cfg(max_rev=1, tempo_max=11, gain_mult=9.0))
    assert [t.saida_por for t in tr] == ["stop", "tempo"] and [t.reversao for t in tr] == [0, 1]
    assert tr[1].entrada_ts == ts("10:00") and tr[1].saida_ts == ts("10:15") and tr[1].preco_saida == pytest.approx(119.0)


def test_cauda_no_limite_exato_a_perda_igual_ao_limite_encerra_o_dia():
    # Números inteiros: media_op = 10 em todas as barras; o 1º ciclo perde exatamente 10 pts (venda a 105, stop a 115).
    bars = AQUECE + [(99, 108, 98, 105), (105, 115, 105, 114), (114, 121, 113, 120)]
    subs = SUB_AQUECE + [[(99, 101, 98, 100), (100, 108, 99, 105), (105, 106, 104, 105)], plano(105, 115, 105, 114),
                         [(114, 116, 113, 115), (115, 121, 114, 120), (120, 121, 119, 120)]]
    n = lambda x: len(rodar(bars, subs, max_ops=5, parar_dia_x=x))
    assert rodar(bars, subs, max_ops=5)[0].pts == pytest.approx(-10.0)
    assert n(1.0) == 1                  # limite 10 == perda 10: encerra (<=)
    assert n(1.01) == 2                 # limite 10,1 > perda: ainda opera
    assert n(0.0) == 2


# ------------------------------------------------------------------ Trailing stop (porte do ghost_trail_start_r do sistema antigo)
# Vende a 105 (barra 3, 09:50, entrada limite: o sub-candle do fill é imune). media_op(3) = 10, media_op(4) = 9,33. A proteção só é atualizada
# quando uma barra FECHA; `gain_mult = 10` mantém o alvo longe para isolar o trailing.
BAR4 = plano(105, 106, 90, 92)           # avanço a favor de 15 pts (1,6 x media_op): arma o trailing com trail_r <= 1,6
BAR5 = plano(92, 100, 91, 99)            # máxima 100: vira o nível protegido (venda: máxima da barra fechada)
BAR6 = plano(96, 101, 95, 100)           # toca 100


def com_trail(extras, **over):
    bars = AQUECE + [B3] + [barra_de(s) for s in extras]
    subs = SUB_AQUECE + [S3] + list(extras)
    return run_day(make_day(bars, subs), cfg(gain_mult=10.0, **over))


def test_trailing_arma_numa_barra_fechada_e_o_stop_passa_a_seguir_a_maxima_da_seguinte():
    tr = com_trail([BAR4, BAR5, BAR6], trail_r=1.0)
    assert len(tr) == 1 and tr[0].saida_por == "trailing" and tr[0].desfecho == "gain"
    assert tr[0].preco_saida == pytest.approx(100.0) and tr[0].pts == pytest.approx(5.0)
    # desligado (padrão): nada protege a posição, que segue até o fim dos dados
    off = com_trail([BAR4, BAR5, BAR6])
    assert [(t.saida_por, t.preco_saida) for t in off] == [("fim_dados", 99.0)] or off[0].saida_por == "fim_dados"
    assert com_trail([BAR4, BAR5, BAR6], trail_r=0.0)[0].saida_por == "fim_dados"


def test_trailing_no_fechamento_que_arma_ainda_nao_move_o_stop():
    # BAR4 arma (fecha com avanço 15 >= 9,33), mas a proteção só passa a existir quando BAR5 fecha: com BAR5 já tocando 100 no
    # próprio sub-candle em que o stop normal (116) está longe, nada acontece até BAR6
    tr = com_trail([BAR4, plano(92, 101, 91, 99)], trail_r=1.0)       # BAR5 sobe até 101 > 100 e NÃO é barrada (prot ainda não existe)
    assert tr[0].saida_por == "fim_dados"


def test_trailing_so_conta_o_que_veio_depois_da_entrada_na_barra_da_entrada():
    # A barra 3 foi até 98 ANTES do fill (adv de 7 >= 0,5 x 10 se contasse inteira); depois da entrada só foi a 104 (adv 1).
    b4, b5 = plano(105, 108, 104, 106), plano(106, 109, 105, 108)
    com = com_trail([b4, b5], trail_r=0.5)
    sem = com_trail([b4, b5])
    assert [(t.saida_por, t.preco_saida) for t in com] == [(t.saida_por, t.preco_saida) for t in sem] and com[0].saida_por == "fim_dados"
    # prova de que o cenário discrimina: com a barra 4 afundando 1 pt a mais o avanço passa de 4,67 e o trailing arma e atua
    com2 = com_trail([plano(105, 108, 100, 106), plano(106, 109, 105, 108), plano(106, 110, 105, 109)], trail_r=0.5)
    assert com2[0].saida_por == "trailing"


def test_trailing_so_aperta_nunca_afrouxa():
    b6, b7 = plano(96, 99, 93, 94), plano(94, 100, 93, 99)
    tr = com_trail([BAR4, BAR5, b6, b7], trail_r=1.0)
    # barra 5 fixa o nível em 100; a barra 6 (máxima 99) aperta para 99; a barra 7 toca 99 e sai ali (não em 100)
    assert tr[0].saida_por == "trailing" and tr[0].preco_saida == pytest.approx(99.0) and tr[0].pts == pytest.approx(6.0)


def test_trailing_com_gap_na_abertura_sai_na_abertura():
    tr = com_trail([BAR4, BAR5, plano(103, 104, 102, 103)], trail_r=1.0)      # abre acima do nível protegido (100)
    assert tr[0].saida_por == "trailing" and tr[0].preco_saida == pytest.approx(103.0) and tr[0].pts == pytest.approx(2.0)


def test_saida_pelo_stop_normal_continua_sendo_stop():
    tr = depois_do_sinal(SUB4_REV, trail_r=1.0)
    assert tr[0].saida_por == "stop"


def test_trailing_com_perda_tambem_reverte_e_a_reversao_zera_a_protecao():
    # barra 5 fecha com máxima 108 (> 105): o nível protegido fica ACIMA da entrada; a barra 6 o toca em 108 = perda de 3 pts
    b5, b6, b7 = plano(92, 108, 91, 107), plano(106, 109, 105, 108), plano(109, 112, 104, 111)
    tr = com_trail([BAR4, b5, b6, b7], trail_r=1.0, max_rev=1)
    assert [(t.lado, t.reversao, t.saida_por) for t in tr] == [("sell", 0, "trailing"), ("buy", 1, "fim_dados")]
    assert tr[0].pts == pytest.approx(-3.0) and tr[0].desfecho == "loss"
    # se a proteção (ou o trailing já armado) da 1ª perna vazasse para a 2ª, a mínima 104 da barra 7 a estouraria: ela segue aberta até o fim dos dados
    assert tr[1].preco_entrada == pytest.approx(108.0)


def test_trailing_no_proximo_candle_conta_o_sub_candle_da_abertura():
    # entrada a mercado na abertura da barra 4 (104). O 1º sub-candle dela vai a 89: avanço 15 >= 1,5 x 9,33 (14). Sem esse sub-candle o avanço
    # seria 13 (mínima 91) e não armaria.
    b4 = [(104, 105, 89, 92), (92, 93, 91, 92), (92, 93, 91, 92)]
    tr = com_trail([b4, plano(92, 100, 91, 99), plano(96, 101, 95, 100)], trail_r=1.5, modo_entrada="proximo_candle")
    assert tr[0].preco_entrada == pytest.approx(104.0)
    assert tr[0].saida_por == "trailing" and tr[0].preco_saida == pytest.approx(100.0) and tr[0].pts == pytest.approx(4.0)


# ------------------------------------------------------------------ Escada de contratos (porte do ghost_escada_* do sistema antigo)
def _trades_com_pts(pts_lista, **over):
    from strategylab.engine.fills import make_trade
    c = cfg(**over)
    ts0 = pd.Timestamp("2023-01-02 09:50")
    return [make_trade(i + 1, "buy", ts0, 100.0, ts0, 100.0 + p, "gain" if p > 0 else "loss", c) for i, p in enumerate(pts_lista)], c


def _contratos(pts_lista, **over):
    from strategylab.engine.ghost import aplicar_escada
    tr, c = _trades_com_pts(pts_lista, **over)
    return [t.contratos for t in aplicar_escada(tr, c)], tr


def test_escada_desligada_mantem_um_contrato():
    ks, tr = _contratos([5, -5, 3])
    assert ks == [1, 1, 1] and [t.rs for t in tr] == pytest.approx([5 * 0.2, -5 * 0.2, 3 * 0.2])


def test_escada_sobe_no_ganho_desce_na_perda_e_respeita_piso_e_teto():
    over = dict(escada_ini=2, escada_ganho="somar", escada_ganho_qtd=1, escada_perda="subtrair", escada_perda_qtd=1, escada_min=1, escada_max=4)
    ks, tr = _contratos([10, 10, 10, -10, -10, -10, -10], **over)
    assert ks == [2, 3, 4, 4, 3, 2, 1]                               # o 3º ganho bate no teto (4); a 4ª perda bate no piso (1)
    assert [t.rs for t in tr] == pytest.approx([p * k * 0.2 for p, k in zip([10, 10, 10, -10, -10, -10, -10], ks)])


def test_escada_quantidades_acoes_e_zero_conta_como_perda():
    over = dict(escada_ini=3, escada_ganho="subtrair", escada_ganho_qtd=2, escada_perda="somar", escada_perda_qtd=3, escada_min=1, escada_max=8)
    ks, _ = _contratos([4, 0, -2, 7], **over)
    # 3 -> (ganho: -2) 1 -> (zero = perda: +3) 4 -> (perda: +3) 7 -> (ganho: -2) 5
    assert ks == [3, 1, 4, 7]
    ks2, _ = _contratos([5, 5], escada_ini=2, escada_ganho="manter", escada_perda="manter", escada_min=1, escada_max=5)
    assert ks2 == [2, 2]                                              # "manter" não mexe, qualquer quantidade


def test_escada_comeca_preso_entre_piso_e_teto():
    ks, _ = _contratos([1], escada_ini=9, escada_min=1, escada_max=4)
    assert ks == [4]


def test_escada_no_motor_reseta_por_pregao_e_conta_cada_perna_de_reversao():
    over = dict(escada_ini=3, escada_perda="subtrair", escada_perda_qtd=1, escada_min=1, escada_max=5)
    tr = com_rev(CADEIA, max_rev=2, max_ops=1, **over)
    assert [t.reversao for t in tr] == [0, 1, 2] and [t.contratos for t in tr][:2] == [3, 2]       # a reversão é uma operação: 3, 2, ...
    assert [t.rs for t in tr] == pytest.approx([t.pts * t.contratos * 0.2 for t in tr])
    # outro pregão (nova chamada): volta a 3
    assert com_rev(CADEIA, max_rev=2, max_ops=1, **over)[0].contratos == 3
    # o caminho do preço é o mesmo sem a escada
    sem = com_rev(CADEIA, max_rev=2, max_ops=1)
    assert [(t.preco_entrada, t.preco_saida, t.pts) for t in tr] == [(t.preco_entrada, t.preco_saida, t.pts) for t in sem]


def test_trailing_arma_exatamente_no_limiar():
    # n_media = 2: media_op(4) = (10 + 8) / 2 = 9 e o limiar com trail_r 1,0 é 9; o avanço da barra 4 é 105 - 96 = 9 (igual arma)
    bars = [barra_de(x) for x in (BAR_A4, BAR_A5, BAR_A6)]
    sim = run_day(make_day(AQUECE + [B3] + bars, SUB_AQUECE + [S3, BAR_A4, BAR_A5, BAR_A6]), cfg(gain_mult=10.0, trail_r=1.0, n_media=2))
    assert sim[0].saida_por == "trailing" and sim[0].preco_saida == pytest.approx(100.0)
    nao = run_day(make_day(AQUECE + [B3] + bars, SUB_AQUECE + [S3, BAR_A4, BAR_A5, BAR_A6]), cfg(gain_mult=10.0, trail_r=1.01, n_media=2))
    assert nao[0].saida_por == "fim_dados"


BAR_A4 = plano(105, 106, 96, 98)
BAR_A5 = plano(98, 100, 97, 99)
BAR_A6 = plano(96, 101, 95, 100)


def test_trailing_na_compra_segue_a_minima_da_barra_fechada():
    # espelho da venda: compra a 95 (barra 3); a barra 4 avança 15 (arma); a barra 5 fecha com mínima 100 (nível protegido); a barra 6 o toca
    b4, b5, b6 = plano(95, 110, 94, 108), plano(108, 109, 100, 101), plano(104, 105, 99, 100)
    bars = AQUECE + [(99, 102, 94, 95)] + [barra_de(x) for x in (b4, b5, b6)]
    subs = SUB_AQUECE + [S_BAIXO[3], b4, b5, b6]
    tr = run_day(make_day(bars, subs), cfg(gain_mult=10.0, trail_r=1.0))
    assert tr[0].lado == "buy" and tr[0].preco_entrada == pytest.approx(95.0)
    assert tr[0].saida_por == "trailing" and tr[0].preco_saida == pytest.approx(100.0) and tr[0].pts == pytest.approx(5.0)
    assert run_day(make_day(bars, subs), cfg(gain_mult=10.0))[0].saida_por == "fim_dados"
