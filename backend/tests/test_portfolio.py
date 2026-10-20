"""Resultado conjunto ("Correlacionar"): soma de backtests independentes, pregão a pregão.

O conjunto NÃO reimplementa regra de trade: os componentes vêm de `executar`. Aqui se prova a conta da soma, o drawdown do
conjunto (recalculado de forma independente), a correlação e a memória da seleção. Um componente sozinho tem de ser igual ao
`executar`; no BD real, dois cenários das âncoras somam as âncoras.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from strategylab.engine import data
from strategylab.engine.metrics import resumo_diario, trades_para_df
from strategylab.engine.params import Params
from strategylab.engine.portfolio import combinar, pearson
from strategylab.engine.runner import executar, meses_do_bd, preparar_mercado, resumo_json
from strategylab.main import create_app
from tests.conftest import csv_sintetico

A = dict(operacoes_por_dia=3, book="ambas")
B = dict(operacoes_por_dia=2, book="cont", stop_x_media=0.5, alvo_x_media=1.5)
C = dict(operacoes_por_dia=4, book="ambas", reversoes=1, rev_stop_x_media=0.7, rev_alvo_x_media=2.0, candles_gatilho=1)


@pytest.fixture(scope="module")
def mundo():
    raw, _ = data.carregar_csv(csv_sintetico(dias=30, semente=21).encode())
    barras, sub = data.preparar_barras(raw, 10)
    mercado = preparar_mercado(barras, sub)
    res = {nome: executar(barras, Params(**over), sub, mercado) for nome, over in (("A", A), ("B", B), ("C", C))}
    return {"mercado": mercado, "res": res, "datas": list(mercado.feat), "meses": meses_do_bd(mercado)}


def juntar(mundo, *nomes):
    comps = [{"nome": n, "res": mundo["res"][n]} for n in nomes]
    return combinar(comps, mundo["datas"], mundo["meses"])


def sem(lista, *campos):
    return [{k: v for k, v in x.items() if k not in campos} for x in lista]


def test_os_componentes_de_teste_operam(mundo):
    assert all(r["resumo"]["operacoes"] > 0 for r in mundo["res"].values())
    assert mundo["res"]["A"]["resumo"]["total_rs"] != mundo["res"]["B"]["resumo"]["total_rs"]


def test_um_componente_sozinho_e_identico_ao_backtest(mundo):
    c = juntar(mundo, "A")
    r = mundo["res"]["A"]
    assert c["resumo"] == r["resumo"]
    assert sem(c["diario"], "rs_por") == r["diario"]
    assert sem(c["mensal"], "rs_por") == r["mensal"]
    assert sem(c["operacoes"], "estrategia") == sorted(r["operacoes"], key=lambda o: (o["data"], o["entrada"]))
    assert c["estrategias"][0]["correlacao_principal"] is None
    assert c["diversificacao"]["dd_conjunto"] == c["diversificacao"]["soma_dd_isolados"] == r["resumo"]["drawdown"]["rs"]


def test_dois_componentes_somam_totais_operacoes_e_dias(mundo):
    c = juntar(mundo, "A", "B")
    a, b = mundo["res"]["A"]["resumo"], mundo["res"]["B"]["resumo"]
    assert c["resumo"]["total_rs"] == pytest.approx(a["total_rs"] + b["total_rs"])
    assert c["resumo"]["total_pts"] == pytest.approx(a["total_pts"] + b["total_pts"])
    assert c["resumo"]["operacoes"] == a["operacoes"] + b["operacoes"] == len(c["operacoes"])
    assert c["resumo"]["ganhos"] == a["ganhos"] + b["ganhos"] and c["resumo"]["perdas"] == a["perdas"] + b["perdas"]
    assert c["diario"][-1]["acumulado"] == pytest.approx(c["resumo"]["total_rs"])
    datas = {d["data"] for d in mundo["res"]["A"]["diario"]} | {d["data"] for d in mundo["res"]["B"]["diario"]}
    assert [d["data"] for d in c["diario"]] == sorted(datas)                       # união dos pregões operados


def test_rs_por_soma_o_resultado_do_dia_e_do_mes(mundo):
    c = juntar(mundo, "A", "B", "C")
    for d in c["diario"]:
        assert len(d["rs_por"]) == 3 and sum(d["rs_por"]) == pytest.approx(d["rs"])
    for m in c["mensal"]:
        assert len(m["rs_por"]) == 3 and sum(m["rs_por"]) == pytest.approx(m["rs"])
    por_dia = {i: {d["data"]: d["rs"] for d in mundo["res"][n]["diario"]} for i, n in enumerate("ABC")}
    for d in c["diario"]:
        assert d["rs_por"] == pytest.approx([por_dia[i].get(d["data"], 0.0) for i in range(3)])


def test_drawdown_do_conjunto_confere_com_conta_independente(mundo):
    c = juntar(mundo, "A", "B", "C")
    serie = pd.Series({d["data"]: d["rs"] for d in c["diario"]}).sort_index().cumsum()
    esperado = float((serie - serie.cummax()).min())
    assert c["resumo"]["drawdown"]["rs"] == pytest.approx(esperado)
    assert c["diversificacao"]["dd_conjunto"] == pytest.approx(esperado)
    soma = sum(mundo["res"][n]["resumo"]["drawdown"]["rs"] for n in "ABC")
    assert c["diversificacao"]["soma_dd_isolados"] == pytest.approx(soma)


def test_mes_operado_se_algum_componente_operou_e_todos_os_meses_do_bd_aparecem(mundo):
    c = juntar(mundo, "A", "B")
    assert [m["mes"] for m in c["mensal"]] == mundo["meses"]
    for m in c["mensal"]:
        assert m["operado"] == (m["dias"] > 0)
    assert sum(m["rs"] for m in c["mensal"]) == pytest.approx(c["resumo"]["total_rs"])


def test_ordem_das_nao_principais_nao_muda_os_totais(mundo):
    x, y = juntar(mundo, "A", "B", "C"), juntar(mundo, "A", "C", "B")
    assert x["resumo"] == y["resumo"]
    assert [d["rs"] for d in x["diario"]] == [d["rs"] for d in y["diario"]]
    for dx, dy in zip(x["diario"], y["diario"]):
        assert dx["rs_por"][0] == dy["rs_por"][0] and dx["rs_por"][1:] == dy["rs_por"][:0:-1]


def test_correlacao_com_a_principal(mundo):
    mesma = combinar([{"nome": "A", "res": mundo["res"]["A"]}, {"nome": "A2", "res": copy.deepcopy(mundo["res"]["A"])}],
                     mundo["datas"], mundo["meses"])
    assert mesma["estrategias"][1]["correlacao_principal"] == pytest.approx(1.0)
    c = juntar(mundo, "A", "B", "C")
    for e in c["estrategias"][1:]:
        assert e["correlacao_principal"] is None or -1.0 <= e["correlacao_principal"] <= 1.0
    # independente: Pearson do R$ diário sobre todos os pregões do BD, zero onde não operou
    cal = sorted(set(mundo["datas"]))
    a = pd.Series({pd.Timestamp(d["data"]).date(): d["rs"] for d in mundo["res"]["A"]["diario"]}).reindex(cal).fillna(0.0)
    b = pd.Series({pd.Timestamp(d["data"]).date(): d["rs"] for d in mundo["res"]["B"]["diario"]}).reindex(cal).fillna(0.0)
    assert c["estrategias"][1]["correlacao_principal"] == pytest.approx(float(np.corrcoef(a, b)[0, 1]))


def test_pearson_casos_de_borda():
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert pearson([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert pearson([1, 2, 3], [5, 5, 5]) is None          # série constante: indefinida
    assert pearson([], []) is None and pearson([1], [1]) is None
    assert pearson([1, 2, 3], [4, 9, 2]) == pytest.approx(pearson([4, 9, 2], [1, 2, 3]))      # simétrica


def test_componente_sem_nenhuma_operacao_nao_quebra_e_tem_correlacao_nula(mundo):
    vazio = copy.deepcopy(mundo["res"]["B"])
    vazio.update(diario=[], operacoes=[], resumo=resumo_json(resumo_diario(trades_para_df([]))))
    vazio["mensal"] = [{**m, "rs": 0.0, "pts": 0.0, "dias": 0, "dias_positivos": 0, "operado": False} for m in vazio["mensal"]]
    c = combinar([{"nome": "A", "res": mundo["res"]["A"]}, {"nome": "vazia", "res": vazio}], mundo["datas"], mundo["meses"])
    assert c["estrategias"][1]["correlacao_principal"] is None
    assert c["resumo"]["total_rs"] == pytest.approx(mundo["res"]["A"]["resumo"]["total_rs"])
    assert all(d["rs_por"][1] == 0.0 for d in c["diario"])


def test_combinar_nao_altera_os_resultados_de_entrada(mundo):
    antes = copy.deepcopy(mundo["res"]["A"])
    juntar(mundo, "A", "B")
    assert mundo["res"]["A"] == antes                      # o cache da API guarda esses dicionários: nunca podem ser mutados


# ------------------------------------------------------------------ API
@pytest.fixture
def cliente(tmp_path, bd_sintetico_path):
    app = create_app(estrategias_dir=tmp_path / "estrategias", bd_padrao=bd_sintetico_path, frontend_dist=tmp_path / "sem_frontend")
    with TestClient(app) as c:
        yield c


def comp(nome, **over):
    return {"nome": nome, "params": over}


def test_api_portfolio_formato_e_soma(cliente):
    corpo = {"componentes": [comp("A", **A), comp("B", **B)]}
    r = cliente.post("/api/portfolio", json=corpo)
    assert r.status_code == 200
    j = r.json()
    assert {"resumo", "diario", "mensal", "operacoes", "estrategias", "diversificacao", "bd", "params", "em_cache"} <= set(j)
    um = cliente.post("/api/backtest", json={"params": A}).json()
    dois = cliente.post("/api/backtest", json={"params": B}).json()
    assert j["resumo"]["total_rs"] == pytest.approx(um["resumo"]["total_rs"] + dois["resumo"]["total_rs"])
    assert [e["nome"] for e in j["estrategias"]] == ["A", "B"]
    assert {o["estrategia"] for o in j["operacoes"]} <= {0, 1}
    assert j["params"]["operacoes_por_dia"] == 3                       # params da principal
    assert cliente.post("/api/portfolio", json=corpo).json()["em_cache"] is True


@pytest.mark.parametrize("n", [0, 13])
def test_api_portfolio_recusa_quantidade_fora_do_limite(cliente, n):
    r = cliente.post("/api/portfolio", json={"componentes": [comp(f"E{i}") for i in range(n)]})
    assert r.status_code == 422


def test_api_portfolio_recusa_parametro_invalido(cliente):
    r = cliente.post("/api/portfolio", json={"componentes": [comp("A"), comp("ruim", stop_x_media=-1)]})
    assert r.status_code == 422


def test_meta_informa_a_capacidade_de_correlacao(cliente):
    assert cliente.get("/api/meta").json()["capacidades"]["correlacao"] is True


# ------------------------------------------------------------------ memória da seleção
def criar(cliente, nome):
    return cliente.post("/api/strategies", json={"nome": nome}).json()["id"]


def test_correlacionar_persiste_em_ordem_e_filtra_ids_invalidos(cliente):
    a, b, c = criar(cliente, "Alfa"), criar(cliente, "Beta"), criar(cliente, "Gama")
    r = cliente.put("/api/estado/correlacionar", json={"id": a, "ids": [c, b, a, "nao_existe", c]})
    assert r.status_code == 200 and r.json()["ids"] == [c, b]            # sem a própria, sem inexistentes, sem repetidos, ordem mantida
    assert cliente.get("/api/strategies").json()["correlacionar"] == {a: [c, b]}


def test_lista_vazia_limpa_a_memoria(cliente):
    a, b = criar(cliente, "Alfa"), criar(cliente, "Beta")
    cliente.put("/api/estado/correlacionar", json={"id": a, "ids": [b]})
    cliente.put("/api/estado/correlacionar", json={"id": a, "ids": []})
    assert cliente.get("/api/strategies").json()["correlacionar"] == {}   # desmarcou tudo: na próxima vez vem sem correlacionadas


def test_cada_principal_tem_a_sua_lista(cliente):
    a, b, c = criar(cliente, "Alfa"), criar(cliente, "Beta"), criar(cliente, "Gama")
    cliente.put("/api/estado/correlacionar", json={"id": a, "ids": [b]})
    cliente.put("/api/estado/correlacionar", json={"id": b, "ids": [a, c]})
    assert cliente.get("/api/strategies").json()["correlacionar"] == {a: [b], b: [a, c]}


def test_excluir_remove_a_estrategia_de_todas_as_listas_e_a_propria_lista(cliente):
    a, b, c = criar(cliente, "Alfa"), criar(cliente, "Beta"), criar(cliente, "Gama")
    cliente.put("/api/estado/correlacionar", json={"id": a, "ids": [b, c]})
    cliente.put("/api/estado/correlacionar", json={"id": b, "ids": [c]})
    assert cliente.delete(f"/api/strategies/{c}").status_code == 204
    assert cliente.get("/api/strategies").json()["correlacionar"] == {a: [b]}
    assert cliente.delete(f"/api/strategies/{a}").status_code == 204
    assert cliente.get("/api/strategies").json()["correlacionar"] == {}


def test_correlacionar_de_principal_inexistente_da_404(cliente):
    assert cliente.put("/api/estado/correlacionar", json={"id": "fantasma", "ids": []}).status_code == 404


# ------------------------------------------------------------------ BD real (âncoras)
@pytest.mark.lento
def test_conjunto_de_dois_cenarios_ancora_soma_as_ancoras(barras_reais):
    _, barras, sub = barras_reais
    mercado = preparar_mercado(barras, sub)
    base = executar(barras, Params(), sub, mercado)                                        # âncora: 1.054 ops, R$ 7.391
    ambas = executar(barras, Params(book="ambas"), sub, mercado)                           # âncora: 1.073 ops, R$ -2.071
    c = combinar([{"nome": "base", "res": base}, {"nome": "ambas", "res": ambas}], list(mercado.feat), meses_do_bd(mercado))
    assert base["resumo"]["total_rs"] == 7391.0 and ambas["resumo"]["total_rs"] == -2071.0
    assert c["resumo"]["total_rs"] == pytest.approx(7391.0 - 2071.0)
    assert c["resumo"]["operacoes"] == 1054 + 1073 == len(c["operacoes"])
    assert sum(m["rs"] for m in c["mensal"]) == pytest.approx(5320.0)
    assert [m["mes"] for m in c["mensal"]] == meses_do_bd(mercado)
    assert max(d["data"] for d in c["diario"]) <= "2025-12-31"                              # hold-out: só o BD do projeto
