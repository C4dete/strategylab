"""Aplicação FastAPI: API em `/api` + o frontend compilado (`frontend/dist`) na raiz."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import paths
from .api.routes import router
from .services.dataset import CacheResultados, RegistroBD
from .services.strategies import EstrategiaStore


def _mensagem_validacao(exc: RequestValidationError) -> str:
    partes = []
    for e in exc.errors():
        msg = str(e.get("msg", "")).removeprefix("Value error, ")
        campo = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "params"))
        partes.append(f"{campo}: {msg}" if campo else msg)
    return "; ".join(partes) or "Dados inválidos."


def create_app(estrategias_dir: Optional[Path] = None, bd_padrao: Optional[Path] = None,
               frontend_dist: Optional[Path] = None, carregar_bd: bool = True) -> FastAPI:
    estrategias_dir = Path(estrategias_dir or paths.ESTRATEGIAS)
    bd_padrao = Path(bd_padrao or paths.BD_PADRAO)
    frontend_dist = Path(frontend_dist or paths.FRONTEND_DIST)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if carregar_bd:
            app.state.bd.iniciar()                 # o BD padrão carrega em segundo plano
        yield

    app = FastAPI(title="StrategyLab", version="0.1.0", lifespan=lifespan)
    app.state.estrategias = EstrategiaStore(estrategias_dir)
    app.state.bd = RegistroBD(bd_padrao)
    app.state.cache = CacheResultados()
    app.state.lock_execucao = threading.Lock()

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": _mensagem_validacao(exc)})

    app.include_router(router)

    index = frontend_dist / "index.html"
    if index.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        def spa(caminho: str):
            if caminho.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Rota não encontrada."})
            arquivo = (frontend_dist / caminho).resolve()
            if caminho and arquivo.is_file() and frontend_dist.resolve() in arquivo.parents:
                return FileResponse(arquivo)
            return FileResponse(index)

    return app
