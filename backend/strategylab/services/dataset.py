"""BD ativo: o padrão (carregado em segundo plano na subida) ou um arquivo enviado pelo usuário.

O arquivo enviado vale só para a sessão do servidor: ao reiniciar volta ao padrão.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from ..engine import data as dados
from ..engine.indicators import bollinger, ema
from ..engine.params import EXECUCAO
from ..engine.runner import Mercado, preparar_mercado


@dataclass
class BD:
    id: str                   # hash do conteúdo (chave do cache de resultados)
    nome: str
    padrao: bool
    info: dados.InfoBD
    barras: pd.DataFrame      # barras do timeframe da estratégia + sub-candles
    sub_min: int
    _indicadores: dict = field(default_factory=dict, repr=False)
    _mercado: Optional[Mercado] = field(default=None, repr=False)

    def mercado(self) -> Mercado:
        """O BD preparado para o motor (feito uma vez; é o mesmo que o laboratório de combinações usa)."""
        if self._mercado is None:
            self._mercado = preparar_mercado(self.barras, self.sub_min)
        return self._mercado

    def indicadores(self, mm_periodo: int, bb_periodo: int, bb_desvio: float) -> dict:
        """Séries de indicadores sobre TODAS as barras (valor no fechamento de cada barra), em cache por parâmetros."""
        chave = (mm_periodo, bb_periodo, round(bb_desvio, 4))
        achou = self._indicadores.get(chave)
        if achou is None:
            close = self.barras["close"].to_numpy(float)
            bm, bs, bi = bollinger(close, bb_periodo, bb_desvio)
            achou = {"mm": ema(close, mm_periodo), "bbm": bm, "bbs": bs, "bbi": bi}
            if len(self._indicadores) >= 6:
                self._indicadores.pop(next(iter(self._indicadores)))
            self._indicadores[chave] = achou
        return achou


def _construir(nome: str, conteudo: bytes, padrao: bool) -> BD:
    df, avisos = dados.carregar_csv(conteudo)
    info = dados.informacoes(df, avisos)
    barras, sub_min = dados.preparar_barras(df, EXECUCAO.timeframe_min)
    if sub_min > 1:
        info.avisos.append(
            f"Candles de {sub_min} min: a ordem dos eventos dentro da barra é lida com menos detalhe. "
            "Os números não são comparáveis aos do BD de 1 min."
        )
    return BD(hashlib.sha1(conteudo).hexdigest()[:16], nome, padrao, info, barras, sub_min)


class RegistroBD:
    def __init__(self, caminho_padrao: Path):
        self.caminho_padrao = Path(caminho_padrao)
        self._lock = threading.Lock()
        self._pronto = threading.Event()
        self._padrao: Optional[BD] = None
        self._ativo: Optional[BD] = None
        self.estado = "carregando"        # carregando | pronto | erro
        self.erro: Optional[str] = None

    # --------------------------------------------------------------- padrão
    def _carregar_padrao(self) -> None:
        try:
            conteudo = self.caminho_padrao.read_bytes()
            bd = _construir(self.caminho_padrao.name, conteudo, padrao=True)
        except FileNotFoundError:
            self.erro = f"BD padrão não encontrado: {self.caminho_padrao}"
        except dados.DadosInvalidos as exc:
            self.erro = f"BD padrão inválido: {exc}"
        except Exception as exc:  # noqa: BLE001 - qualquer falha precisa chegar à tela
            self.erro = f"Falha ao carregar o BD padrão: {exc}"
        else:
            with self._lock:
                self._padrao = bd
                if self._ativo is None:
                    self._ativo = bd
                    self.estado = "pronto"
            self._pronto.set()
            return
        with self._lock:
            if self._ativo is None:
                self.estado = "erro"
        self._pronto.set()

    def iniciar(self, em_segundo_plano: bool = True) -> None:
        if em_segundo_plano:
            threading.Thread(target=self._carregar_padrao, name="bd-padrao", daemon=True).start()
        else:
            self._carregar_padrao()

    # --------------------------------------------------------------- acesso
    def aguardar(self, timeout: float = 120.0) -> bool:
        return self._pronto.wait(timeout)

    def ativo(self) -> Optional[BD]:
        with self._lock:
            return self._ativo

    def carregar_upload(self, nome: str, conteudo: bytes) -> BD:
        """Valida, prepara e ativa o arquivo. Levanta `DadosInvalidos` (nada muda se falhar)."""
        bd = _construir(nome, conteudo, padrao=False)
        with self._lock:
            self._ativo = bd
            self.estado = "pronto"
        self._pronto.set()
        return bd

    def voltar_padrao(self) -> BD:
        self.aguardar()
        with self._lock:
            if self._padrao is None:
                raise dados.DadosInvalidos(self.erro or "BD padrão indisponível.")
            self._ativo = self._padrao
            self.estado = "pronto"
            return self._padrao

    # --------------------------------------------------------------- consulta
    def barras_do_dia(self, bd: BD, dia, indicadores: Optional[tuple[int, int, float]] = None) -> list[dict]:
        """Barras do pregão. Com `indicadores=(mm, bb, k)` anexa, em cada barra, o valor de cada indicador NO FECHAMENTO dela."""
        mascara = (bd.barras["date"] == dia).to_numpy()
        d = bd.barras[mascara]
        ind = bd.indicadores(*indicadores) if indicadores else None

        def v(chave: str, k: int):
            x = ind[chave][mascara][k]
            return None if x != x else float(x)

        out = []
        for k, r in enumerate(d.itertuples(index=False)):
            b = {"t": r.datetime.strftime("%H:%M"), "o": float(r.open), "h": float(r.high),
                 "l": float(r.low), "c": float(r.close)}
            if ind is not None:
                b.update(mm=v("mm", k), bbm=v("bbm", k), bbs=v("bbs", k), bbi=v("bbi", k))
            out.append(b)
        return out


class CacheResultados:
    """LRU simples: (id do BD, parâmetros) -> resultado do backtest."""

    def __init__(self, capacidade: int = 24):
        self.capacidade = capacidade
        self._itens: "OrderedDict[tuple, dict]" = OrderedDict()
        self._lock = threading.Lock()

    def obter(self, chave: tuple) -> Optional[dict]:
        with self._lock:
            if chave in self._itens:
                self._itens.move_to_end(chave)
                return self._itens[chave]
        return None

    def guardar(self, chave: tuple, valor: dict) -> None:
        with self._lock:
            self._itens[chave] = valor
            self._itens.move_to_end(chave)
            while len(self._itens) > self.capacidade:
                self._itens.popitem(last=False)
