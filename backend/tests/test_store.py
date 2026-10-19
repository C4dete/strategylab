"""Persistência das estratégias em disco."""

from __future__ import annotations

import json

import pytest

from strategylab.engine.params import Params
from strategylab.services.strategies import (EstrategiaStore, NaoEncontrada, NomeDuplicado, NomeInvalido,
                                             NOME_SEMENTE)


@pytest.fixture
def store(tmp_path):
    return EstrategiaStore(tmp_path / "estrategias")


def test_primeira_execucao_cria_a_inicial_default_com_os_valores_padrao(store):
    itens = store.listar()
    assert [e.name for e in itens] == [NOME_SEMENTE]
    assert itens[0].id == "inicial_default" and itens[0].params == Params()
    assert store.ultima() == "inicial_default"


def test_a_semente_nasce_uma_vez_so(tmp_path):
    raiz = tmp_path / "estrategias"
    s1 = EstrategiaStore(raiz)
    s1.excluir("inicial_default")
    s2 = EstrategiaStore(raiz)                       # "reabrir o sistema"
    assert s2.listar() == []
    assert s2.ultima() is None


def test_criar_salvar_renomear_excluir_persistem_em_arquivo(tmp_path):
    raiz = tmp_path / "estrategias"
    s1 = EstrategiaStore(raiz)
    e = s1.criar("  Minha   Estratégia ", Params(stop_x_media=2.0))
    assert e.name == "Minha Estratégia" and e.id == "minha_estrategia"
    assert (raiz / "minha_estrategia.json").exists()

    s1.salvar(e.id, Params(stop_x_media=2.5, book="ambas"))
    s1.renomear(e.id, "Renomeada")

    s2 = EstrategiaStore(raiz)                       # nova instância = sistema reaberto
    lido = s2.obter("minha_estrategia")
    assert lido.name == "Renomeada"                  # o id (arquivo) não muda ao renomear
    assert lido.params.stop_x_media == 2.5 and lido.params.book == "ambas"
    assert s2.ultima() == "minha_estrategia"

    s2.excluir("minha_estrategia")
    assert not (raiz / "minha_estrategia.json").exists()
    assert [x.id for x in EstrategiaStore(raiz).listar()] == ["inicial_default"]
    assert s2.ultima() == "inicial_default"          # a "última" cai para uma que existe


def test_arquivo_gravado_e_legivel_e_versionado(store):
    store.criar("Teste")
    bruto = json.loads((store.raiz / "teste.json").read_text(encoding="utf-8"))
    assert bruto["schema"] == 1 and bruto["name"] == "Teste"
    assert bruto["params"]["candles_gatilho"] == 5
    assert not list(store.raiz.glob("*.tmp"))        # escrita atômica não deixa lixo


def test_nome_duplicado_ignora_caixa_e_nome_invalido(store):
    store.criar("Alpha")
    with pytest.raises(NomeDuplicado):
        store.criar("alpha")
    store.criar("Beta")
    with pytest.raises(NomeDuplicado):
        store.renomear("beta", "ALPHA")
    store.renomear("beta", "Beta")                   # renomear para o próprio nome é permitido
    for ruim in ("", "   ", "x" * 61):
        with pytest.raises(NomeInvalido):
            store.criar(ruim)


def test_ids_colidem_e_ganham_sufixo(store):
    a = store.criar("Minha Estratégia")
    b = store.criar("minha estrategia")              # nome diferente (acento), mesmo slug
    assert (a.id, b.id) == ("minha_estrategia", "minha_estrategia_2")


def test_nao_encontrada_e_id_malicioso(store):
    for ruim in ("nao_existe", "../x", "..\\x", "_estado"):
        with pytest.raises(NaoEncontrada):
            store.obter(ruim)
    with pytest.raises(NaoEncontrada):
        store.excluir("nao_existe")


def test_arquivo_corrompido_nao_derruba_a_lista(store):
    (store.raiz / "quebrada.json").write_text("{isso não é json", encoding="utf-8")
    (store.raiz / "invalida.json").write_text(
        json.dumps({"name": "Invalida", "params": {"candles_gatilho": 99}}), encoding="utf-8")
    por_id = {e.id: e for e in store.listar()}
    assert por_id["inicial_default"].valida
    assert not por_id["quebrada"].valida and "ilegível" in por_id["quebrada"].erro
    assert not por_id["invalida"].valida and "candles_gatilho" in por_id["invalida"].erro
    store.excluir("quebrada")                        # dá para limpar


def test_arquivo_antigo_com_campos_faltando_continua_valido(store):
    (store.raiz / "antiga.json").write_text(
        json.dumps({"schema": 1, "name": "Antiga", "params": {"stop_x_media": 1.5}}), encoding="utf-8")
    e = store.obter("antiga")
    assert e.valida and e.params.stop_x_media == 1.5 and e.params.candles_media == 5


def test_definir_ultima(store):
    store.criar("Outra")
    store.definir_ultima("inicial_default")
    assert store.ultima() == "inicial_default"
    with pytest.raises(NaoEncontrada):
        store.definir_ultima("fantasma")
