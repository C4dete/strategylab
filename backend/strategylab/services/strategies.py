"""Persistência das estratégias: um JSON por estratégia em `estrategias/`.

    estrategias/<id>.json     {schema, id, name, created_at, updated_at, params}
    estrategias/_estado.json  {seeded, ultima}

O `id` nasce do nome (slug) e NÃO muda ao renomear. Escritas são atômicas.
"""

from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from ..engine.params import Params, params_padrao

SCHEMA = 1
NOME_SEMENTE = "inicial_default"
_ESTADO = "_estado.json"
_NOME_MAX = 60


class EstrategiaErro(Exception):
    """Erro de negócio com mensagem para o usuário. `status` é o código HTTP sugerido."""

    status = 400


class NaoEncontrada(EstrategiaErro):
    status = 404


class NomeInvalido(EstrategiaErro):
    status = 422


class NomeDuplicado(EstrategiaErro):
    status = 409


@dataclass
class Estrategia:
    id: str
    name: str
    created_at: str
    updated_at: str
    params: Optional[Params]          # None quando o arquivo está inválido
    erro: Optional[str] = None

    @property
    def valida(self) -> bool:
        return self.params is not None


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _slug(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "estrategia"


def _limpa_nome(nome: str) -> str:
    nome = re.sub(r"\s+", " ", (nome or "")).strip()
    if not nome:
        raise NomeInvalido("Dê um nome à estratégia.")
    if len(nome) > _NOME_MAX:
        raise NomeInvalido(f"O nome pode ter no máximo {_NOME_MAX} caracteres.")
    return nome


class EstrategiaStore:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.garantir_semente()

    # ------------------------------------------------------------------ arquivos
    def _arquivo(self, id_: str) -> Path:
        return self.raiz / f"{id_}.json"

    def _escrever(self, caminho: Path, dados: dict) -> None:
        tmp = caminho.with_suffix(caminho.suffix + ".tmp")
        tmp.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, caminho)

    def _ler(self, caminho: Path) -> Estrategia:
        id_ = caminho.stem
        try:
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
            if not isinstance(bruto, dict):
                raise ValueError("o arquivo não contém um objeto JSON")
        except (OSError, ValueError) as exc:
            return Estrategia(id_, id_, "", "", None, f"Arquivo ilegível: {exc}")
        nome = str(bruto.get("name") or id_)
        criada, atualizada = str(bruto.get("created_at", "")), str(bruto.get("updated_at", ""))
        try:
            params = Params.model_validate(bruto.get("params") or {})
        except ValidationError as exc:
            msg = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            return Estrategia(id_, nome, criada, atualizada, None, f"Parâmetros inválidos ({msg})")
        return Estrategia(id_, nome, criada, atualizada, params)

    def _gravar(self, e: Estrategia) -> None:
        assert e.params is not None
        self._escrever(self._arquivo(e.id), {
            "schema": SCHEMA, "id": e.id, "name": e.name,
            "created_at": e.created_at, "updated_at": e.updated_at,
            "params": e.params.model_dump(),
        })

    # ------------------------------------------------------------------ estado
    def _estado(self) -> dict:
        try:
            est = json.loads((self.raiz / _ESTADO).read_text(encoding="utf-8"))
            return est if isinstance(est, dict) else {}
        except (OSError, ValueError):
            return {}

    def _salva_estado(self, **campos) -> None:
        est = self._estado()
        est.update(campos)
        self._escrever(self.raiz / _ESTADO, est)

    def ultima(self) -> Optional[str]:
        return self._estado().get("ultima")

    def definir_ultima(self, id_: str) -> None:
        with self._lock:
            self.obter(id_)
            self._salva_estado(ultima=id_)

    def correlacionar(self) -> dict:
        """Mapa principal -> ids marcados em "Correlacionar", só com estratégias que existem e são válidas."""
        bruto = self._estado().get("correlacionar")
        if not isinstance(bruto, dict):
            return {}
        validas = {e.id for e in self.listar() if e.valida}
        saida = {}
        for principal, ids in bruto.items():
            if principal not in validas or not isinstance(ids, list):
                continue
            vistos = [i for k, i in enumerate(ids) if isinstance(i, str) and i in validas and i != principal and i not in ids[:k]]
            if vistos:
                saida[principal] = vistos
        return saida

    def definir_correlacionar(self, id_: str, ids: List[str]) -> List[str]:
        """Grava (em ordem, sem repetir) as correlacionadas da principal. Lista vazia apaga a marca: ao voltar, vem sem nenhuma."""
        with self._lock:
            self.obter(id_)
            validas = {e.id for e in self.listar() if e.valida}
            limpas: List[str] = []
            for i in ids:
                if i in validas and i != id_ and i not in limpas:
                    limpas.append(i)
            mapa = {k: v for k, v in (self._estado().get("correlacionar") or {}).items() if k != id_}
            if limpas:
                mapa[id_] = limpas
            self._salva_estado(correlacionar=mapa)
            return limpas

    def garantir_semente(self) -> None:
        """Cria a `inicial_default` UMA vez; se o usuário apagar, ela não volta."""
        with self._lock:
            if self._estado().get("seeded"):
                return
            if not any(self._ids()):
                agora = _agora()
                self._gravar(Estrategia(_slug(NOME_SEMENTE), NOME_SEMENTE, agora, agora, params_padrao()))
                self._salva_estado(seeded=True, ultima=_slug(NOME_SEMENTE))
            else:
                self._salva_estado(seeded=True)

    # ------------------------------------------------------------------ consulta
    def _ids(self) -> List[str]:
        return sorted(p.stem for p in self.raiz.glob("*.json") if not p.stem.startswith("_"))

    def listar(self) -> List[Estrategia]:
        with self._lock:
            itens = [self._ler(self._arquivo(i)) for i in self._ids()]
        return sorted(itens, key=lambda e: e.name.casefold())

    def obter(self, id_: str) -> Estrategia:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_\-]*", id_ or ""):
            raise NaoEncontrada("Estratégia não encontrada.")
        caminho = self._arquivo(id_)
        if not caminho.exists():
            raise NaoEncontrada("Estratégia não encontrada.")
        return self._ler(caminho)

    # ------------------------------------------------------------------ mutações
    def _checa_nome_livre(self, nome: str, ignorar: Optional[str] = None) -> None:
        for e in self.listar():
            if e.id != ignorar and e.name.casefold() == nome.casefold():
                raise NomeDuplicado(f"Já existe uma estratégia chamada “{e.name}”.")

    def criar(self, nome: str, params: Optional[Params] = None) -> Estrategia:
        nome = _limpa_nome(nome)
        with self._lock:
            self._checa_nome_livre(nome)
            base, n = _slug(nome), 1
            id_ = base
            while self._arquivo(id_).exists():
                n += 1
                id_ = f"{base}_{n}"
            agora = _agora()
            e = Estrategia(id_, nome, agora, agora, params or params_padrao())
            self._gravar(e)
            self._salva_estado(ultima=id_)
            return e

    def salvar(self, id_: str, params: Params) -> Estrategia:
        with self._lock:
            e = self.obter(id_)
            e.params = params
            e.erro = None
            e.updated_at = _agora()
            self._gravar(e)
            return e

    def renomear(self, id_: str, nome: str) -> Estrategia:
        nome = _limpa_nome(nome)
        with self._lock:
            e = self.obter(id_)
            self._checa_nome_livre(nome, ignorar=id_)
            if e.params is None:
                raise EstrategiaErro("Esta estratégia está inválida; corrija ou exclua o arquivo.")
            e.name = nome
            e.updated_at = _agora()
            self._gravar(e)
            return e

    def excluir(self, id_: str) -> None:
        with self._lock:
            self.obter(id_)
            self._arquivo(id_).unlink()
            mapa = (self._estado().get("correlacionar") or {})
            if mapa:                                         # a estratégia some das listas de todas as outras
                self._salva_estado(correlacionar={k: [i for i in v if i != id_] for k, v in mapa.items()
                                                  if k != id_ and [i for i in v if i != id_]})
            if self.ultima() == id_:
                restantes = [e.id for e in self.listar()]
                self._salva_estado(ultima=restantes[0] if restantes else None)
