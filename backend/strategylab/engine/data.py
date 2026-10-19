"""Leitura, validação e preparação do BD de candles.

Formato aceito (o mesmo do BD padrão): `CANDLE;OPEN;HIGH;LOW;CLOSE;VFIN;VNEG`, separador `;`,
data `dd/mm/aaaa hh:mm`, ordem qualquer (é ordenado). `VFIN`/`VNEG` são opcionais e não são usadas.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List

import pandas as pd

_RENAME = {
    "CANDLE": "candle", "OPEN": "open", "HIGH": "high", "MAX": "high",
    "LOW": "low", "MIN": "low", "CLOSE": "close",
}
_OHLC = ("open", "high", "low", "close")
_DATE_FORMAT = "%d/%m/%Y %H:%M"
_MIN_CANDLES = 100
_MIN_PREGOES = 5
_TOLERANCIA_INCOERENTE = 0.01      # acima de 1% de candles com OHLC impossível, o arquivo é recusado


class DadosInvalidos(ValueError):
    """BD fora do padrão. A mensagem é exibida ao usuário."""


@dataclass
class InfoBD:
    linhas: int
    pregoes: int
    inicio: str
    fim: str
    timeframe_min: int
    avisos: List[str] = field(default_factory=list)


def _ler_texto(origem) -> pd.DataFrame:
    if isinstance(origem, (bytes, bytearray)):
        origem = io.BytesIO(origem)
    try:
        df = pd.read_csv(origem, sep=";", dtype=str, encoding="utf-8-sig", skip_blank_lines=True)
    except UnicodeDecodeError:
        if hasattr(origem, "seek"):
            origem.seek(0)
        df = pd.read_csv(origem, sep=";", dtype=str, encoding="latin-1", skip_blank_lines=True)
    except pd.errors.EmptyDataError as exc:
        raise DadosInvalidos("O arquivo está vazio.") from exc
    except pd.errors.ParserError as exc:
        raise DadosInvalidos(f"Não foi possível ler o arquivo como CSV separado por ';': {exc}") from exc
    return df


def carregar_csv(origem) -> tuple[pd.DataFrame, List[str]]:
    """Lê e valida o CSV. Devolve (candles, avisos). Levanta `DadosInvalidos` em português."""
    df = _ler_texto(origem)
    avisos: List[str] = []

    df.columns = [str(c).strip().upper() for c in df.columns]
    df = df.rename(columns=_RENAME)
    faltam = [c for c in ("candle", *_OHLC) if c not in df.columns]
    if faltam:
        raise DadosInvalidos(
            "Cabeçalho fora do padrão: faltam as colunas "
            f"{', '.join(c.upper() for c in faltam)}. Esperado: CANDLE;OPEN;HIGH;LOW;CLOSE;VFIN;VNEG."
        )

    # Linhas totalmente vazias (ex.: ";;;;;;" no fim de arquivos exportados) não são dados.
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty:
        raise DadosInvalidos("O arquivo não tem nenhum candle.")

    df["datetime"] = pd.to_datetime(df["candle"].str.strip(), format=_DATE_FORMAT, errors="coerce")
    ruins = df["datetime"].isna()
    if ruins.any():
        linha = int(ruins.idxmax()) + 2          # +1 do cabeçalho, +1 por ser 1-based
        exemplo = df.loc[ruins.idxmax(), "candle"]
        raise DadosInvalidos(
            f"{int(ruins.sum())} data(s) fora do formato dd/mm/aaaa hh:mm "
            f"(primeira na linha {linha}: {exemplo!r})."
        )

    for col in _OHLC:
        s = df[col].astype(str).str.strip().str.replace(",", ".", regex=False)
        df[col] = pd.to_numeric(s, errors="coerce")

    ruins = df[list(_OHLC)].isna().any(axis=1)
    if ruins.any():
        linha = int(ruins.idxmax()) + 2
        raise DadosInvalidos(
            f"{int(ruins.sum())} candle(s) com preço ilegível em OPEN/HIGH/LOW/CLOSE "
            f"(primeiro na linha {linha}). Os preços devem ser números, com ponto ou vírgula decimal."
        )

    df = df.sort_values("datetime").reset_index(drop=True)

    dup = df["datetime"].duplicated(keep="last")
    if dup.any():
        avisos.append(f"{int(dup.sum())} candle(s) com horário repetido foram descartados (ficou o último).")
        df = df.loc[~dup].reset_index(drop=True)

    incoerente = (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    )
    if incoerente.any():
        frac = float(incoerente.mean())
        if frac > _TOLERANCIA_INCOERENTE:
            raise DadosInvalidos(
                f"{int(incoerente.sum())} candles ({frac:.1%}) têm máxima/mínima incoerente com abertura/fechamento. "
                "O arquivo parece corrompido ou com separador numérico errado."
            )
        avisos.append(f"{int(incoerente.sum())} candle(s) com máxima/mínima incoerente (mantidos).")

    df["date"] = df["datetime"].dt.date
    if len(df) < _MIN_CANDLES or df["date"].nunique() < _MIN_PREGOES:
        raise DadosInvalidos(
            f"Poucos dados: {len(df)} candles em {df['date'].nunique()} pregão(ões). "
            f"São necessários pelo menos {_MIN_CANDLES} candles em {_MIN_PREGOES} pregões."
        )

    keep = ["datetime", "open", "high", "low", "close", "date"]
    return df[keep], avisos


def timeframe_base_min(df: pd.DataFrame) -> int:
    """Timeframe da série em minutos, inferido da mediana das diferenças DENTRO de cada pregão."""
    if len(df) < 3:
        return 0
    d = df.sort_values("datetime")
    dif = d.groupby(d["datetime"].dt.date)["datetime"].diff().dt.total_seconds()
    dif = dif[dif > 0]
    if dif.empty:
        return 0
    return max(1, int(round(float(dif.median()) / 60.0)))


def informacoes(df: pd.DataFrame, avisos: List[str]) -> InfoBD:
    return InfoBD(
        linhas=int(len(df)),
        pregoes=int(df["date"].nunique()),
        inicio=str(df["datetime"].iloc[0].date()),
        fim=str(df["datetime"].iloc[-1].date()),
        timeframe_min=timeframe_base_min(df),
        avisos=list(avisos),
    )


def _agrega(df: pd.DataFrame, minutos: int) -> pd.DataFrame:
    d = df.set_index("datetime").sort_index()
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    out = (d.resample(f"{minutos}min", label="left", closed="left")
           .agg(agg).dropna(subset=["open"]).reset_index())
    out["date"] = out["datetime"].dt.date
    return out


def _anexa_subbarras(barras: pd.DataFrame, bruto: pd.DataFrame, minutos: int, sub: int) -> pd.DataFrame:
    """Anexa a cada barra os sub-candles de `sub` minutos que a formam (colunas so/sh/sl/sc{k})."""
    n_sub = minutos // sub
    r = bruto.sort_values("datetime").copy()
    r["_b"] = r["datetime"].dt.floor(f"{minutos}min")
    r["_k"] = ((r["datetime"] - r["_b"]).dt.total_seconds() // (sub * 60)).astype(int)
    out = barras.copy()
    for k in range(n_sub):
        parte = r[r["_k"] == k].set_index("_b")[["open", "high", "low", "close"]]
        parte.columns = [f"so{k}", f"sh{k}", f"sl{k}", f"sc{k}"]
        out = out.merge(parte, left_on="datetime", right_index=True, how="left")
    return out


def preparar_barras(df: pd.DataFrame, timeframe_min: int) -> tuple[pd.DataFrame, int]:
    """Barras do timeframe da estratégia + sub-candles na melhor resolução do arquivo.

    Devolve (barras, sub_min). Levanta `DadosInvalidos` se o arquivo não permite ler a execução por
    sub-candles (a resolução do arquivo precisa dividir o timeframe).
    """
    base = timeframe_base_min(df)
    if base <= 0:
        raise DadosInvalidos("Não foi possível identificar o timeframe do arquivo.")
    if base >= timeframe_min or timeframe_min % base != 0:
        raise DadosInvalidos(
            f"O arquivo tem candles de {base} min. O StrategyLab precisa de candles de 1, 2 ou 5 min "
            f"(que dividam {timeframe_min} min); o recomendado é 1 min."
        )
    barras = _agrega(df, timeframe_min)
    barras = _anexa_subbarras(barras, df, timeframe_min, base)
    return barras, base
