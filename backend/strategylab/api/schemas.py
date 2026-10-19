"""Modelos de entrada e saída da API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from ..engine.params import Params


class EstrategiaOut(BaseModel):
    id: str
    nome: str
    atualizada_em: str
    valida: bool
    erro: Optional[str] = None
    params: Optional[Params] = None


class ListaEstrategias(BaseModel):
    estrategias: List[EstrategiaOut]
    ultima: Optional[str] = None


class NovaEstrategia(BaseModel):
    nome: str
    params: Optional[Params] = None       # None = valores padrão


class SalvarParams(BaseModel):
    params: Params


class Renomear(BaseModel):
    nome: str


class Ultima(BaseModel):
    id: str


class BDOut(BaseModel):
    estado: str                            # carregando | pronto | erro
    erro: Optional[str] = None
    id: Optional[str] = None
    nome: Optional[str] = None
    padrao: Optional[bool] = None
    linhas: Optional[int] = None
    pregoes: Optional[int] = None
    inicio: Optional[str] = None
    fim: Optional[str] = None
    timeframe_min: Optional[int] = None
    avisos: List[str] = []


class BacktestIn(BaseModel):
    params: Params
