"""Execução paralela da grade sobre o MESMO motor do app (`engine.runner.rodar_trades`).

Fidelidade: o laboratório não tem motor próprio. Cada combinação passa por `rodar_trades` + `metricas` (que usa as funções de
resumo do app). A velocidade vem de três coisas que não mudam nenhum número: o BD é preparado UMA vez (`Mercado`: pregões
pré-processados + EMAs em cache), combinações com a mesma `chave_motor` são calculadas uma só vez, e as combinações rodam em
vários processos (um `Mercado` por processo, lido de um cache em disco).
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import re

from ..engine import data as dados
from ..engine.params import EXECUCAO, Params
from ..paths import DATA_LIMITE_PESQUISA
from ..engine.runner import Mercado, executar, preparar_mercado, rodar_trades
from .metricas import metricas

_ENGINE = Path(__file__).resolve().parents[1] / "engine"
_ARQUIVOS_DO_MOTOR = ("ghost.py", "data.py", "runner.py", "indicators.py", "fills.py", "metrics.py", "params.py")

# sha1 do BD padrão do projeto (`dados/WIN_1M_21_25.csv`) e o resultado do cenário base nele (números-âncora de `tests/test_golden.py`).
ANCORA = {"sha1": "acb224d15a61d012b2083a9ec199b679764d9a26", "operacoes": 1054, "total_rs": 7391.0}


def hash_do_motor() -> str:
    """Muda quando QUALQUER arquivo do motor muda: invalida o cache em disco (que guarda dados derivados do código)."""
    h = hashlib.sha1()
    for nome in _ARQUIVOS_DO_MOTOR:
        h.update((_ENGINE / nome).read_bytes())
    return h.hexdigest()[:10]


@dataclass
class BDPronto:
    id: str                       # sha1 do CSV
    nome: str
    barras: pd.DataFrame
    sub_min: int
    caminho_mercado: Path         # pickle do `Mercado` (cada processo lê o seu)
    do_cache: bool


class BDAlemDoLimite(ValueError):
    """O CSV tem datas depois de `DATA_LIMITE_PESQUISA`: é o hold-out do Ricardo e não pode ser usado em pesquisa."""


def _checa_limite(conteudo: bytes, nome: str) -> None:
    """Recusa o arquivo SEM interpretar valores: só olha os anos que aparecem nas datas (dd/mm/aaaa)."""
    anos = {int(a) for a in re.findall(rb"\d{2}/\d{2}/(\d{4})", conteudo)}
    if anos and max(anos) > int(DATA_LIMITE_PESQUISA[:4]):
        raise BDAlemDoLimite(
            f"'{nome}' tem dados depois de {DATA_LIMITE_PESQUISA}. Esse período é o hold-out do Ricardo e não entra em pesquisa. "
            "Use dados/WIN_1M_21_25.csv (ou um BD que termine em 2025).")


def carregar_bd(csv: Path, cache_dir: Path) -> BDPronto:
    """Lê o CSV (ou usa o cache em disco, indexado pelo conteúdo do CSV e pelo código do motor) e prepara o `Mercado`."""
    csv = Path(csv)
    conteudo = csv.read_bytes()
    _checa_limite(conteudo, csv.name)
    sha = hashlib.sha1(conteudo).hexdigest()
    chave = f"{sha[:12]}_{hash_do_motor()}"
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    f_barras, f_mercado = cache_dir / f"barras_{chave}.pkl", cache_dir / f"mercado_{chave}.pkl"
    if f_barras.exists() and f_mercado.exists():
        try:
            with open(f_barras, "rb") as fh:
                barras, sub_min = pickle.load(fh)
            return BDPronto(sha, csv.name, barras, sub_min, f_mercado, True)
        except Exception:                                             # noqa: BLE001 - cache ilegível: refaz
            pass
    df, _ = dados.carregar_csv(conteudo)
    barras, sub_min = dados.preparar_barras(df, EXECUCAO.timeframe_min)
    mercado = preparar_mercado(barras, sub_min)
    for antigo in cache_dir.glob("*.pkl"):                            # só o cache atual fica (os outros ficaram velhos)
        if antigo.name not in (f_barras.name, f_mercado.name):
            antigo.unlink(missing_ok=True)
    for arq, obj in ((f_barras, (barras, sub_min)), (f_mercado, mercado)):
        tmp = arq.with_suffix(".tmp")
        with open(tmp, "wb") as fh:
            pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, arq)
    return BDPronto(sha, csv.name, barras, sub_min, f_mercado, False)


# --------------------------------------------------------------------------- processos de trabalho
_MERCADO: Optional[Mercado] = None
_CORTE: Optional[str] = None
_JANELAS: Optional[dict] = None


def _baixa_prioridade() -> None:
    """Os trabalhadores rodam com prioridade abaixo do normal: o computador continua utilizável durante a grade."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL
        except Exception:                                             # noqa: BLE001
            pass
    else:
        try:
            os.nice(5)
        except Exception:                                             # noqa: BLE001
            pass


def _iniciar(caminho_mercado: str, corte: Optional[str], janelas: Optional[dict] = None) -> None:
    global _MERCADO, _CORTE, _JANELAS
    _baixa_prioridade()
    with open(caminho_mercado, "rb") as fh:
        _MERCADO = pickle.load(fh)
    _CORTE = corte
    _JANELAS = janelas


def meses_do_mercado(mercado: Mercado) -> list:
    """Meses (AAAA-MM) com pregões no BD: base das métricas de meses positivos (mês sem operação não conta como positivo)."""
    achou = getattr(mercado, "_meses_bd", None)
    if achou is None:
        achou = sorted({d.strftime("%Y-%m") for d, *_ in mercado.dias})
        mercado._meses_bd = achou
    return achou


def _calcular(mercado: Mercado, params: dict, corte: Optional[str], janelas: Optional[dict] = None) -> dict:
    t0 = time.perf_counter()
    try:
        p = Params(**params)
        tr = rodar_trades(None, p, mercado.sub_min, mercado)
        m = metricas(tr, corte, meses_do_mercado(mercado), janelas)
        m["status"] = "ok"
    except Exception as exc:                                          # noqa: BLE001 - uma combinação ruim não derruba a grade
        m = {"status": "erro", "erro": f"{type(exc).__name__}: {exc}"}
    m["tempo_ms"] = int((time.perf_counter() - t0) * 1000)
    return m


def _tarefa(lote: list) -> list:
    return [(i, _calcular(_MERCADO, params, _CORTE, _JANELAS)) for i, params in lote]


# --------------------------------------------------------------------------- grade
def executar_grade(unicos: list, bd: BDPronto, corte: Optional[str], workers: int,
                   progresso: Optional[Callable[[int, int, float], None]] = None, janelas: Optional[dict] = None) -> dict:
    """`unicos` = [(indice, params_dict)] já sem repetições de `chave_motor`. Devolve {indice: metricas}."""
    total = len(unicos)
    resultados: dict = {}
    t0 = time.perf_counter()
    if total == 0:
        return resultados
    if workers <= 1 or total == 1:
        with open(bd.caminho_mercado, "rb") as fh:
            mercado = pickle.load(fh)
        for k, (i, params) in enumerate(unicos, 1):
            resultados[i] = _calcular(mercado, params, corte, janelas)
            if progresso:
                progresso(k, total, time.perf_counter() - t0)
        return resultados
    workers = min(workers, total)
    tamanho = max(1, min(8, total // (workers * 6)))
    lotes = [unicos[k:k + tamanho] for k in range(0, total, tamanho)]
    feitos = 0
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn"),
                             initializer=_iniciar, initargs=(str(bd.caminho_mercado), corte, janelas)) as pool:
        futuros = [pool.submit(_tarefa, lote) for lote in lotes]
        for fut in as_completed(futuros):
            for i, m in fut.result():
                resultados[i] = m
            feitos += len(fut.result())
            if progresso:
                progresso(feitos, total, time.perf_counter() - t0)
    return resultados


# --------------------------------------------------------------------------- verificação de fidelidade
def verificar(bd: BDPronto, amostra: list, resultados: dict, corte: Optional[str]) -> list:
    """Recalcula `amostra` ([(indice, params)]) pelo CAMINHO DO APP (`executar`, com um `Mercado` novo feito do CSV, sem
    cache em disco nem processos) e compara com o que a grade produziu. Devolve a lista de divergências (vazia = fiel)."""
    mercado = preparar_mercado(bd.barras, bd.sub_min)
    erros = []
    for i, params in amostra:
        esperado = executar(bd.barras, Params(**params), bd.sub_min, mercado)["resumo"]
        obtido = resultados[i]
        pares = [("operacoes", esperado["operacoes"], obtido.get("operacoes")),
                 ("total_rs", esperado["total_rs"], obtido.get("total_rs")),
                 ("total_pts", esperado["total_pts"], obtido.get("total_pts")),
                 ("dd_rs", esperado["drawdown"]["rs"], obtido.get("dd_rs")),
                 ("win_rate", esperado["win_rate"], obtido.get("win_rate"))]
        for nome, a, b in pares:
            if b is None or abs(float(a) - float(b)) > 1e-9:
                erros.append(f"combinação {i}: {nome} do app = {a}, da grade = {b}")
    return erros


def checar_ancora(bd: BDPronto) -> Optional[str]:
    """Se o BD é o padrão do projeto, o cenário base (`Params()`) precisa dar exatamente o número-âncora. Devolve a divergência
    (ou None quando bate / quando o BD não é o conhecido)."""
    if ANCORA["sha1"] is None or bd.id != ANCORA["sha1"]:
        return None
    with open(bd.caminho_mercado, "rb") as fh:
        mercado = pickle.load(fh)
    tr = rodar_trades(None, Params(), bd.sub_min, mercado)
    if len(tr) != ANCORA["operacoes"] or abs(float(tr["rs"].sum()) - ANCORA["total_rs"]) > 1e-6:
        return (f"cenário base no BD padrão deu {len(tr)} operações / R$ {tr['rs'].sum():.2f}; "
                f"o esperado é {ANCORA['operacoes']} / R$ {ANCORA['total_rs']:.2f}")
    return None
