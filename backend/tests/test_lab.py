"""Laboratório de combinações: expansão da grade, métricas, execução paralela e, principalmente, FIDELIDADE ao motor do app.

O laboratório não tem motor próprio: tudo o que ele produz precisa ser idêntico ao que o app (`executar`/`rodar_trades`) produz
para os mesmos parâmetros. Os testes abaixo cobrem as pontes onde isso poderia se perder: o BD preparado (`Mercado`), o
cache em disco/processos e a deduplicação por `chave_motor`.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from strategylab.engine import data
from strategylab.engine.ghost import run_day
from strategylab.engine.params import Params
from strategylab.engine.runner import executar, montar_cfg, preparar_mercado, rodar_trades
from strategylab.lab import cli, executor, grade as g
from strategylab.lab.metricas import metricas
from tests.conftest import BD_PADRAO, csv_sintetico


# ------------------------------------------------------------------ expansão da grade
def test_produto_de_eixos_e_variantes():
    gr = g.expandir({"eixos": {"reversoes": [0, 1, 2], "book": ["cont", "ambas"]}, "variantes": [{}, {"sair_ao_tocar_mm": True}]})
    assert len(gr.combinacoes) == 3 * 2 * 2
    assert {c.params["reversoes"] for c in gr.combinacoes} == {0, 1, 2}
    assert sum(c.params["sair_ao_tocar_mm"] for c in gr.combinacoes) == 6
    assert [c.id for c in gr.combinacoes] == list(range(12))


def test_faixa_com_passo_sem_deriva_de_ponto_flutuante():
    assert g.valores_do_eixo("stop_x_media", {"de": 0.1, "ate": 0.5, "passo": 0.1}) == [0.1, 0.2, 0.3, 0.4, 0.5]
    assert g.valores_do_eixo("reversoes", {"de": 0, "ate": 5, "passo": 1}) == [0, 1, 2, 3, 4, 5]


def test_campo_desconhecido_e_erro_e_nao_silencio():
    with pytest.raises(g.GradeErro, match="reversao_x"):
        g.expandir({"eixos": {"reversao_x": [1, 2]}})
    with pytest.raises(g.GradeErro, match="desconhecid"):
        g.expandir({"eixos": {"reversoes": [1]}, "eixoss": {}})


def test_grade_sem_eixos_nem_variantes_e_recusada():
    with pytest.raises(g.GradeErro):
        g.expandir({"nome": "vazia"})


def test_campo_em_eixo_e_em_variante_e_ambiguo():
    with pytest.raises(g.GradeErro, match="reversoes"):
        g.expandir({"eixos": {"reversoes": [1]}, "variantes": [{"reversoes": 2}]})


def test_combinacao_invalida_e_marcada_e_nao_derruba_a_grade():
    gr = g.expandir({"base": {"janela_inicio": "09:00"}, "eixos": {"ultima_entrada": ["16:00", "08:00"], "reversoes": [0, 9]}})
    erros = [c.erro for c in gr.combinacoes if c.erro]
    assert len(erros) == 3                                              # 08:00 (antes do início) e reversoes 9 (> 5)
    assert any("última entrada" in e for e in erros) and any("reversoes" in e for e in erros)


def test_base_por_estrategia_salva_id_ou_nome(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps({"id": "minha_estr", "name": "Minha Estratégia", "params": {"stop_x_media": 2.5}}), encoding="utf-8")
    for ref in ("minha_estr", "minha estratégia"):
        gr = g.expandir({"base": ref, "eixos": {"reversoes": [0, 1]}}, tmp_path)
        assert all(c.params["stop_x_media"] == 2.5 for c in gr.combinacoes)
    with pytest.raises(g.GradeErro, match="nenhuma estratégia"):
        g.expandir({"base": "nao_existe", "eixos": {"reversoes": [0]}}, tmp_path)


def test_chave_do_motor_agrupa_combinacoes_equivalentes():
    gr = g.expandir({"eixos": {"bb_periodo": [10, 20, 30], "reversoes": [0, 1]}})        # Bollinger não entra no resultado
    assert len({c.chave for c in gr.combinacoes}) == 2


# ------------------------------------------------------------------ métricas = as do app
@pytest.fixture(scope="module")
def mercado_sintetico():
    raw, _ = data.carregar_csv(csv_sintetico(dias=40, semente=11).encode())
    barras, sub = data.preparar_barras(raw, 10)
    return raw, barras, sub, preparar_mercado(barras, sub)


CASOS = {
    "base": {},
    "tudo": dict(modo_entrada="proximo_candle", sair_ao_tocar_mm=True, rastrear_mm=True, filtro_afast_mm_ativo=True,
                 filtro_afast_mm_x_media=0.1, reversoes=2, rev_stop_x_media=0.7, operacoes_por_dia=3, book="ambas"),
    "reversoes": dict(reversoes=3, rev_alvo_x_media=2.0, operacoes_por_dia=2),
    "mm": dict(sair_ao_tocar_mm=True, mm_periodo=9, operacoes_por_dia=4, parar_apos_losses=2),
}


@pytest.mark.parametrize("nome", list(CASOS))
def test_metricas_do_laboratorio_iguais_as_do_app(mercado_sintetico, nome):
    _, barras, sub, mercado = mercado_sintetico
    p = Params(**CASOS[nome])
    app = executar(barras, p, sub, mercado)["resumo"]
    m = metricas(rodar_trades(None, p, sub, mercado), "2024-03-20")
    assert m["operacoes"] == app["operacoes"] and m["total_rs"] == app["total_rs"] and m["total_pts"] == app["total_pts"]
    assert m["dd_rs"] == app["drawdown"]["rs"] and m["win_rate"] == app["win_rate"]
    assert m["is_rs"] + m["oos_rs"] == pytest.approx(m["total_rs"]) and sum(m["por_ano"].values()) == pytest.approx(m["total_rs"])
    if m["dd_rs"] < 0:
        assert m["ret_dd"] == pytest.approx(m["total_rs"] / abs(m["dd_rs"]))


def test_metricas_sem_operacoes():
    cols = ["data", "ciclo", "lado", "entrada_ts", "preco_entrada", "saida_ts", "preco_saida", "contratos", "pts", "rs", "desfecho",
            "saida_por", "reversao", "ref_barra", "ref_mm", "ref_afast", "media_op"]
    m = metricas(pd.DataFrame(columns=cols), "2025-01-01")
    assert m["operacoes"] == 0 and m["total_rs"] == 0 and np.isnan(m["ret_dd"])


# ------------------------------------------------------------------ fidelidade: BD preparado == caminho por pregão (DataFrame)
@pytest.mark.parametrize("nome", list(CASOS))
def test_mercado_preparado_identico_ao_caminho_por_dataframe(mercado_sintetico, nome):
    """O caminho por DataFrame (`run_day` em cada pregão, com a coluna `mm`) e o preparado têm de dar os mesmos trades."""
    from strategylab.engine.indicators import ema
    from strategylab.engine.metrics import trades_para_df

    _, barras, sub, mercado = mercado_sintetico
    p = Params(**CASOS[nome])
    cfg = montar_cfg(p, sub)
    b = barras.assign(mm=ema(barras["close"].to_numpy(float), p.mm_periodo))
    antigo = trades_para_df([t for _, dia in b.groupby("date", sort=True) for t in run_day(dia, cfg)])
    novo = rodar_trades(None, p, sub, mercado)
    assert len(antigo) == len(novo) > 5
    pd.testing.assert_frame_equal(antigo, novo)


def test_mercado_e_reaproveitado_sem_vazar_estado_entre_execucoes(mercado_sintetico):
    """Rodar A, B e A de novo no mesmo `Mercado` (com a memória de media_operacao e as EMAs em cache) dá o mesmo A."""
    _, barras, sub, mercado = mercado_sintetico
    pa = Params(**CASOS["tudo"])
    pb = Params(candles_media=3, candles_gatilho=8, mm_periodo=40, sair_ao_tocar_mm=True, operacoes_por_dia=3)
    a = rodar_trades(None, pa, sub, mercado)
    b = rodar_trades(None, pb, sub, mercado)
    a2 = rodar_trades(None, pa, sub, mercado)
    pd.testing.assert_frame_equal(a, a2)
    pd.testing.assert_frame_equal(a, rodar_trades(barras, pa, sub))        # contra um Mercado novo (sem nada em cache)
    pd.testing.assert_frame_equal(b, rodar_trades(barras, pb, sub))        # a execução B (outra janela e outra MM) também


# ------------------------------------------------------------------ cache em disco, processos e verificação
@pytest.fixture(scope="module")
def csv_lab(tmp_path_factory):
    arq = tmp_path_factory.mktemp("lab") / "bd.csv"
    arq.write_text(csv_sintetico(dias=30, semente=5), encoding="utf-8")
    return arq


def test_cache_do_bd_em_disco_e_invalidado_quando_o_motor_muda(csv_lab, tmp_path, monkeypatch):
    a = executor.carregar_bd(csv_lab, tmp_path)
    b = executor.carregar_bd(csv_lab, tmp_path)
    assert not a.do_cache and b.do_cache and a.id == b.id
    monkeypatch.setattr(executor, "hash_do_motor", lambda: "motor_novo")
    c = executor.carregar_bd(csv_lab, tmp_path)
    assert not c.do_cache
    assert len(list(tmp_path.glob("*.pkl"))) == 2                       # só o cache atual fica


GRADE_PEQUENA = {"eixos": {"stop_x_media": [0.5, 1.0], "reversoes": [0, 1, 2]},
                 "variantes": [{}, {"sair_ao_tocar_mm": True, "modo_entrada": "proximo_candle"}]}


def _unicos(gr):
    vistos = {}
    for c in gr.combinacoes:
        vistos.setdefault(c.chave, c)
    return [(c.id, c.params) for c in vistos.values()]


def test_paralelo_igual_ao_serial_e_igual_ao_app(csv_lab, tmp_path):
    bd = executor.carregar_bd(csv_lab, tmp_path)
    lista = _unicos(g.expandir(GRADE_PEQUENA))
    serial = executor.executar_grade(lista, bd, "2024-03-20", workers=1)
    paralelo = executor.executar_grade(lista, bd, "2024-03-20", workers=2)
    assert serial.keys() == paralelo.keys() == {i for i, _ in lista}
    for i in serial:
        a, b = dict(serial[i]), dict(paralelo[i])
        a.pop("tempo_ms"), b.pop("tempo_ms")
        assert a == b
    assert executor.verificar(bd, lista, paralelo, "2024-03-20") == []       # recalculado pelo caminho do app


def test_verificacao_detecta_resultado_adulterado(csv_lab, tmp_path):
    bd = executor.carregar_bd(csv_lab, tmp_path)
    lista = _unicos(g.expandir(GRADE_PEQUENA))[:3]
    res = executor.executar_grade(lista, bd, None, workers=1)
    i = lista[0][0]
    res[i] = {**res[i], "total_rs": res[i]["total_rs"] + 0.2}
    erros = executor.verificar(bd, lista, res, None)
    assert erros and "total_rs" in erros[0]


def test_combinacao_com_erro_nao_derruba_as_outras(csv_lab, tmp_path):
    bd = executor.carregar_bd(csv_lab, tmp_path)
    res = executor.executar_grade([(0, {"stop_x_media": 99.0}), (1, Params().model_dump())], bd, None, workers=1)
    assert res[0]["status"] == "erro" and res[1]["status"] == "ok"


# ------------------------------------------------------------------ linha de comando de ponta a ponta
def test_cli_ponta_a_ponta(csv_lab, tmp_path, capsys):
    spec = {"nome": "e2e", "bd": str(csv_lab), "eixos": {"reversoes": [0, 1], "stop_x_media": [0.5, 1.0]}, "min_operacoes": 1, "top": 3}
    arq = tmp_path / "grade.json"
    arq.write_text(json.dumps(spec), encoding="utf-8")
    rc = cli.main([str(arq), "--workers", "2", "--saida", str(tmp_path / "out"), "--cache-dir", str(tmp_path / "cache"), "--trades", "1"])
    out = capsys.readouterr().out
    assert rc == 0 and "Verificação: OK" in out
    pasta = next((tmp_path / "out").iterdir())
    df = pd.read_csv(pasta / "resultados.csv", sep=";", decimal=",", encoding="utf-8-sig")
    assert len(df) == 4 and set(df["status"]) == {"ok"} and {"reversoes", "stop_x_media", "total_rs", "ret_dd", "oos_rs"} <= set(df.columns)
    assert (pasta / "resumo.md").read_text(encoding="utf-8").startswith("# Laboratório: e2e") and (pasta / "grade.json").exists()
    assert list(pasta.glob("trades_*.csv"))
    # o número da grade é o do app
    barras, sub = data.preparar_barras(data.carregar_csv(csv_lab.read_bytes())[0], 10)
    linha = df[(df["reversoes"] == 1) & (df["stop_x_media"] == 0.5)].iloc[0]
    assert linha["total_rs"] == pytest.approx(executar(barras, Params(reversoes=1, stop_x_media=0.5), sub)["resumo"]["total_rs"])


def test_cli_erros_de_grade_saem_com_codigo_2(tmp_path, capsys):
    assert cli.main(["--eixo", "campo_que_nao_existe=1,2"]) == 2
    assert "campo_que_nao_existe" in capsys.readouterr().err
    assert cli.main([str(tmp_path / "nao_existe.json")]) == 2


def test_cli_dry_run_nao_executa(capsys):
    assert cli.main(["--eixo", "reversoes=0,1,2", "--eixo", "book=cont,ambas", "--dry-run"]) == 0
    assert "6 combinações" in capsys.readouterr().out


# ------------------------------------------------------------------ no BD real (lento): os números-âncora saem iguais pelo laboratório
@pytest.mark.lento
def test_laboratorio_reproduz_os_numeros_ancora_no_bd_real(tmp_path):
    bd = executor.carregar_bd(BD_PADRAO, tmp_path)
    assert bd.id == executor.ANCORA["sha1"], "o BD padrão mudou: atualize `executor.ANCORA`, `test_golden.py` e `docs/motor.md`"
    gr = g.expandir({"variantes": [{}, {"reversoes": 1}, {"modo_entrada": "proximo_candle"}, {"sair_ao_tocar_mm": True}, {"rastrear_mm": True}]})
    res = executor.executar_grade(_unicos(gr), bd, "2025-01-01", workers=3)
    esperado = {0: (1054, 7391.0), 1: (1817, 6318.0), 2: (1054, 625.0), 3: (1054, 4365.0), 4: (1058, -909.0)}
    for i, (n, rs) in esperado.items():
        assert (res[i]["operacoes"], res[i]["total_rs"]) == (n, rs)
    assert executor.checar_ancora(bd) is None


# ------------------------------------------------------------------ janelas de tempo (busca walk-forward)
def test_janelas_particionam_o_total_e_contam_os_meses(mercado_sintetico):
    _, barras, sub, mercado = mercado_sintetico
    tr = rodar_trades(None, Params(**CASOS["tudo"]), sub, mercado)
    from strategylab.lab.executor import meses_do_mercado

    meses = meses_do_mercado(mercado)
    dias = sorted(mercado.dias, key=lambda x: x[0])
    ini, fim = str(dias[0][0]), str(dias[-1][0])
    meio = str(dias[len(dias) // 2][0])
    ant = (pd.Timestamp(meio) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    m = metricas(tr, None, meses, {"a": (ini, ant), "b": (meio, fim), "tudo": (ini, fim)})
    assert m["a_total_rs"] + m["b_total_rs"] == pytest.approx(m["total_rs"]) and m["tudo_total_rs"] == pytest.approx(m["total_rs"])
    assert m["a_operacoes"] + m["b_operacoes"] == m["operacoes"] and m["tudo_dd_rs"] == m["dd_rs"]
    assert m["tudo_meses_pos"] == m["meses_pos"] and m["tudo_pior_mes"] == m["pior_mes"]
    assert sum(m["por_mes"].values()) == pytest.approx(m["total_rs"]) and len(m["por_mes"]) == len(meses)


def test_resultado_da_janela_nao_depende_do_que_vem_depois_dela():
    """O coração do walk-forward: destruir TODOS os dados depois do fim da janela não pode mudar a janela (sem look-ahead)."""
    from tests.test_sem_lookahead import _destroi_o_futuro

    raw, _ = data.carregar_csv(csv_sintetico(dias=60, semente=17).encode())
    barras, sub = data.preparar_barras(raw, 10)
    dias = sorted(raw["date"].unique())
    fim_janela = dias[39]
    corte = pd.Timestamp(fim_janela) + pd.Timedelta(hours=23)
    destruido = _destroi_o_futuro(raw, corte, semente=3)
    barras2, _ = data.preparar_barras(destruido, 10)
    janelas = {"treino": (str(dias[0]), str(fim_janela))}
    for over in (CASOS["tudo"], CASOS["reversoes"], CASOS["mm"]):
        p = Params(**over)
        a = metricas(rodar_trades(barras, p, sub), None, None, janelas)
        b = metricas(rodar_trades(barras2, p, sub), None, None, janelas)
        assert a["treino_operacoes"] > 5
        for k in ("total_rs", "dd_rs", "operacoes", "pregoes"):
            assert a[f"treino_{k}"] == b[f"treino_{k}"], (over, k)


def test_cli_grava_colunas_de_janela_e_de_mes(csv_lab, tmp_path, capsys):
    spec = {"nome": "janelas", "bd": str(csv_lab), "eixos": {"reversoes": [0, 1]}, "min_operacoes": 1,
            "janelas": {"ini": ["2024-03-01", "2024-03-31"], "resto": ["2024-04-01", "2024-12-31"]}}
    arq = tmp_path / "g.json"
    arq.write_text(json.dumps(spec), encoding="utf-8")
    assert cli.main([str(arq), "--workers", "1", "--saida", str(tmp_path / "o"), "--cache-dir", str(tmp_path / "c"), "--verificar", "0"]) == 0
    capsys.readouterr()
    df = pd.read_csv(next((tmp_path / "o").iterdir()) / "resultados.csv", sep=";", decimal=",", encoding="utf-8-sig")
    assert {"ini_total_rs", "ini_meses_pos", "resto_dd_rs", "resto_operacoes"} <= set(df.columns)
    assert any(c.startswith("m_2024-") for c in df.columns)
    assert (df["ini_total_rs"] + df["resto_total_rs"]).tolist() == pytest.approx(df["total_rs"].tolist())


def test_janelas_mal_formadas_sao_recusadas():
    with pytest.raises(g.GradeErro, match="janelas"):
        g.expandir({"eixos": {"reversoes": [0, 1]}, "janelas": {"x": ["2024-01-01"]}})


# ------------------------------------------------------------------ trava do hold-out (dados depois de 2025)
def test_trava_recusa_bd_com_datas_depois_de_2025(tmp_path):
    csv = tmp_path / "WIN_1M_completo.csv"
    csv.write_text(csv_sintetico(dias=10, semente=3, inicio="2025-12-22"), encoding="utf-8")      # atravessa a virada do ano
    with pytest.raises(executor.BDAlemDoLimite, match="hold-out"):
        executor.carregar_bd(csv, tmp_path / "cache")
    assert not list((tmp_path / "cache").glob("*.pkl")) if (tmp_path / "cache").exists() else True      # nada foi preparado/guardado


def test_trava_aceita_bd_que_termina_em_2025(tmp_path):
    csv = tmp_path / "ate_2025.csv"
    csv.write_text(csv_sintetico(dias=8, semente=3, inicio="2025-12-10"), encoding="utf-8")        # 8 pregões: termina antes de 2026
    assert executor.carregar_bd(csv, tmp_path / "cache").id


def test_cli_recusa_bd_com_2026_com_codigo_2(tmp_path, capsys):
    csv = tmp_path / "completo.csv"
    csv.write_text(csv_sintetico(dias=10, semente=3, inicio="2025-12-22"), encoding="utf-8")
    spec = {"nome": "x", "bd": str(csv), "eixos": {"reversoes": [0, 1]}}
    arq = tmp_path / "g.json"
    arq.write_text(json.dumps(spec), encoding="utf-8")
    assert cli.main([str(arq), "--workers", "1", "--cache-dir", str(tmp_path / "c"), "--saida", str(tmp_path / "o")]) == 2
    assert "hold-out" in capsys.readouterr().err


def test_o_bd_padrao_do_projeto_respeita_a_trava():
    from strategylab.paths import BD_PADRAO, DATA_LIMITE_PESQUISA

    anos = {int(a) for a in __import__("re").findall(rb"\d{2}/\d{2}/(\d{4})", BD_PADRAO.read_bytes())}
    assert max(anos) <= int(DATA_LIMITE_PESQUISA[:4])
