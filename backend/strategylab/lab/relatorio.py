"""Tabela de resultados da grade: CSV (para o Excel pt-BR) + resumo em Markdown (para ler e para a IA reportar)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .grade import Grade
from .metricas import COLUNAS

_COLS_RESUMO = ["total_rs", "dd_rs", "ret_dd", "win_rate", "operacoes", "is_rs", "oos_rs", "oos_ret_dd"]


def tabela(grade: Grade, resultados: dict, representante: dict) -> pd.DataFrame:
    """Uma linha por combinação (inclusive inválidas): variáveis + métricas. `representante[id]` = id calculado de fato."""
    linhas = []
    nomes = grade.variaveis_nomes                                                       # tudo o que varia em ALGUMA combinação
    for c in grade.combinacoes:
        linha = {"id": c.id, **{k: c.params.get(k, c.variaveis.get(k)) for k in nomes}}   # valor EFETIVO (base + variável)
        if c.erro:
            linha.update(status="invalida", erro=c.erro)
        else:
            m = resultados[representante[c.id]]
            linha.update({k: v for k, v in m.items() if k not in ("status", "erro", "tempo_ms", "por_ano", "por_mes")})
            linha["status"] = m["status"]
            if m["status"] != "ok":
                linha["erro"] = m.get("erro", "")
            linha["motor_unico"] = representante[c.id]
            for ano, v in (m.get("por_ano") or {}).items():
                linha[f"rs_{ano}"] = v
            for mes, v in (m.get("por_mes") or {}).items():
                linha[f"m_{mes}"] = v
        linhas.append(linha)
    df = pd.DataFrame(linhas)
    fixas = ["id", "status"]
    variaveis = [k for k in nomes if k in df.columns]
    anos = sorted(k for k in df.columns if k.startswith("rs_"))
    extras = [k for k in df.columns if k not in fixas + variaveis + COLUNAS + anos + ["motor_unico", "erro"] and not k.startswith("m_")]
    meses = sorted(k for k in df.columns if k.startswith("m_"))
    ordem = fixas + variaveis + [k for k in COLUNAS if k in df.columns] + extras + anos + meses + [k for k in ("motor_unico", "erro") if k in df.columns]
    return df[ordem]


def _fmt(v, col: str) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    if isinstance(v, bool):
        return "sim" if v else "não"
    if col in ("ret_dd", "oos_ret_dd"):
        return f"{v:.2f}".replace(".", ",")
    if col == "win_rate":
        return f"{v:.1f}%".replace(".", ",")
    if isinstance(v, (int, float)) and col.endswith(("_rs", "rs")) or col in ("operacoes", "oos_operacoes"):
        return f"{v:,.0f}".replace(",", ".")
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def _md_tabela(df: pd.DataFrame, colunas: list) -> str:
    cab = "| " + " | ".join(colunas) + " |\n|" + "|".join("---" for _ in colunas) + "|\n"
    corpo = "".join("| " + " | ".join(_fmt(r[c], c) for c in colunas) + " |\n" for _, r in df.iterrows())
    return cab + corpo


def diagnosticos(df_ok: pd.DataFrame, corte_oos: Optional[str]) -> list:
    n = len(df_ok)
    linhas = [f"- Combinações com resultado: **{n}**. Limiar de significância (Bonferroni, 5% ÷ n): **{0.05 / n:.4f}**." if n else "- Nenhuma combinação válida."]
    if not n:
        return linhas
    linhas.append(f"- Com resultado total positivo: **{(df_ok['total_rs'] > 0).mean() * 100:.0f}%**.")
    if corte_oos and df_ok["oos_rs"].notna().any():
        linhas.append(f"- Com OOS (a partir de {corte_oos}) positivo: **{(df_ok['oos_rs'] > 0).mean() * 100:.0f}%**.")
        if n >= 5:
            rho = df_ok["is_rs"].rank().corr(df_ok["oos_rs"].rank())
            linhas.append(f"- Correlação de postos IS × OOS: **{rho:.2f}** (≈ 0 = escolher a melhor no IS não prevê o OOS).")
    return linhas


def escrever(grade: Grade, df: pd.DataFrame, meta: dict, pasta_base: Path) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", grade.nome.lower()).strip("-") or "grade"
    pasta = Path(pasta_base) / f"{datetime.now():%Y%m%d-%H%M%S}_{slug}"
    pasta.mkdir(parents=True, exist_ok=True)
    df.to_csv(pasta / "resultados.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    (pasta / "grade.json").write_text(json.dumps(meta["spec"], ensure_ascii=False, indent=2), encoding="utf-8")

    ok = df[df["status"] == "ok"]
    elegiveis = ok[ok["operacoes"] >= grade.min_operacoes]
    ordenar = grade.ordenar_por if grade.ordenar_por in df.columns else "ret_dd"
    ranque = elegiveis.sort_values(ordenar, ascending=False, na_position="last")
    variaveis = [c for c in df.columns if c in grade.variaveis_nomes]
    cols = ["id"] + variaveis + [c for c in _COLS_RESUMO if c in df.columns]
    md = [f"# Laboratório: {grade.nome}", ""]
    md += [f"- BD: `{meta['bd']}` · base: {grade.base_nome} · corte IS/OOS: {grade.corte_oos or 'desligado'}",
           f"- Combinações: **{len(df)}** (motores distintos calculados: **{meta['unicos']}**, inválidas: {int((df['status'] == 'invalida').sum())}, "
           f"com erro: {int((df['status'] == 'erro').sum())})",
           f"- Execução: {meta['workers']} processo(s), {meta['segundos']:.1f} s ({meta['por_segundo']:.1f} motores/s)",
           f"- Fidelidade: {meta['verificacao']}", ""]
    md += ["## Diagnósticos", ""] + diagnosticos(ok, grade.corte_oos) + [""]
    md += [f"## Top {min(grade.top, len(ranque))} por `{ordenar}` (mínimo {grade.min_operacoes} operações)", "",
           _md_tabela(ranque.head(grade.top), cols) if len(ranque) else "_Nenhuma combinação atende ao mínimo de operações._", ""]
    if len(ranque) > grade.top:
        md += [f"## Pior {min(5, len(ranque))}", "", _md_tabela(ranque.tail(5), cols), ""]
    md += ["Colunas completas (por ano, pior dia, soma dos 20 piores dias, meses positivos...) em `resultados.csv` "
           "(separador `;`, decimal `,`, UTF-8).", ""]
    (pasta / "resumo.md").write_text("\n".join(md), encoding="utf-8")
    return pasta


def tabela_console(grade: Grade, df: pd.DataFrame, top: int) -> str:
    ok = df[(df["status"] == "ok") & (df["operacoes"] >= grade.min_operacoes)]
    ordenar = grade.ordenar_por if grade.ordenar_por in df.columns else "ret_dd"
    ranque = ok.sort_values(ordenar, ascending=False, na_position="last").head(top)
    variaveis = [c for c in df.columns if c in grade.variaveis_nomes]
    cols = ["id"] + variaveis + [c for c in _COLS_RESUMO if c in df.columns]
    return _md_tabela(ranque, cols) if len(ranque) else "(nenhuma combinação atende ao mínimo de operações)"
