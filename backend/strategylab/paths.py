"""Caminhos do projeto. A raiz é a pasta que contém `backend/`, `frontend/`, `dados/` e `estrategias/`."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "dados"
ESTRATEGIAS = RAIZ / "estrategias"
FRONTEND_DIST = RAIZ / "frontend" / "dist"

BD_PADRAO = DADOS / "WIN_1M_21_25.csv"

# HOLD-OUT DO RICARDO: dados depois desta data são a validação final dele e NUNCA entram em pesquisa (laboratório, diagnósticos,
# conferências). A trava em `lab/executor.py::carregar_bd` recusa qualquer CSV com data posterior. Não há opção para desligá-la.
DATA_LIMITE_PESQUISA = "2025-12-31"
