"""Rotas da API (`/api/*`). Os serviços ficam em `request.app.state`."""

from __future__ import annotations

from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..engine import data as dados
from ..engine.params import EXECUCAO, Params, params_padrao
from ..engine.portfolio import combinar
from ..engine.runner import executar, meses_do_bd
from ..services.dataset import BD
from ..services.strategies import Estrategia, EstrategiaErro
from . import schemas as s

router = APIRouter(prefix="/api")

LIMITE_UPLOAD = 300 * 1024 * 1024


# ----------------------------------------------------------------------------- helpers
def _estr_out(e: Estrategia) -> s.EstrategiaOut:
    return s.EstrategiaOut(id=e.id, nome=e.name, atualizada_em=e.updated_at,
                           valida=e.valida, erro=e.erro, params=e.params)


def _bd_out(reg, bd: Optional[BD]) -> s.BDOut:
    if bd is None:
        return s.BDOut(estado=reg.estado, erro=reg.erro)
    i = bd.info
    return s.BDOut(estado="pronto", id=bd.id, nome=bd.nome, padrao=bd.padrao, linhas=i.linhas,
                   pregoes=i.pregoes, inicio=i.inicio, fim=i.fim, timeframe_min=i.timeframe_min,
                   avisos=i.avisos)


def _erro(exc: EstrategiaErro) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


# ----------------------------------------------------------------------------- meta
@router.get("/meta")
def meta():
    """O que é fixo nesta etapa + os limites dos campos (a UI lê daqui)."""
    esquema = Params.model_json_schema()["properties"]

    def faixa(campo: str) -> dict:
        p = esquema[campo]
        return {"min": p.get("minimum"), "max": p.get("maximum")}

    return {
        "execucao": {
            "ativo": EXECUCAO.ativo, "descricao_ativo": EXECUCAO.descricao_ativo, "perfil": EXECUCAO.perfil,
            "valor_ponto": EXECUCAO.valor_ponto, "contratos": EXECUCAO.contratos,
            "timeframe_min": EXECUCAO.timeframe_min, "leitura_min": EXECUCAO.leitura_min,
            "slippage_pts": EXECUCAO.slippage_pts, "spread_pts": EXECUCAO.spread_pts,
            "tick_pts": EXECUCAO.tick_pts, "entrada": EXECUCAO.entrada,
        },
        "faixas": {c: faixa(c) for c in (
            "candles_gatilho", "candles_media", "bracket_fracao", "penetracao_ticks",
            "parar_apos_losses", "operacoes_por_dia", "stop_x_media", "alvo_x_media",
            "mm_periodo", "bb_periodo", "bb_desvio", "filtro_afast_mm_x_media",
            "reversoes", "rev_stop_x_media", "rev_alvo_x_media", "parar_dia_perda_x_media", "tempo_max_min",
            "filtro_gap_max_x_media", "filtro_vol_ontem_max", "filtro_bb_largura_min_pct", "filtro_bb_largura_max_pct",
            "filtro_inclinacao_barras", "filtro_inclinacao_max_x_media", "filtro_candle_discrepante_x", "trailing_inicio_r",
            "escada_contratos", "escada_ganho_qtd", "escada_perda_qtd", "escada_min", "escada_max")},
        "padrao": params_padrao().model_dump(),
        "capacidades": {"correlacao": True},          # a interface detecta servidor antigo por aqui
    }


# ----------------------------------------------------------------------------- BD
@router.get("/dataset", response_model=s.BDOut)
def dataset(request: Request):
    reg = request.app.state.bd
    return _bd_out(reg, reg.ativo())


@router.post("/dataset", response_model=s.BDOut)
async def enviar_dataset(request: Request, arquivo: UploadFile = File(...)):
    reg = request.app.state.bd
    conteudo = await arquivo.read(LIMITE_UPLOAD + 1)
    if len(conteudo) > LIMITE_UPLOAD:
        raise HTTPException(413, "Arquivo grande demais (limite de 300 MB).")
    if not conteudo:
        raise HTTPException(422, "O arquivo está vazio.")
    try:
        bd = await run_in_threadpool(reg.carregar_upload, arquivo.filename or "arquivo.csv", conteudo)
    except dados.DadosInvalidos as exc:
        raise HTTPException(422, str(exc)) from exc
    return _bd_out(reg, bd)


@router.post("/dataset/reset", response_model=s.BDOut)
def voltar_padrao(request: Request):
    reg = request.app.state.bd
    try:
        return _bd_out(reg, reg.voltar_padrao())
    except dados.DadosInvalidos as exc:
        raise HTTPException(503, str(exc)) from exc


# ----------------------------------------------------------------------------- estratégias
@router.get("/strategies", response_model=s.ListaEstrategias)
def listar(request: Request):
    store = request.app.state.estrategias
    itens = store.listar()
    ultima = store.ultima()
    if ultima not in {e.id for e in itens}:
        ultima = next((e.id for e in itens if e.valida), None)
    return s.ListaEstrategias(estrategias=[_estr_out(e) for e in itens], ultima=ultima,
                              correlacionar=store.correlacionar())


@router.post("/strategies", response_model=s.EstrategiaOut, status_code=201)
def criar(request: Request, corpo: s.NovaEstrategia):
    try:
        return _estr_out(request.app.state.estrategias.criar(corpo.nome, corpo.params))
    except EstrategiaErro as exc:
        raise _erro(exc) from exc


@router.put("/strategies/{id_}", response_model=s.EstrategiaOut)
def salvar(request: Request, id_: str, corpo: s.SalvarParams):
    try:
        return _estr_out(request.app.state.estrategias.salvar(id_, corpo.params))
    except EstrategiaErro as exc:
        raise _erro(exc) from exc


@router.patch("/strategies/{id_}", response_model=s.EstrategiaOut)
def renomear(request: Request, id_: str, corpo: s.Renomear):
    try:
        return _estr_out(request.app.state.estrategias.renomear(id_, corpo.nome))
    except EstrategiaErro as exc:
        raise _erro(exc) from exc


@router.delete("/strategies/{id_}", status_code=204)
def excluir(request: Request, id_: str):
    try:
        request.app.state.estrategias.excluir(id_)
    except EstrategiaErro as exc:
        raise _erro(exc) from exc


@router.put("/estado/correlacionar")
def definir_correlacionar(request: Request, corpo: s.Correlacionar):
    try:
        return {"ids": request.app.state.estrategias.definir_correlacionar(corpo.id, corpo.ids)}
    except EstrategiaErro as exc:
        raise _erro(exc) from exc


@router.put("/estado/ultima", status_code=204)
def definir_ultima(request: Request, corpo: s.Ultima):
    try:
        request.app.state.estrategias.definir_ultima(corpo.id)
    except EstrategiaErro as exc:
        raise _erro(exc) from exc


# ----------------------------------------------------------------------------- backtest
def _bd_pronto(app):
    if not app.bd.aguardar():
        raise HTTPException(503, "O BD ainda está carregando. Tente de novo em instantes.")
    bd = app.bd.ativo()
    if bd is None:
        raise HTTPException(503, app.bd.erro or "Nenhum BD disponível.")
    return bd


def _resultado(app, bd, params: Params) -> tuple[dict, bool]:
    """Backtest de uma estratégia, com cache por (BD, parâmetros do motor). Devolve (resultado, veio_do_cache)."""
    chave = (bd.id, params.chave_motor())
    res = app.cache.obter(chave)
    if res is not None:
        return res, True
    with app.lock_execucao:                           # uma execução pesada por vez
        res = app.cache.obter(chave)
        if res is not None:
            return res, True
        res = executar(bd.barras, params, bd.sub_min, bd.mercado())
        app.cache.guardar(chave, res)
        return res, False


@router.post("/backtest")
def backtest(request: Request, corpo: s.BacktestIn):
    app = request.app.state
    bd = _bd_pronto(app)
    res, em_cache = _resultado(app, bd, corpo.params)
    return {**res, "em_cache": em_cache, "bd": _bd_out(app.bd, bd).model_dump(),
            "params": corpo.params.model_dump()}


@router.post("/portfolio")
def portfolio(request: Request, corpo: s.PortfolioIn):
    """Resultado conjunto: soma, pregão a pregão, de backtests independentes (ver `engine/portfolio.py`). A 1ª é a principal."""
    app = request.app.state
    bd = _bd_pronto(app)
    componentes, tudo_em_cache = [], True
    for c in corpo.componentes:
        try:
            res, em_cache = _resultado(app, bd, c.params)
        except Exception as exc:                      # noqa: BLE001 - diz QUAL estratégia falhou
            raise HTTPException(422, f"Não foi possível executar “{c.nome}”: {exc}") from exc
        tudo_em_cache = tudo_em_cache and em_cache
        componentes.append({"nome": c.nome, "res": res})
    mercado = bd.mercado()
    conj = combinar(componentes, datas_bd=list(mercado.feat), meses_bd=meses_do_bd(mercado))
    return {**conj, "em_cache": tudo_em_cache, "bd": _bd_out(app.bd, bd).model_dump(),
            "params": corpo.componentes[0].params.model_dump()}


@router.get("/dia/{dia}")
def dia_detalhe(request: Request, dia: str, mm: Optional[int] = None, bb: Optional[int] = None,
                k: Optional[float] = None):
    """Barras do pregão. Com `mm`, `bb` e `k` (períodos e desvio) devolve também os indicadores no fechamento de cada barra."""
    app = request.app.state
    bd = app.bd.ativo()
    if bd is None:
        raise HTTPException(503, "Nenhum BD disponível.")
    try:
        d = _date.fromisoformat(dia)
    except ValueError as exc:
        raise HTTPException(422, "Data inválida (use AAAA-MM-DD).") from exc
    indicadores = (mm, bb, k) if mm and bb and k else None
    if indicadores and not (2 <= mm <= 200 and 2 <= bb <= 200 and 0.5 <= k <= 5):
        raise HTTPException(422, "Períodos entre 2 e 200 e desvio entre 0,5 e 5.")
    barras = app.bd.barras_do_dia(bd, d, indicadores)
    if not barras:
        raise HTTPException(404, "Não há candles neste dia no BD ativo.")
    return {"data": dia, "barras": barras}
