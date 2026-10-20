"""API ponta a ponta, com um BD sintético pequeno (rápido)."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from strategylab.main import create_app
from tests.conftest import csv_sintetico


@pytest.fixture
def cliente(tmp_path, bd_sintetico_path):
    app = create_app(estrategias_dir=tmp_path / "estrategias", bd_padrao=bd_sintetico_path,
                     frontend_dist=tmp_path / "sem_frontend")
    with TestClient(app) as c:
        yield c


def test_meta_traz_execucao_fixa_e_faixas(cliente):
    m = cliente.get("/api/meta").json()
    assert m["execucao"]["ativo"] == "WIN" and m["execucao"]["tick_pts"] == 5.0
    assert m["faixas"]["candles_gatilho"] == {"min": 1, "max": 30}
    assert m["padrao"]["book"] == "cont"


def test_lista_ja_vem_com_a_inicial_default_e_ultima(cliente):
    r = cliente.get("/api/strategies").json()
    assert [e["nome"] for e in r["estrategias"]] == ["inicial_default"]
    assert r["ultima"] == "inicial_default"
    assert r["estrategias"][0]["params"]["alvo_x_media"] == 3.0


def test_fluxo_criar_salvar_renomear_excluir(cliente):
    novo = cliente.post("/api/strategies", json={"nome": "Teste A", "params": {"stop_x_media": 2}})
    assert novo.status_code == 201 and novo.json()["params"]["stop_x_media"] == 2.0
    id_ = novo.json()["id"]

    r = cliente.put(f"/api/strategies/{id_}", json={"params": {"alvo_x_media": 4.5}})
    assert r.status_code == 200 and r.json()["params"]["alvo_x_media"] == 4.5

    r = cliente.patch(f"/api/strategies/{id_}", json={"nome": "Teste B"})
    assert r.json()["nome"] == "Teste B" and r.json()["id"] == id_

    assert cliente.get("/api/strategies").json()["ultima"] == id_
    assert cliente.delete(f"/api/strategies/{id_}").status_code == 204
    nomes = [e["nome"] for e in cliente.get("/api/strategies").json()["estrategias"]]
    assert nomes == ["inicial_default"]


def test_erros_em_portugues(cliente):
    cliente.post("/api/strategies", json={"nome": "X"})
    r = cliente.post("/api/strategies", json={"nome": "x"})
    assert r.status_code == 409 and "Já existe" in r.json()["detail"]
    r = cliente.post("/api/strategies", json={"nome": "  "})
    assert r.status_code == 422 and "Dê um nome" in r.json()["detail"]
    r = cliente.put("/api/strategies/inicial_default", json={"params": {"candles_gatilho": 99}})
    assert r.status_code == 422 and "candles_gatilho" in r.json()["detail"]
    r = cliente.put("/api/strategies/inicial_default", json={"params": {"janela_inicio": "17:30", "janela_fim": "09:00"}})
    assert r.status_code == 422 and "início da janela" in r.json()["detail"]
    assert cliente.delete("/api/strategies/fantasma").status_code == 404
    assert cliente.patch("/api/strategies/fantasma", json={"nome": "Y"}).status_code == 404


def test_dataset_padrao_e_upload_e_reset(cliente):
    d = cliente.get("/api/dataset")
    assert d.status_code == 200
    padrao = cliente.post("/api/dataset/reset").json()
    assert padrao["padrao"] is True and padrao["pregoes"] == 15 and padrao["timeframe_min"] == 1

    ok = cliente.post("/api/dataset", files={"arquivo": ("meu_bd.csv", csv_sintetico(dias=9, semente=3).encode())})
    assert ok.status_code == 200
    j = ok.json()
    assert j["padrao"] is False and j["nome"] == "meu_bd.csv" and j["pregoes"] == 9
    assert cliente.get("/api/dataset").json()["nome"] == "meu_bd.csv"

    assert cliente.post("/api/dataset/reset").json()["nome"] == "bd_padrao.csv"
    assert cliente.get("/api/dataset").json()["padrao"] is True


def test_upload_invalido_nao_troca_o_bd_ativo(cliente):
    cliente.post("/api/dataset/reset")
    r = cliente.post("/api/dataset", files={"arquivo": ("ruim.csv", b"A;B\n1;2\n")})
    assert r.status_code == 422 and "Cabeçalho" in r.json()["detail"]
    r = cliente.post("/api/dataset", files={"arquivo": ("vazio.csv", b"")})
    assert r.status_code == 422
    assert cliente.get("/api/dataset").json()["nome"] == "bd_padrao.csv"


def test_upload_com_linhas_vazias_no_fim_funciona(cliente):
    r = cliente.post("/api/dataset", files={"arquivo": ("vazias.csv", csv_sintetico(dias=8, extra_vazias=40).encode())})
    assert r.status_code == 200 and r.json()["pregoes"] == 8


def test_upload_de_5_minutos_avisa(cliente):
    r = cliente.post("/api/dataset", files={"arquivo": ("5min.csv", csv_sintetico(dias=8, base_min=5).encode())})
    assert r.status_code == 200
    assert any("5 min" in a for a in r.json()["avisos"])


def test_backtest_formato_cache_e_dia(cliente):
    corpo = {"params": {"operacoes_por_dia": 3, "book": "ambas"}}
    r1 = cliente.post("/api/backtest", json=corpo)
    assert r1.status_code == 200
    j = r1.json()
    assert j["em_cache"] is False
    assert {"resumo", "diario", "mensal", "operacoes", "bd", "params", "tempo_ms"} <= set(j)
    assert j["params"]["operacoes_por_dia"] == 3
    res = j["resumo"]
    assert res["operacoes"] == len(j["operacoes"]) == sum(d["operacoes"] for d in j["diario"])
    assert res["total_rs"] == pytest.approx(sum(d["rs"] for d in j["diario"]))
    assert j["diario"][-1]["acumulado"] == pytest.approx(res["total_rs"])
    # mensal: todo mês que o BD cobre aparece; mês sem operação vem zerado e marcado, sem mudar o total
    bd = cliente.get("/api/dataset").json()
    meses_bd = [str(m) for m in pd.period_range(bd["inicio"], bd["fim"], freq="M")]
    assert [m["mes"] for m in j["mensal"]] == meses_bd
    assert sum(m["rs"] for m in j["mensal"]) == pytest.approx(res["total_rs"])
    for m in j["mensal"]:
        assert m["operado"] == (m["dias"] > 0)
        if not m["operado"]:
            assert m["rs"] == 0 and m["pts"] == 0 and m["dias_positivos"] == 0

    r2 = cliente.post("/api/backtest", json=corpo).json()
    assert r2["em_cache"] is True and r2["resumo"] == res

    if j["operacoes"]:
        dia = j["operacoes"][0]["data"]
        b = cliente.get(f"/api/dia/{dia}").json()
        assert b["data"] == dia and b["barras"][0]["t"] == "09:00"
        assert {"t", "o", "h", "l", "c"} == set(b["barras"][0])
    assert cliente.get("/api/dia/2000-01-01").status_code == 404
    assert cliente.get("/api/dia/ontem").status_code == 422


def test_backtest_invalido_devolve_mensagem(cliente):
    r = cliente.post("/api/backtest", json={"params": {"stop_x_media": 0}})
    assert r.status_code == 422 and "stop_x_media" in r.json()["detail"]


def test_cache_respeita_o_bd(cliente):
    corpo = {"params": {}}
    a = cliente.post("/api/backtest", json=corpo).json()
    cliente.post("/api/dataset", files={"arquivo": ("outro.csv", csv_sintetico(dias=10, semente=99).encode())})
    b = cliente.post("/api/backtest", json=corpo).json()
    assert b["em_cache"] is False and b["bd"]["nome"] == "outro.csv"
    assert a["bd"]["id"] != b["bd"]["id"]


def test_filtro_afastamento_pela_api_registra_o_candle_de_referencia(cliente):
    sem = cliente.post("/api/backtest", json={"params": {"operacoes_por_dia": 3, "book": "ambas"}}).json()
    com = cliente.post("/api/backtest", json={"params": {
        "operacoes_por_dia": 3, "book": "ambas", "filtro_afast_mm_ativo": True, "filtro_afast_mm_x_media": 0.2}}).json()
    assert all(o["ref"] is None for o in sem["operacoes"])                       # desligado: nada registrado
    assert com["resumo"]["operacoes"] <= sem["resumo"]["operacoes"]
    assert com["params"]["filtro_afast_mm_ativo"] is True
    for o in com["operacoes"]:
        ref = o["ref"]
        assert ref and ref["afast_pts"] > 0 and ref["afast_x"] >= 0.2 - 1e-9     # passou no limite configurado
        assert ref["barra"] < o["entrada_barra"] or o["entrada_barra"] < "09:00"  # candle de referência é ANTERIOR à barra da entrada


def test_cache_ignora_bollinger_e_mm_sem_filtro_mas_nao_o_filtro(cliente):
    corpo = {"params": {}}
    assert cliente.post("/api/backtest", json=corpo).json()["em_cache"] is False
    assert cliente.post("/api/backtest", json={"params": {"bb_periodo": 30, "bb_desvio": 3.0}}).json()["em_cache"] is True
    assert cliente.post("/api/backtest", json={"params": {"mm_periodo": 40}}).json()["em_cache"] is True
    r = cliente.post("/api/backtest", json={"params": {"bb_periodo": 30, "filtro_afast_mm_ativo": True}}).json()
    assert r["em_cache"] is False and r["params"]["bb_periodo"] == 30                 # devolve o que foi pedido
    assert cliente.post("/api/backtest", json={"params": {"bb_periodo": 31, "filtro_afast_mm_ativo": True}}).json()["em_cache"] is True
    assert cliente.post("/api/backtest", json={"params": {"mm_periodo": 40, "filtro_afast_mm_ativo": True}}).json()["em_cache"] is False


def test_dia_devolve_indicadores_no_fechamento_de_cada_barra(cliente):
    ops = cliente.post("/api/backtest", json={"params": {"operacoes_por_dia": 3, "book": "ambas"}}).json()["operacoes"]
    d = ops[-1]["data"]
    sem = cliente.get(f"/api/dia/{d}").json()["barras"]
    assert "mm" not in sem[0]
    r = cliente.get(f"/api/dia/{d}", params={"mm": 15, "bb": 15, "k": 2.0})
    assert r.status_code == 200
    barras = r.json()["barras"]
    assert {"mm", "bbm", "bbs", "bbi"} <= set(barras[0])
    valores = [b for b in barras if b["mm"] is not None]
    assert valores, "a partir do 3º pregão da série a EMA(15) de 10 min já está formada"
    for b in valores:
        assert b["bbi"] < b["bbm"] < b["bbs"] and b["bbm"] == pytest.approx(b["mm"])     # mesma EMA(15) no centro da banda
    # a EMA da barra t não pode depender do futuro: a mesma barra sai igual consultando outro período de Bollinger
    outro = cliente.get(f"/api/dia/{d}", params={"mm": 15, "bb": 30, "k": 3.0}).json()["barras"]
    assert [b["mm"] for b in outro] == [b["mm"] for b in barras]
    assert cliente.get(f"/api/dia/{d}", params={"mm": 1, "bb": 15, "k": 2.0}).status_code == 422


# ------------------------------------------------------------------ Etapa 3: modo de entrada e saída na MM
def test_meta_traz_os_padroes_da_etapa_3(cliente):
    padrao = cliente.get("/api/meta").json()["padrao"]
    assert padrao["modo_entrada"] == "padrao" and padrao["sair_ao_tocar_mm"] is False


def test_backtest_pela_api_com_proximo_candle_e_saida_na_mm(cliente):
    base = {"operacoes_por_dia": 3, "book": "ambas"}
    pad = cliente.post("/api/backtest", json={"params": base}).json()
    pro = cliente.post("/api/backtest", json={"params": {**base, "modo_entrada": "proximo_candle"}}).json()
    mm = cliente.post("/api/backtest", json={"params": {**base, "sair_ao_tocar_mm": True}}).json()
    assert pro["params"]["modo_entrada"] == "proximo_candle" and mm["params"]["sair_ao_tocar_mm"] is True
    assert pad["em_cache"] is False and pro["em_cache"] is False and mm["em_cache"] is False
    assert pro["resumo"]["total_rs"] != pad["resumo"]["total_rs"]
    assert pro["operacoes"] and all(o["entrada"][-1] == "0" for o in pro["operacoes"])      # sempre na abertura de uma barra de 10 min
    assert {o["saida_por"] for o in pad["operacoes"]} <= {"stop", "alvo", "zeragem", "fim_dados"}
    assert "mm" in {o["saida_por"] for o in mm["operacoes"]}


def test_cache_distingue_o_modo_de_entrada_e_a_saida_na_mm(cliente):
    cliente.post("/api/backtest", json={"params": {}})
    assert cliente.post("/api/backtest", json={"params": {"mm_periodo": 40}}).json()["em_cache"] is True      # nada mudou para o motor
    assert cliente.post("/api/backtest", json={"params": {"modo_entrada": "proximo_candle"}}).json()["em_cache"] is False
    assert cliente.post("/api/backtest", json={"params": {"modo_entrada": "proximo_candle", "bb_periodo": 33}}).json()["em_cache"] is True
    assert cliente.post("/api/backtest", json={"params": {"sair_ao_tocar_mm": True}}).json()["em_cache"] is False
    assert cliente.post("/api/backtest", json={"params": {"sair_ao_tocar_mm": True, "mm_periodo": 40}}).json()["em_cache"] is False


def test_modo_de_entrada_invalido_e_recusado_em_portugues(cliente):
    r = cliente.post("/api/backtest", json={"params": {"modo_entrada": "abertura"}})
    assert r.status_code == 422


def test_estrategia_salva_com_os_controles_novos_volta_igual(cliente):
    novo = cliente.post("/api/strategies", json={"nome": "Etapa 3", "params": {"modo_entrada": "proximo_candle", "sair_ao_tocar_mm": True}})
    assert novo.status_code == 201
    lida = [e for e in cliente.get("/api/strategies").json()["estrategias"] if e["id"] == novo.json()["id"]][0]
    assert lida["params"]["modo_entrada"] == "proximo_candle" and lida["params"]["sair_ao_tocar_mm"] is True


def test_backtest_pela_api_com_rastrear_mm(cliente):
    base = {"operacoes_por_dia": 3, "book": "ambas"}
    livre = cliente.post("/api/backtest", json={"params": base}).json()
    rast = cliente.post("/api/backtest", json={"params": {**base, "rastrear_mm": True}}).json()
    assert rast["params"]["rastrear_mm"] is True and rast["em_cache"] is False
    assert 0 < len(rast["operacoes"]) < len(livre["operacoes"])                 # o filtro corta entradas
    assert cliente.get("/api/meta").json()["padrao"]["rastrear_mm"] is False


def test_backtest_pela_api_com_reversoes(cliente):
    base = {"operacoes_por_dia": 2, "book": "ambas"}
    sem = cliente.post("/api/backtest", json={"params": base}).json()
    com = cliente.post("/api/backtest", json={"params": {**base, "reversoes": 2, "rev_stop_x_media": 0.5, "rev_alvo_x_media": 2.0}}).json()
    assert com["params"]["reversoes"] == 2 and com["em_cache"] is False
    assert len(com["operacoes"]) > len(sem["operacoes"])                       # as pernas revertidas viram operações
    assert max(o["reversao"] for o in com["operacoes"]) >= 1 and {o["reversao"] for o in sem["operacoes"]} == {0}
    # o stop/alvo da reversão só entram na conta quando há reversões
    assert cliente.post("/api/backtest", json={"params": {**base, "rev_stop_x_media": 3.0}}).json()["em_cache"] is True
    assert cliente.post("/api/backtest", json={"params": {**base, "reversoes": 6}}).status_code == 422
    assert cliente.get("/api/meta").json()["faixas"]["reversoes"] == {"min": 0, "max": 5}


def test_backtest_pela_api_com_cauda_e_filtros_de_regime(cliente):
    base = {"operacoes_por_dia": 3, "book": "ambas"}
    livre = cliente.post("/api/backtest", json={"params": base}).json()
    tempo = cliente.post("/api/backtest", json={"params": {**base, "tempo_max_min": 30}}).json()
    assert "tempo" in {o["saida_por"] for o in tempo["operacoes"]} and "tempo" not in {o["saida_por"] for o in livre["operacoes"]}
    bb = cliente.post("/api/backtest", json={"params": {**base, "filtro_bb_ativo": True, "filtro_bb_largura_max_pct": 0.3}}).json()
    assert 0 < len(bb["operacoes"]) < len(livre["operacoes"])
    assert cliente.post("/api/backtest", json={"params": {**base, "filtro_gap_max_x_media": 3.0}}).json()["em_cache"] is True       # filtro desligado: mesma chave
    assert cliente.post("/api/backtest", json={"params": {"filtro_bb_largura_max_pct": 0.0}}).status_code == 422
    meta = cliente.get("/api/meta").json()
    assert meta["padrao"]["tempo_max_min"] == 0 and meta["padrao"]["filtro_bb_ativo"] is False
