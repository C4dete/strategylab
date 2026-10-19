"""Matriz de combinações: o motor não pode quebrar nem violar invariantes, seja qual for a mistura de controles.

Cada combinação roda o backtest num BD sintético e confere propriedades que valem SEMPRE (horários, grade de ticks, ordem
das operações, contagem de losses, coerência entre desfecho e motivo da saída). Não compara valores com um oráculo (isso está
em `test_modos_vs_oraculo.py` e `test_golden.py`): o objetivo aqui é achar combinações que dão erro ou resultado impossível.

`test_amostra_de_combinacoes` roda uma amostra fixa (rápido); `test_todas_as_combinacoes` roda o produto cartesiano inteiro (lento).
"""

from __future__ import annotations

import itertools
import random

import pandas as pd
import pytest

from strategylab.engine import data
from strategylab.engine.params import EXECUCAO, Params, hhmm_para_min
from strategylab.engine.runner import executar, rodar_trades
from tests.conftest import csv_sintetico

DIMENSOES = {
    "modo_entrada": [{"modo_entrada": "padrao"}, {"modo_entrada": "proximo_candle"}],
    "sair_mm": [{"sair_ao_tocar_mm": False}, {"sair_ao_tocar_mm": True, "mm_periodo": 9}],
    "rastrear": [{"rastrear_mm": False}, {"rastrear_mm": True}],
    "filtro": [{"filtro_afast_mm_ativo": False}, {"filtro_afast_mm_ativo": True, "filtro_afast_mm_x_media": 0.2}],
    "book": [{"book": b} for b in ("cont", "ambas", "recuo", "acima", "abaixo")],
    "penetracao": [{"penetracao_ticks": n} for n in (0, 1, 3)],
    "gestao": [
        dict(operacoes_por_dia=1),
        dict(operacoes_por_dia=4, stop_x_media=0.5, alvo_x_media=1.5),
        dict(operacoes_por_dia=5, parar_apos_losses=2, contagem_losses="seguidos"),
        dict(operacoes_por_dia=5, parar_apos_losses=2, contagem_losses="dia", stop_x_media=2.0, alvo_x_media=6.0),
        dict(operacoes_por_dia=3, reversoes=2, rev_stop_x_media=0.7, rev_alvo_x_media=2.0),
        dict(operacoes_por_dia=3, reversoes=2, rev_stop_x_media=0.7, trailing_inicio_r=0.6),
        dict(operacoes_por_dia=2, trailing_inicio_r=1.2, parar_apos_losses=2, contagem_losses="seguidos"),
        dict(operacoes_por_dia=3, reversoes=2, escada_contratos=3, escada_ganho_acao="somar", escada_ganho_qtd=1, escada_perda_acao="subtrair",
             escada_perda_qtd=2, escada_min=1, escada_max=5),
        dict(operacoes_por_dia=2, reversoes=5, parar_apos_losses=3, contagem_losses="dia"),
    ],
    "janela": [
        {},
        dict(janela_inicio="09:30", janela_fim="16:30", ultima_entrada="15:00", candles_gatilho=8, candles_media=3, bracket_fracao=0.3),
        dict(ultima_entrada=None),
        dict(candles_gatilho=1, candles_media=2),
        dict(candles_gatilho=1, candles_media=5, bracket_fracao=0.25),
    ],
}

TODAS = [
    {k: v for parcial in combo for k, v in parcial.items()}
    for combo in itertools.product(*DIMENSOES.values())
]
AMOSTRA = random.Random(2026).sample(TODAS, 96)


@pytest.fixture(scope="module")
def mercado():
    raw, _ = data.carregar_csv(csv_sintetico(dias=25, semente=33).encode())
    return data.preparar_barras(raw, 10)


def _minutos(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s)
    return s.dt.hour * 60 + s.dt.minute


def confere(tr: pd.DataFrame, p: Params) -> None:
    """Invariantes que valem para QUALQUER combinação de controles."""
    ini = hhmm_para_min(p.janela_inicio)
    fim = hhmm_para_min(p.janela_fim)
    ult = hhmm_para_min(p.ultima_entrada) if p.ultima_entrada else fim
    if tr.empty:
        return
    ent, sai = _minutos(tr["entrada_ts"]), _minutos(tr["saida_ts"])

    # horários
    inicial = tr["reversao"] == 0                   # a reversão é continuação do ciclo: ignora a última entrada
    assert (ent >= ini).all() and (ent[inicial] < ult).all(), "entrada fora da janela / depois da última entrada"
    assert (sai <= fim).all(), "posição passou da zeragem"
    assert (tr["saida_ts"] >= tr["entrada_ts"]).all()

    # preços na grade de ticks (limite arredonda ao tick; mercado arredonda contra)
    assert (tr["preco_entrada"] % EXECUCAO.tick_pts == 0).all() and (tr["preco_saida"] % EXECUCAO.tick_pts == 0).all()

    # contas
    sinal = tr["lado"].map({"buy": 1.0, "sell": -1.0})
    assert (tr["pts"] - (tr["preco_saida"] - tr["preco_entrada"]) * sinal).abs().max() < 1e-9
    assert (tr["rs"] - tr["pts"] * tr["contratos"] * EXECUCAO.valor_ponto).abs().max() < 1e-9
    if p.escada_contratos == 0:
        assert (tr["contratos"] == EXECUCAO.contratos).all()
    else:
        assert tr["contratos"].between(p.escada_min, p.escada_max).all()

    # motivo da saída coerente com o desfecho
    assert set(tr["saida_por"]) <= {"stop", "alvo", "mm", "zeragem", "fim_dados", "tempo", "trailing"}
    if p.tempo_max_min == 0:
        assert "tempo" not in set(tr["saida_por"])
    else:                                         # dados completos (1 min): a perna sai exatamente N min depois de entrar
        t_ = tr[tr["saida_por"] == "tempo"]
        assert ((t_["saida_ts"] - t_["entrada_ts"]) == pd.Timedelta(minutes=p.tempo_max_min)).all()
    if not p.sair_ao_tocar_mm:
        assert "mm" not in set(tr["saida_por"])
    if p.trailing_inicio_r == 0:
        assert "trailing" not in set(tr["saida_por"])
    assert ((tr["saida_por"] == "zeragem") == (tr["desfecho"] == "time_close")).all()
    assert ((tr["saida_por"] == "fim_dados") == (tr["desfecho"] == "eod")).all()
    assert (tr.loc[tr["saida_por"] == "alvo", "desfecho"] == "gain").all()
    ganhos = tr[tr["desfecho"] == "gain"]
    assert (ganhos.loc[ganhos["saida_por"].isin(["stop", "trailing", "mm", "tempo"]), "pts"] > 0).all()      # stop/MM: gain só se sobrou ponto
    assert (tr.loc[tr["desfecho"] == "loss", "pts"] <= 0).all()
    assert (sai[tr["saida_por"] == "zeragem"] == fim).all()

    # entradas: modo próximo candle sempre na abertura de uma barra de 10 min
    if p.modo_entrada == "proximo_candle":
        assert (ent[inicial] % EXECUCAO.timeframe_min == 0).all()

    # reversões: só existem se pedidas, no máximo `reversoes` por ciclo, no lado oposto, logo após um stop com perda
    assert (tr["reversao"] <= p.reversoes).all()
    if p.reversoes == 0:
        assert (tr["reversao"] == 0).all()

    # por pregão: teto de CICLOS (reversões não contam), ciclos sequenciais, pernas encadeadas, sem sobreposição e losses
    for _, d in tr.groupby("data", sort=True):
        d = d.sort_values("entrada_ts")
        if p.escada_contratos > 0:                                  # escada: começa o dia no inicial e cada passo respeita a regra
            ks = d["contratos"].tolist()
            assert ks[0] == p.escada_contratos, "o pregão não começou nos contratos iniciais"
            for k_ant, pts_ant, k_novo in zip(ks, d["pts"].tolist(), ks[1:]):
                acao, q = (p.escada_ganho_acao, p.escada_ganho_qtd) if pts_ant > 0 else (p.escada_perda_acao, p.escada_perda_qtd)
                esperado = k_ant + q if acao == "somar" else k_ant - q if acao == "subtrair" else k_ant
                assert k_novo == max(p.escada_min, min(p.escada_max, esperado)), "passo da escada fora da regra"
        ciclos = list(dict.fromkeys(d["ciclo"]))
        assert len(ciclos) <= p.operacoes_por_dia and ciclos == list(range(1, len(ciclos) + 1))
        fim_anterior = None
        perdas_antes = []                                           # resultado (<= 0) das pernas dos ciclos anteriores
        for c, g in d.groupby("ciclo", sort=True):
            g = g.sort_values("entrada_ts")
            assert g["reversao"].tolist() == list(range(len(g))), "pernas fora de ordem"
            if fim_anterior is not None:
                assert g["entrada_ts"].iloc[0] > fim_anterior, "ciclos sobrepostos"
            for k in range(len(g) - 1):                             # cada perna que reverteu: stop (ou trailing) com perda e lado oposto
                a, b = g.iloc[k], g.iloc[k + 1]
                assert a["saida_por"] in ("stop", "trailing") and a["pts"] <= 0 and a["lado"] != b["lado"]
                assert b["entrada_ts"] == a["saida_ts"], "a reversão entra no minuto do stop"
            if p.parar_apos_losses and c > 1:
                if p.contagem_losses == "dia":
                    assert sum(perdas_antes) < p.parar_apos_losses, "ciclo novo depois de atingir o limite de losses"
                else:
                    seq = 0
                    for x in reversed(perdas_antes):
                        if not x:
                            break
                        seq += 1
                    assert seq < p.parar_apos_losses
            perdas_antes += [x <= 0 for x in g["pts"]]
            fim_anterior = g["saida_ts"].iloc[-1]


def _rodar(mercado, over):
    barras, sub = mercado
    p = Params(**over)
    tr = rodar_trades(barras, p, sub)
    confere(tr, p)
    return p, tr


def test_a_matriz_tem_o_tamanho_esperado():
    assert len(TODAS) == 2 * 2 * 2 * 2 * 5 * 3 * 9 * 5 == 10800
    assert len({str(sorted(c.items())) for c in TODAS}) == len(TODAS)


def _id(i: int, o: dict) -> str:
    return (f"{i:02d}-{'prox' if o['modo_entrada'] == 'proximo_candle' else 'pad'}-{'mm' if o['sair_ao_tocar_mm'] else 'sem'}"
            f"-{'filtro' if o['filtro_afast_mm_ativo'] else 'livre'}-{'rast' if o['rastrear_mm'] else 'nr'}-{o['book']}")


@pytest.mark.parametrize("over", [pytest.param(o, id=_id(i, o)) for i, o in enumerate(AMOSTRA)])
def test_amostra_de_combinacoes(mercado, over):
    _rodar(mercado, over)


def test_a_amostra_exercita_os_dois_modos_e_as_saidas(mercado):
    """Evita que a amostra vire teste vazio: tem operações, saídas pela MM e entradas nos dois modos."""
    motivos, modos, total = set(), set(), 0
    for over in AMOSTRA[:40]:
        p, tr = _rodar(mercado, over)
        total += len(tr)
        motivos |= set(tr["saida_por"])
        if len(tr):
            modos.add(p.modo_entrada)
    assert total > 200 and motivos >= {"stop", "alvo", "mm"} and modos == {"padrao", "proximo_candle"}


def test_mesma_combinacao_duas_vezes_da_o_mesmo_resultado(mercado):
    over = dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True, book="ambas",
                operacoes_por_dia=4, filtro_afast_mm_x_media=0.1)
    _, a = _rodar(mercado, over)
    _, b = _rodar(mercado, over)
    assert len(a) > 5
    pd.testing.assert_frame_equal(a, b)


def test_executar_completo_funciona_com_as_combinacoes_novas(mercado):
    """O caminho inteiro (motor -> métricas -> JSON), inclusive o campo novo `saida_por` e dias sem operação."""
    barras, sub = mercado
    for over in (dict(modo_entrada="proximo_candle"), dict(sair_ao_tocar_mm=True),
                 dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True,
                      filtro_afast_mm_x_media=10.0)):                   # a última quase nunca opera: resultado vazio também funciona
        r = executar(barras, Params(**over), sub)
        assert r["resumo"]["operacoes"] == len(r["operacoes"])
        assert all(o["saida_por"] in {"stop", "alvo", "mm", "zeragem", "fim_dados"} for o in r["operacoes"])


@pytest.mark.lento
@pytest.mark.parametrize("lote", range(8))
def test_todas_as_combinacoes(mercado, lote):
    """Produto cartesiano inteiro (4.320 combinações), em 8 lotes."""
    for over in TODAS[lote::8]:
        _rodar(mercado, over)


@pytest.mark.parametrize("extra", [
    dict(),
    dict(modo_entrada="proximo_candle"),
    dict(book="ambas", penetracao_ticks=0),
    dict(rastrear_mm=True),
    dict(filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.2),
    dict(stop_x_media=0.5, alvo_x_media=1.5),
    dict(reversoes=2, rev_stop_x_media=0.7),
])
def test_sair_na_mm_nao_exclui_a_saida_normal(mercado, extra):
    """A saída na MM é só mais uma condição. Com 1 operação por dia as entradas são as mesmas ligada ou desligada; então, por operação:
    a saída nunca vem depois da que existiria sem a MM, e quando NÃO foi a MM que encerrou, a saída é exatamente a normal (stop, alvo ou zeragem)."""
    def primeira_perna(over):                                     # a reversão muda o que vem depois da 1ª saída, não a 1ª saída
        tr = _rodar(mercado, over)[1]
        return tr[tr["reversao"] == 0].set_index("data")

    sem = primeira_perna(dict(extra, sair_ao_tocar_mm=False))
    com = primeira_perna(dict(extra, sair_ao_tocar_mm=True))
    assert len(sem) == len(com) > 5
    assert (sem["entrada_ts"] == com["entrada_ts"]).all() and (sem["preco_entrada"] == com["preco_entrada"]).all()
    assert (com["saida_ts"] <= sem["saida_ts"]).all()
    normais = com["saida_por"] != "mm"
    assert normais.any() and (com["saida_por"] == "mm").any()
    for col in ("saida_ts", "preco_saida", "saida_por"):
        assert (com.loc[normais, col] == sem.loc[normais, col]).all()


# ------------------------------------------------------------------ Etapa 6: controle de cauda e filtros de regime (matriz própria, em dados COM gaps)
DIM_REGIME = {
    "regime": [
        {},
        dict(parar_dia_perda_x_media=1.0),
        dict(tempo_max_min=30),
        dict(parar_dia_perda_x_media=0.5, tempo_max_min=90, reversoes=2),
        dict(filtro_gap_ativo=True, filtro_gap_max_x_media=0.4, filtro_vol_ontem_ativo=True, filtro_vol_ontem_max=1.3),
        dict(filtro_bb_ativo=True, filtro_bb_largura_min_pct=0.1, filtro_bb_largura_max_pct=0.4),
        dict(filtro_inclinacao_ativo=True, filtro_inclinacao_barras=8, filtro_inclinacao_max_x_media=0.3, mm_periodo=9),
        dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.3),
        dict(parar_dia_perda_x_media=1.0, tempo_max_min=60, filtro_gap_ativo=True, filtro_vol_ontem_ativo=True, filtro_bb_ativo=True,
             filtro_bb_largura_max_pct=0.5, filtro_inclinacao_ativo=True, filtro_inclinacao_max_x_media=0.6),
    ],
    "modo": [{"modo_entrada": "padrao"}, {"modo_entrada": "proximo_candle"}],
    "mm": [{}, dict(rastrear_mm=True, sair_ao_tocar_mm=True, filtro_afast_mm_ativo=True, filtro_afast_mm_x_media=0.2)],
    "book": [{"book": b} for b in ("cont", "ambas", "recuo")],
    "gestao": [dict(operacoes_por_dia=1), dict(operacoes_por_dia=4, parar_apos_losses=2, contagem_losses="seguidos"),
               dict(operacoes_por_dia=5, reversoes=3, rev_stop_x_media=0.7)],
}
TODAS_REGIME = [{k: v for parcial in combo for k, v in parcial.items()} for combo in itertools.product(*DIM_REGIME.values())]


@pytest.fixture(scope="module")
def mercado_com_gaps():
    from tests.test_modos_vs_oraculo import com_saltos

    raw, _ = data.carregar_csv(csv_sintetico(dias=25, semente=33).encode())
    return data.preparar_barras(com_saltos(raw), 10)


def test_a_escada_nao_muda_o_caminho_do_preco_so_o_tamanho(mercado):
    """Contrato só multiplica o ponto: entradas, saídas e pontos são idênticos com e sem a escada; só contratos e R$ mudam."""
    barras, sub = mercado
    base = dict(operacoes_por_dia=4, reversoes=2, trailing_inicio_r=0.8)
    sem = rodar_trades(barras, Params(**base), sub)
    com = rodar_trades(barras, Params(**base, escada_contratos=3, escada_ganho_acao="somar", escada_perda_acao="subtrair", escada_perda_qtd=2,
                                      escada_min=1, escada_max=6), sub)
    colunas = ["data", "entrada_ts", "preco_entrada", "saida_ts", "preco_saida", "pts", "saida_por", "reversao"]
    assert sem[colunas].equals(com[colunas])
    assert com["contratos"].nunique() > 1 and not com["rs"].equals(sem["rs"])
    assert abs(com["rs"] - com["pts"] * com["contratos"] * EXECUCAO.valor_ponto).max() < 1e-9


def test_matriz_de_regime_tem_o_tamanho_esperado():
    assert len(TODAS_REGIME) == 9 * 2 * 2 * 3 * 3 == 324


@pytest.mark.parametrize("over", [pytest.param(o, id=f"{i:03d}") for i, o in enumerate(random.Random(61).sample(TODAS_REGIME, 48))])
def test_amostra_da_matriz_de_regime(mercado_com_gaps, over):
    _rodar(mercado_com_gaps, over)


def test_matriz_de_regime_exercita_os_controles(mercado_com_gaps):
    """A amostra não é vazia: há saídas por tempo, e os filtros de regime cortam operações em relação ao mesmo cenário sem eles."""
    barras, sub = mercado_com_gaps
    base = dict(operacoes_por_dia=4)
    sem = len(rodar_trades(barras, Params(**base), sub))
    assert len(rodar_trades(barras, Params(**base, filtro_bb_ativo=True, filtro_bb_largura_max_pct=0.3), sub)) < sem
    assert len(rodar_trades(barras, Params(**base, filtro_inclinacao_ativo=True, filtro_inclinacao_max_x_media=0.2), sub)) < sem
    assert len(rodar_trades(barras, Params(**base, filtro_gap_ativo=True, filtro_gap_max_x_media=0.2), sub)) < sem
    com = rodar_trades(barras, Params(**base, filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.2), sub)
    ref = rodar_trades(barras, Params(**base), sub)
    assert not com[['preco_entrada', 'preco_saida']].equals(ref[['preco_entrada', 'preco_saida']])        # o descarte muda o caminho
    assert (rodar_trades(barras, Params(**base, tempo_max_min=30), sub)["saida_por"] == "tempo").sum() > 5


@pytest.mark.lento
@pytest.mark.parametrize("lote", range(4))
def test_toda_a_matriz_de_regime(mercado_com_gaps, lote):
    for over in TODAS_REGIME[lote::4]:
        _rodar(mercado_com_gaps, over)
