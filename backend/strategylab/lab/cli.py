"""Linha de comando do laboratório de combinações.

    python -m strategylab.lab grade.json                       # roda a grade (ver `docs/laboratorio.md`)
    python -m strategylab.lab --eixo reversoes=0,1,2 --eixo book=cont,ambas --nome teste
    python -m strategylab.lab grade.json --dry-run             # só conta as combinações e estima o tempo

A partir da raiz do projeto: `python -m strategylab.lab ...` com `PYTHONPATH=backend` (ou use `lab.bat`).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from .. import paths
from . import executor, grade as g, relatorio


def _valor(txt: str):
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return txt


def _spec_inline(args) -> dict:
    eixos = {}
    for e in args.eixo or []:
        nome, _, vals = e.partition("=")
        if not vals:
            raise g.GradeErro(f"--eixo '{e}': use campo=valor1,valor2,...")
        eixos[nome.strip()] = [_valor(v.strip()) for v in vals.split(",")]
    spec = {"nome": args.nome or "inline", "eixos": eixos}
    if args.base:
        spec["base"] = args.base
    return spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="strategylab.lab", description="Laboratório de combinações do StrategyLab (mesmo motor do app).")
    ap.add_argument("grade", nargs="?", help="arquivo JSON da grade")
    ap.add_argument("--eixo", action="append", help="eixo inline: campo=v1,v2,v3 (repetível)")
    ap.add_argument("--nome"), ap.add_argument("--base", help="estratégia salva (id ou nome) usada como base")
    ap.add_argument("--bd", help="CSV do BD (padrão: dados/WIN_1M_21_25.csv)")
    ap.add_argument("--workers", type=int, default=0, help="processos (padrão: núcleos − 1)")
    ap.add_argument("--saida", help="pasta dos resultados (padrão: lab_resultados/)")
    ap.add_argument("--cache-dir", help="pasta do cache do BD preparado (padrão: lab_cache/)")
    ap.add_argument("--top", type=int), ap.add_argument("--ordenar-por"), ap.add_argument("--corte-oos")
    ap.add_argument("--min-operacoes", type=int)
    ap.add_argument("--trades", type=int, default=0, help="grava os trades das N melhores combinações")
    ap.add_argument("--verificar", type=int, default=3, help="nº de combinações recalculadas pelo caminho do app (0 = não verificar)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        if args.grade:
            spec = json.loads(Path(args.grade).read_text(encoding="utf-8"))
        elif args.eixo:
            spec = _spec_inline(args)
        else:
            ap.error("informe o arquivo da grade ou ao menos um --eixo")
        for chave, val in (("nome", args.nome), ("top", args.top), ("ordenar_por", args.ordenar_por),
                           ("corte_oos", args.corte_oos), ("min_operacoes", args.min_operacoes), ("bd", args.bd)):
            if val is not None:
                spec[chave] = val
        grade = g.expandir(spec, paths.ESTRATEGIAS)
    except (g.GradeErro, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"ERRO na grade: {exc}", file=sys.stderr)
        return 2

    validas = [c for c in grade.combinacoes if not c.erro]
    unicos = {}
    representante = {}
    for c in validas:
        representante[c.id] = unicos.setdefault(c.chave, c.id)
    workers = args.workers or max(1, (os.cpu_count() or 2) - 1)
    print(f"Grade '{grade.nome}': {len(grade.combinacoes)} combinações ({len(validas)} válidas, {len(unicos)} motores distintos), "
          f"base: {grade.base_nome}.")
    if len(validas) < len(grade.combinacoes):
        for c in grade.combinacoes:
            if c.erro:
                print(f"  inválida #{c.id} {c.variaveis}: {c.erro}")
    if args.dry_run:
        print(f"Estimativa: ~{len(unicos) * 0.6 / max(1, workers):.0f} s com {workers} processo(s) (≈0,2–1,5 s por motor).")
        return 0
    if not unicos:
        print("Nenhuma combinação válida.", file=sys.stderr)
        return 2

    csv = Path(grade.bd) if grade.bd else paths.BD_PADRAO
    cache_dir = Path(args.cache_dir) if args.cache_dir else paths.RAIZ / "lab_cache"
    t0 = time.perf_counter()
    try:
        bd = executor.carregar_bd(csv, cache_dir)
    except Exception as exc:                                          # noqa: BLE001
        print(f"ERRO ao preparar o BD '{csv}': {exc}", file=sys.stderr)
        return 2
    print(f"BD: {bd.nome} ({'cache' if bd.do_cache else 'preparado'} em {time.perf_counter() - t0:.1f} s). Rodando com {workers} processo(s)...")

    ultimo = [0.0]

    def progresso(feitos: int, total: int, seg: float) -> None:
        if feitos == total or seg - ultimo[0] >= 10:
            ultimo[0] = seg
            falta = seg / feitos * (total - feitos) if feitos else 0
            print(f"  {feitos}/{total} motores · {feitos / max(seg, 1e-9):.1f}/s · faltam ~{falta:.0f} s", flush=True)

    t1 = time.perf_counter()
    lista = [(i, next(c.params for c in grade.combinacoes if c.id == i)) for i in unicos.values()]
    resultados = executor.executar_grade(lista, bd, grade.corte_oos, workers, progresso, grade.janelas)
    seg = time.perf_counter() - t1

    verificacao = "não verificada (--verificar 0)"
    if args.verificar > 0:
        problema = executor.checar_ancora(bd)
        rng = random.Random(7)
        ids = [i for i in unicos.values() if resultados[i].get("status") == "ok"]
        amostra_ids = ids if len(ids) <= args.verificar else rng.sample(ids, args.verificar)
        amostra = [(i, next(c.params for c in grade.combinacoes if c.id == i)) for i in amostra_ids]
        erros = ([problema] if problema else []) + executor.verificar(bd, amostra, resultados, grade.corte_oos)
        if erros:
            print("FALHA DE FIDELIDADE: a grade não bate com o caminho do app:", file=sys.stderr)
            for e in erros:
                print("  -", e, file=sys.stderr)
            return 3
        verificacao = (f"OK — {len(amostra)} combinação(ões) recalculada(s) pelo caminho do app, resultados idênticos"
                       + (" e cenário base = número-âncora (R$ 7.391 / 1.054)" if executor.ANCORA["sha1"] == bd.id else ""))
        print("Verificação:", verificacao)

    df = relatorio.tabela(grade, resultados, representante)
    pasta = relatorio.escrever(grade, df, {"spec": spec, "bd": bd.nome, "unicos": len(unicos), "workers": workers,
                                           "segundos": seg, "por_segundo": len(unicos) / max(seg, 1e-9),
                                           "verificacao": verificacao}, Path(args.saida) if args.saida else paths.RAIZ / "lab_resultados")
    if args.trades > 0:
        _gravar_trades(grade, df, bd, args.trades, pasta)
    ok = df[df["status"] == "ok"]
    print(f"\nTop {min(grade.top, len(ok))} por {grade.ordenar_por}:\n")
    print(relatorio.tabela_console(grade, df, min(grade.top, 15)))
    print(f"\nTempo da grade: {seg:.1f} s ({len(unicos) / max(seg, 1e-9):.1f} motores/s). Resultados em: {pasta}")
    return 0


def _gravar_trades(grade, df, bd, n, pasta) -> None:
    from ..engine.params import Params
    from ..engine.runner import preparar_mercado, rodar_trades

    ok = df[df["status"] == "ok"].sort_values(grade.ordenar_por if grade.ordenar_por in df.columns else "ret_dd", ascending=False).head(n)
    mercado = preparar_mercado(bd.barras, bd.sub_min)
    for _, linha in ok.iterrows():
        c = next(c for c in grade.combinacoes if c.id == int(linha["id"]))
        tr = rodar_trades(None, Params(**c.params), bd.sub_min, mercado)
        tr.to_csv(pasta / f"trades_{c.id}.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    sys.exit(main())
