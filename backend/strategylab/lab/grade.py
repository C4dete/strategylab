"""Expansão de uma "grade" de testes (JSON) em combinações de parâmetros.

Formato (todos os campos opcionais, menos `eixos` ou `variantes`):

    {
      "nome": "reversoes x stop",
      "base": "inicial_default",                     # estratégia salva (id ou nome) OU {campo: valor}; omitido = padrões de `Params`
      "variantes": [{}, {"sair_ao_tocar_mm": true}],   # cenários explícitos, cada um é um bloco de campos fixos
      "eixos": {                                       # produto cartesiano de TODOS os eixos
        "reversoes": [0, 1, 2],
        "stop_x_media": {"de": 0.5, "ate": 2.0, "passo": 0.25},
        "book": ["cont", "ambas"]
      },
      "corte_oos": "2025-01-01",                       # separa IS (antes) de OOS (a partir da data); null desliga
      "janelas": {"trainA": ["2021-09-01", "2023-12-31"], "testA": ["2024-01-01", "2024-12-31"]},   # métricas por janela (colunas trainA_total_rs ...)
      "ordenar_por": "ret_dd", "top": 20, "min_operacoes": 30
    }

Combinações = cada variante (ou uma vazia) × produto dos eixos, aplicadas sobre a base. Os nomes de campo são os de
`Params` (ver `docs/motor.md`); um nome desconhecido é ERRO (`Params` ignoraria em silêncio e o eixo não faria nada).
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from ..engine.params import Params

CAMPOS = tuple(Params.model_fields)


class GradeErro(ValueError):
    """Grade mal formada (a mensagem diz o que corrigir)."""


@dataclass
class Combinacao:
    id: int
    variaveis: dict                    # só o que varia (variante + eixos): são as colunas do relatório
    params: dict                       # parâmetros completos (base + variáveis), já validados
    chave: str = ""                    # `Params.chave_motor()`: combinações com a mesma chave dão o mesmo resultado
    erro: Optional[str] = None         # parâmetros inválidos (ex.: última entrada antes do início)


@dataclass
class Grade:
    nome: str
    combinacoes: list
    corte_oos: Optional[str]
    ordenar_por: str
    top: int
    min_operacoes: int
    bd: Optional[str]
    janelas: dict = field(default_factory=dict)
    eixos: dict = field(default_factory=dict)
    base_nome: str = "padrão"

    @property
    def variaveis_nomes(self) -> list:
        """Campos que variam em alguma combinação (as colunas de parâmetros do relatório)."""
        return list(dict.fromkeys(k for c in self.combinacoes for k in c.variaveis))


def valores_do_eixo(nome: str, v: Any) -> list:
    if isinstance(v, dict):
        try:
            de, ate, passo = float(v["de"]), float(v["ate"]), float(v["passo"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GradeErro(f"Eixo '{nome}': use {{\"de\": .., \"ate\": .., \"passo\": ..}}.") from exc
        if passo <= 0 or ate < de:
            raise GradeErro(f"Eixo '{nome}': passo precisa ser > 0 e 'ate' >= 'de'.")
        n = int(round((ate - de) / passo + 1e-9)) + 1
        vals = [round(de + k * passo, 4) for k in range(n)]
        if all(float(x).is_integer() for x in (de, ate, passo)):
            vals = [int(x) for x in vals]
        return vals
    if not isinstance(v, list) or not v:
        raise GradeErro(f"Eixo '{nome}': informe uma lista não vazia de valores ou {{de, ate, passo}}.")
    return list(v)


def _checa_campos(onde: str, d: dict) -> None:
    ruins = [k for k in d if k not in CAMPOS]
    if ruins:
        raise GradeErro(f"{onde}: campo(s) desconhecido(s) {', '.join(ruins)}. Campos válidos: {', '.join(CAMPOS)}.")


def resolver_base(base: Any, estrategias_dir: Optional[Path]) -> tuple[dict, str]:
    """Estratégia salva (id ou nome, sem diferenciar maiúsculas) ou dicionário de campos."""
    if base is None:
        return {}, "padrão"
    if isinstance(base, dict):
        _checa_campos("base", base)
        return dict(base), "campos informados"
    if isinstance(base, str):
        if estrategias_dir is None or not Path(estrategias_dir).is_dir():
            raise GradeErro(f"Base '{base}': pasta de estratégias indisponível.")
        for arq in sorted(Path(estrategias_dir).glob("*.json")):
            if arq.name.startswith("_"):
                continue
            try:
                doc = json.loads(arq.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if base.strip().lower() in (str(doc.get("id", "")).lower(), str(doc.get("name", "")).lower()):
                p = doc.get("params") or {}
                _checa_campos(f"base '{base}'", p)
                return dict(p), f"estratégia '{doc.get('name', base)}'"
        raise GradeErro(f"Base '{base}': nenhuma estratégia salva com esse id ou nome.")
    raise GradeErro("'base' deve ser o nome de uma estratégia salva ou um objeto {campo: valor}.")


def expandir(spec: dict, estrategias_dir: Optional[Path] = None) -> Grade:
    if not isinstance(spec, dict):
        raise GradeErro("A grade precisa ser um objeto JSON.")
    desconhecidas = set(spec) - {"nome", "base", "variantes", "eixos", "corte_oos", "ordenar_por", "top", "min_operacoes", "bd", "janelas"}
    if desconhecidas:
        raise GradeErro(f"Chave(s) desconhecida(s) na grade: {', '.join(sorted(desconhecidas))}.")
    base, base_nome = resolver_base(spec.get("base"), estrategias_dir)

    variantes = spec.get("variantes") or [{}]
    if not isinstance(variantes, list) or not all(isinstance(v, dict) for v in variantes):
        raise GradeErro("'variantes' deve ser uma lista de objetos {campo: valor}.")
    for k, v in enumerate(variantes, 1):
        _checa_campos(f"variante {k}", v)
    eixos_in = spec.get("eixos") or {}
    if not isinstance(eixos_in, dict):
        raise GradeErro("'eixos' deve ser um objeto {campo: valores}.")
    _checa_campos("eixos", eixos_in)
    eixos = {nome: valores_do_eixo(nome, v) for nome, v in eixos_in.items()}
    if not spec.get("variantes") and not eixos:
        raise GradeErro("A grade precisa de 'eixos' ou 'variantes' (senão há só uma combinação: use o app).")
    for nome in eixos:
        for k, v in enumerate(variantes, 1):
            if nome in v:
                raise GradeErro(f"O campo '{nome}' está em 'eixos' e na variante {k}: escolha um dos dois.")

    nomes = list(eixos)
    combos: list[Combinacao] = []
    for var in variantes:
        for vals in itertools.product(*(eixos[n] for n in nomes)):
            variaveis = {**var, **dict(zip(nomes, vals))}
            bruto = {**base, **variaveis}
            c = Combinacao(id=len(combos), variaveis=variaveis, params={})
            try:
                p = Params(**bruto)
            except ValidationError as exc:
                c.params = bruto
                c.erro = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            else:
                c.params = p.model_dump()
                c.chave = p.chave_motor()
            combos.append(c)

    janelas = spec.get("janelas") or {}
    if not isinstance(janelas, dict) or any(not (isinstance(v, list) and len(v) == 2) for v in janelas.values()):
        raise GradeErro("'janelas' deve ser {nome: [data_inicio, data_fim]} (AAAA-MM-DD, inclusive).")
    corte = spec.get("corte_oos", "2025-01-01")
    return Grade(
        nome=str(spec.get("nome") or "grade"), combinacoes=combos, corte_oos=corte,
        ordenar_por=str(spec.get("ordenar_por") or "ret_dd"), top=int(spec.get("top", 20)),
        min_operacoes=int(spec.get("min_operacoes", 30)), bd=spec.get("bd"), eixos=eixos, base_nome=base_nome,
        janelas={k: (str(v[0]), str(v[1])) for k, v in janelas.items()},
    )


def carregar(caminho: Path, estrategias_dir: Optional[Path] = None) -> Grade:
    try:
        spec = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GradeErro(f"Arquivo de grade não encontrado: {caminho}") from exc
    except json.JSONDecodeError as exc:
        raise GradeErro(f"JSON inválido em {caminho}: {exc}") from exc
    return expandir(spec, estrategias_dir)
