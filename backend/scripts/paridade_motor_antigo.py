"""Paridade: o motor novo precisa gerar EXATAMENTE os mesmos trades do motor antigo (ghostcandle_v6).

Uso (a partir da raiz do projeto):
    python backend/scripts/paridade_motor_antigo.py [caminho_do_csv]

O motor antigo vive em `base_conhecimento/` e só é importado aqui (script de desenvolvimento).
As funcionalidades que o painel não expõe (trailing, filtro3, amplitude mínima, ORB, VWAP...)
ficam DESLIGADAS no motor antigo, que é a única configuração comparável.
Imprime uma linha por cenário e termina com código 1 se houver qualquer divergência.
"""

from __future__ import annotations

import sys
import time as T
from datetime import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
sys.path.insert(0, str(RAIZ / "base_conhecimento"))

from ghostcandle.backtest import run_backtest                                   # noqa: E402
from ghostcandle.config import StrategyParams                                   # noqa: E402
from ghostcandle.io_csv import load_candles, resample_ohlc                      # noqa: E402

from strategylab.engine import data as dados                                    # noqa: E402
from strategylab.engine.params import Params, hhmm_para_min                     # noqa: E402
from strategylab.engine.runner import rodar_trades                              # noqa: E402

CENARIOS = {
    "base (inicial_default)": {},
    "book ambas": dict(book="ambas"),
    "book recuo": dict(book="recuo"),
    "book acima": dict(book="acima"),
    "book abaixo": dict(book="abaixo"),
    "penetracao 0": dict(penetracao_ticks=0),
    "penetracao 3": dict(penetracao_ticks=3),
    "5 ops, parar 2 (dia)": dict(operacoes_por_dia=5, parar_apos_losses=2),
    "5 ops, parar 2 (seguidos)": dict(operacoes_por_dia=5, parar_apos_losses=2, contagem_losses="seguidos"),
    "3 ops, stop 0,5, alvo 1,5": dict(operacoes_por_dia=3, stop_x_media=0.5, alvo_x_media=1.5),
    "janela 09:30-16:30, ult. 15:00, gat 8, media 3, k 0,3": dict(
        janela_inicio="09:30", janela_fim="16:30", ultima_entrada="15:00",
        candles_gatilho=8, candles_media=3, bracket_fracao=0.3, operacoes_por_dia=2),
    "sem ult. entrada, stop 2, alvo 6, book ambas": dict(
        ultima_entrada=None, stop_x_media=2.0, alvo_x_media=6.0, book="ambas", operacoes_por_dia=2),
    # Zona de 1 candle (só a máxima/mínima da barra anterior)
    "gatilho 1 candle": dict(candles_gatilho=1),
    "gatilho 1 candle, média 2, ambas, 3 ops, 2 reversões": dict(candles_gatilho=1, candles_media=2, book="ambas", operacoes_por_dia=3, reversoes=2),
    # Candle discrepante (malibu_vol_discard_mult do sistema antigo): o maior da janela > X x o 2o maior sai da media_operacao
    "candle discrepante 2,0 (regra do sistema antigo)": dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=2.0),
    "candle discrepante 1,5, média 8, 2 ops": dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.5, candles_media=8,
                                                  operacoes_por_dia=2),
    "candle discrepante 1,2 + 2 reversões, ambas": dict(filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.2, reversoes=2, book="ambas",
                                                       operacoes_por_dia=3),
    # Trailing stop (ghost_trail_start_r do sistema antigo): arma ao avancar X x risco; segue a minima/maxima da barra fechada
    "trailing 1,6 (o da v6)": dict(trailing_inicio_r=1.6),
    "trailing 0,5, 3 ops, stop 1,5 / alvo 4": dict(trailing_inicio_r=0.5, operacoes_por_dia=3, stop_x_media=1.5, alvo_x_media=4.0),
    "trailing 1,0 + 2 reversões (stop 0,7 / alvo 2), ambas": dict(trailing_inicio_r=1.0, reversoes=2, rev_stop_x_media=0.7, rev_alvo_x_media=2.0, book="ambas",
                                                                operacoes_por_dia=3),
    "trailing 0,8 + candle discrepante 1,5 + 3 reversões": dict(trailing_inicio_r=0.8, filtro_candle_discrepante_ativo=True, filtro_candle_discrepante_x=1.5,
                                                               reversoes=3, operacoes_por_dia=2),
    # Escada de contratos (ghost_escada_* do sistema antigo): contratos por operacao, reseta no pregao
    "escada 2 (ganho +1, perda -1), min 1, max 4, 3 ops": dict(escada_contratos=2, escada_ganho_acao="somar", escada_ganho_qtd=1,
                                                              escada_perda_acao="subtrair", escada_perda_qtd=1, escada_min=1, escada_max=4,
                                                              operacoes_por_dia=3),
    "escada 3 (perda +2, ganho -1), 3 reversões, trailing": dict(escada_contratos=3, escada_ganho_acao="subtrair", escada_ganho_qtd=1,
                                                                escada_perda_acao="somar", escada_perda_qtd=2, escada_min=1, escada_max=8,
                                                                reversoes=3, trailing_inicio_r=0.8, operacoes_por_dia=2),
    # Reversões (Etapa 5): stop com perda reverte no preço do stop, com stop/alvo próprios (0 = herda)
    "1 reversão (herda stop/alvo)": dict(reversoes=1),
    "2 reversões, stop 0,5, alvo 2, 2 ops": dict(reversoes=2, rev_stop_x_media=0.5, rev_alvo_x_media=2.0, operacoes_por_dia=2),
    "5 reversões, 3 ops, ambas, parar 2 seguidos": dict(reversoes=5, rev_stop_x_media=1.5, operacoes_por_dia=3, book="ambas",
                                                       parar_apos_losses=2, contagem_losses="seguidos"),
}


def _hhmm(s: str) -> time:
    m = hhmm_para_min(s)
    return time(m // 60, m % 60)


def params_antigos(p: Params) -> StrategyParams:
    ult = hhmm_para_min(p.ultima_entrada) if p.ultima_entrada else 0
    return StrategyParams(
        contracts=1, point_value=0.20, engine="ghostcandle_v6",
        start_time=_hhmm(p.janela_inicio), end_time=_hhmm(p.janela_fim),
        entry_order="limit", indicators_timing="closed", entry_bar_risk=True,
        slippage_pts=5.0, spread_pts=5.0, tick_size=5.0,
        ff2_maxmin_n=p.candles_gatilho, ff2_media_op_n=p.candles_media,
        ff2_stop_mult=p.stop_x_media, ff2_gain_mult=p.alvo_x_media, ff2_max_trades=p.operacoes_por_dia,
        ff2_range_min_pts=0.0, ff2_invert=True, ff2_max_reversals=p.reversoes, ff2_breakeven_pct=0.0,
        ghost_rev_stop_mult=p.rev_stop_x_media, ghost_rev_gain_mult=p.rev_alvo_x_media,
        ff2_intrabar="stop_first",
        malibu_vol_discard_mult=p.filtro_candle_discrepante_x if p.filtro_candle_discrepante_ativo else 0.0,
        ghost_k=p.bracket_fracao, ghost_sub_minutes=1, ghost_armar=p.book, ghost_trail_start_r=p.trailing_inicio_r,
        ghost_escada_contratos=p.escada_contratos, ghost_escada_gain=p.escada_ganho_acao, ghost_escada_gain_qtd=p.escada_ganho_qtd,
        ghost_escada_loss=p.escada_perda_acao, ghost_escada_loss_qtd=p.escada_perda_qtd, ghost_escada_min=p.escada_min, ghost_escada_max=p.escada_max,
        ghost_filtro3="off", ghost_ult_entrada_hhmm=(ult // 60) * 100 + ult % 60 if ult else 0,
        ghost_parar_losses=p.parar_apos_losses, ghost_parar_modo=p.contagem_losses,
        ghost_penetra_ticks=p.penetracao_ticks,
    )


def chave_antiga(tr):
    return [(r.side, str(r.entry_time), float(r.entry_price), str(r.exit_time), float(r.exit_price),
             float(r.pts), r.outcome, int(r.contracts), round(float(r.result_rs), 6)) for r in tr.itertuples(index=False)]


def chave_nova(tr):
    return [(r.lado, str(r.entrada_ts.floor("10min")), float(r.preco_entrada), str(r.saida_ts.floor("10min")),
             float(r.preco_saida), float(r.pts), r.desfecho, int(r.contratos), round(float(r.rs), 6)) for r in tr.itertuples(index=False)]


def main() -> int:
    csv = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "dados" / "WIN_1M_21_25.csv"
    bruto_antigo = load_candles(str(csv))
    barras_antigas = resample_ohlc(bruto_antigo, 10, sub_minutes=1)
    novo, _ = dados.carregar_csv(str(csv))
    barras_novas, sub = dados.preparar_barras(novo, 10)

    falhas = 0
    for nome, ov in CENARIOS.items():
        p = Params(**ov)
        t0 = T.time()
        _, antigo = run_backtest(barras_antigas, params_antigos(p))
        t1 = T.time()
        novo_tr = rodar_trades(barras_novas, p, sub)
        t2 = T.time()
        a, n = chave_antiga(antigo), chave_nova(novo_tr)
        ok = a == n
        total_a = float(antigo["result_rs"].sum()) if len(antigo) else 0.0
        total_n = float(novo_tr["rs"].sum()) if len(novo_tr) else 0.0
        print(f"[{'OK ' if ok else 'ERRO'}] {nome:55s} trades {len(a):5d}/{len(n):5d}  "
              f"R$ {total_a:10.2f}/{total_n:10.2f}  (antigo {t1 - t0:4.1f}s, novo {t2 - t1:4.1f}s)")
        if not ok:
            falhas += 1
            for x, y in zip(a, n):
                if x != y:
                    print("   primeira divergência:\n    antigo", x, "\n    novo  ", y)
                    break
    print("\nTODOS IDÊNTICOS" if not falhas else f"\n{falhas} cenário(s) divergente(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
