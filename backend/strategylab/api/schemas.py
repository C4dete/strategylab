"""Modelos de entrada e saída da API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

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
    correlacionar: Dict[str, List[str]] = {}      # principal -> ids marcados em "Correlacionar"


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


class Correlacionar(BaseModel):
    id: str
    ids: List[str] = []


class Componente(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    params: Params


class PortfolioIn(BaseModel):
    """Estratégias do conjunto; a primeira é a principal (com o rascunho), as outras vêm com os parâmetros salvos."""
    componentes: List[Componente] = Field(min_length=1, max_length=12)
