"""Roda a bateria de testes em PARALELO, no tamanho certo para a mudança feita (ver docs/testes.md).

    python backend/scripts/testes.py <perfil> [--workers N] [--duracoes]
    python backend/scripts/testes.py --lista

Perfis (do mais barato ao mais completo): fronteira, parametro, regra, completo.
Cada perfil lista o que roda; a decisão de qual usar está na tabela de docs/testes.md.
Sem dependência extra: divide os testes em processos do próprio pytest (prioridade abaixo do normal, o PC continua usável).
Neste PC o ganho de paralelizar satura em ~2,5x (medido): o ganho grande vem de escolher o perfil certo, não de mais processos.
Termina com código 1 se qualquer teste falhar. A paridade com o motor antigo roda junto nos perfis que a pedem.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"
BAIXA = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS (Windows)
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}   # filhos imprimem UTF-8 (acentos)

# Arquivos que NÃO exercitam a regra do motor: validação, API, persistência, métricas, laboratório (parte rápida).
PERIFERIA = ["tests/test_params_metrics.py", "tests/test_api.py", "tests/test_store.py", "tests/test_data.py", "tests/test_indicators.py"]

# Temas afetados -> expressão -k (casa com o nome do cenário nos testes de oráculo/golden/look-ahead no BD real). ASCII de propósito.
TEMAS = {
    "proximo_candle": "candle",
    "sair_mm": "sair",
    "rastrear": "rastrear",
    "reversoes": "revers",
    "escada": "escada or contrato",
    "filtro_afast": "filtro or afastamento",
    "book": "book",
    "penetracao": "penetra",
    "gestao": "ops or stop or parar or alvo",     # operações/dia, stop, alvo, parar por losses
    "janela": "janela or ltima or sem_ult or sem ultima",
    "zona": "zona or gatilho or janela",
    "laboratorio": "laboratorio",
}
# Canários: rodam SEMPRE no BD real (um por camada) mesmo que o tema não os cubra; a lista fixa o que "nada quebrou" significa.
CANARIOS = [
    "tests/test_golden.py::test_inicial_default_resumo_completo",
    "tests/test_golden.py::test_controles_novos_desligados_nao_mudam_o_cenario_base",
    "tests/test_golden.py::test_cenario_identico_ao_motor_antigo[base]",
    "tests/test_lab.py::test_laboratorio_reproduz_os_numeros_ancora_no_bd_real",
    "tests/test_sem_lookahead.py::test_futuro_destruido_nao_muda_as_entradas_no_bd_real[filtro ligado, book cont]",
]
NAO_CARTESIANO = ["--deselect", "tests/test_combinacoes.py::test_todas_as_combinacoes",
                  "--deselect", "tests/test_combinacoes.py::test_toda_a_matriz_de_regime"]

PERFIS = {
    # só interface/texto/documentação: nenhum teste de backend; rode os checks do frontend (docs/testes.md)
    "fronteira": dict(
        descricao="backend: só validação, API, persistência e métricas (periferia, sem motor)",
        args=[["-m", "not lento", *PERIFERIA]], paridade=False),
    # campo/faixa/validação/lista de parâmetros sem mudar regra: periferia + motor rápido (unidade, oráculo e look-ahead sintéticos) + paridade
    "parametro": dict(
        descricao="rápida completa (unidade, oráculo e look-ahead sintéticos, amostra da matriz) + paridade com o motor antigo",
        args=[["-m", "not lento"]], paridade=True),
    # regra nova/alterada no motor: rápida + no BD real SÓ os cenários dos temas afetados (--afeta) + canários, SEM o produto cartesiano
    "regra": dict(
        descricao="rápida + BD real só nos temas afetados (--afeta) e nos canários + paridade; sem o produto cartesiano das matrizes",
        args=[["-m", "not lento"]], paridade=True, afeta=True),
    # núcleo (fills, preparar_dia, runner, chave_motor, métricas do motor) ou antes de entregar etapa: tudo, inclusive as matrizes completas
    "completo": dict(
        descricao="tudo, incluindo o produto cartesiano das matrizes (7.200 + 288) + paridade",
        args=[["-m", "not lento"], ["-m", "lento"]], paridade=True),
}


def coletar(args: list[str]) -> list[str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
                       cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [ln.strip() for ln in r.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))]


# Peso estimado (s, serial) por família de teste; o que não está aqui vale ~PESO_PADRAO (a rápida: ~250 s / 469 testes).
# Os valores repartem os 45 min seriais da bateria lenta na proporção medida; revise se algo ficar bem mais pesado.
PESO_PADRAO = 0.55
PESOS = [
    ("test_todas_as_combinacoes", 170.0), ("test_toda_a_matriz_de_regime", 20.0),
    ("test_motor_confere_com_o_simulador_independente_no_bd_real", 85.0), ("test_filtro_afastamento_confere_com_o_simulador_independente", 50.0),
    ("test_confere_com_o_simulador_independente", 50.0), ("test_cenario_identico_ao_motor_antigo", 13.0),
    ("test_modos_da_etapa_3_numeros_ancora", 13.0), ("_no_bd_real", 17.0), ("test_laboratorio_reproduz", 17.0),
    ("test_inicial_default_resumo_completo", 13.0), ("test_controles_novos_desligados", 13.0),
    ("test_motor_confere_com_o_simulador_independente_nos_dados_sinteticos", 5.0), ("test_regime_e_cauda_conferem", 5.0),
]


def peso(i: str) -> float:
    return next((w for k, w in PESOS if k in i), PESO_PADRAO)


def tarefas(ids: list[str], alvo: float = 40.0) -> list[list[str]]:
    """Pesados rodam sozinhos (cada processo paga a carga do BD uma vez); os leves são agrupados em pacotes de ~`alvo` s.
    Ordem decrescente de peso: o relógio total fica perto do maior pesado ou do (peso total / processos)."""
    pesados = sorted((i for i in ids if peso(i) >= alvo), key=lambda i: -peso(i))
    pacotes, atual, acc = [], [], 0.0
    for i in sorted((i for i in ids if peso(i) < alvo), key=lambda i: (i.split("::")[0], i)):
        atual.append(i)
        acc += peso(i)
        if acc >= alvo:
            pacotes.append(atual)
            atual, acc = [], 0.0
    if atual:
        pacotes.append(atual)
    return [[i] for i in pesados] + pacotes


def rodar_pytest(ids: list[str], saida: Path) -> tuple[int, str]:
    """Saída vai para ARQUIVO (um pipe cheio travaria o processo filho até alguém ler)."""
    with open(saida, "w", encoding="utf-8", errors="replace") as f:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--durations=0", *ids], cwd=BACKEND,
                           stdout=f, stderr=subprocess.STDOUT, env=ENV, creationflags=BAIXA if os.name == "nt" else 0)
    return p.returncode, saida.read_text(encoding="utf-8", errors="replace")


def rodar_paridade(saida: Path) -> tuple[int, str]:
    with open(saida, "w", encoding="utf-8", errors="replace") as f:
        p = subprocess.run([sys.executable, str(BACKEND / "scripts" / "paridade_motor_antigo.py")], cwd=RAIZ, stdout=f,
                           stderr=subprocess.STDOUT, env=ENV, creationflags=BAIXA if os.name == "nt" else 0)
    return p.returncode, saida.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perfil", nargs="?", choices=list(PERFIS))
    ap.add_argument("--workers", type=int, default=3, help="processos simultâneos (neste PC o ganho satura em ~2,5x)")
    ap.add_argument("-k", dest="k", default=None, help="só os testes cujo nome casa com a expressão do pytest (-k), dentro do perfil")
    ap.add_argument("--afeta", default=None, help=f"(perfil regra) temas afetados, separados por vírgula: {', '.join(TEMAS)} ou 'todos' (todo o BD real, sem matrizes)")
    ap.add_argument("--listar", action="store_true", help="só mostra o que rodaria e o tempo estimado; não executa")
    ap.add_argument("--sem-paridade", action="store_true", help="pula a paridade com o motor antigo")
    ap.add_argument("--duracoes", action="store_true", help="imprime os testes mais lentos")
    ap.add_argument("--lista", action="store_true", help="lista os perfis")
    a = ap.parse_args()
    if a.lista or not a.perfil:
        for nome, p in PERFIS.items():
            print(f"{nome:10s} {p['descricao']}")
        return 0

    perfil = PERFIS[a.perfil]
    ids: list[str] = []
    for sel in perfil["args"]:
        ids += [i for i in coletar([*sel, *(["-k", a.k] if a.k else [])]) if i not in ids]
    if perfil.get("afeta"):
        if not a.afeta:
            print("perfil 'regra': informe --afeta com os temas tocados (ex.: --afeta reversoes,rastrear). "
                  f"Temas: {', '.join(TEMAS)}; 'todos' = todo o BD real (sem as matrizes).")
            return 2
        nomes = [t.strip() for t in a.afeta.split(",") if t.strip()]
        ruim = [t for t in nomes if t != "todos" and t not in TEMAS]
        if ruim:
            print(f"tema(s) desconhecido(s): {', '.join(ruim)}. Válidos: {', '.join(TEMAS)}, todos")
            return 2
        if "todos" in nomes:
            lentos = coletar(["-m", "lento", *NAO_CARTESIANO])
        else:
            expr = " or ".join(f"({TEMAS[t]})" for t in nomes)
            lentos = coletar(["-m", "lento", *NAO_CARTESIANO, "-k", expr])
            lentos += [c for c in CANARIOS if c not in lentos]
        ids += [i for i in lentos if i not in ids]
    if not ids:
        print("nenhum teste selecionado")
        return 1
    fila = tarefas(ids)
    if a.listar:
        est = sum(peso(i) for i in ids)
        print(f"perfil '{a.perfil}': {len(ids)} testes, ~{est / 60:.0f} min de CPU estimados (~{est / 60 / 2.5:.0f} min no relógio com paralelismo)")
        for i in sorted(ids, key=lambda i: -peso(i))[:40]:
            if peso(i) > PESO_PADRAO:
                print(f"  ~{peso(i):5.0f}s  {i}")
        return 0
    com_paridade = perfil["paridade"] and not a.sem_paridade and not a.k
    workers = min(a.workers, len(fila) + int(com_paridade))
    print(f"perfil '{a.perfil}': {len(ids)} testes em {len(fila)} tarefas, {workers} processos simultâneos"
          f"{' + paridade' if com_paridade else ''}", flush=True)

    tmp = RAIZ / "lab_cache" / "_testes"
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    falhas, duracoes, resumos = 0, [], []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(rodar_paridade, tmp / "paridade.log")] if com_paridade else []
        futs += [ex.submit(rodar_pytest, t, tmp / f"t{k:03d}.log") for k, t in enumerate(fila)]
        for k, f in enumerate(futs):
            rc, out = f.result()
            if com_paridade and k == 0:
                ok = rc == 0 and "TODOS IDÊNTICOS" in out
                print(f"paridade com o motor antigo: {'TODOS IDÊNTICOS' if ok else 'DIVERGÊNCIA'}")
                if not ok:
                    falhas += 1
                    print(out[-3000:])
                continue
            resumos.append(next((ln for ln in reversed(out.splitlines()) if re.match(r"^(=+ )?\d+ (passed|failed|error)", ln)), "?"))
            if rc != 0:
                falhas += 1
                print(f"--- tarefa {k} falhou ---")
                print(out[-4000:])
            duracoes += [(float(m.group(1)), m.group(2).strip()) for ln in out.splitlines() if (m := re.match(r"\s*([\d.]+)s call\s+(.*)", ln))]
    total = sum(int(m.group(1)) for r in resumos if (m := re.search(r"(\d+) passed", r)))
    print(f"{total} testes passaram, {falhas} falha(s), {time.time() - t0:.0f}s no relógio")
    if a.duracoes:
        for d, nome in sorted(duracoes, reverse=True)[:25]:
            print(f"{d:7.1f}s  {nome}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
