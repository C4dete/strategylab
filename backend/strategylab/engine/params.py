"""Parâmetros editáveis de uma estratégia e o perfil de execução fixo.

`Params` é o que o usuário controla no painel e o que vai para o JSON em `estrategias/`.
Tudo que NÃO está aqui é fixo na Etapa 1 (ver `EXECUCAO` e `docs/motor.md`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Book = Literal["ambas", "cont", "recuo", "acima", "abaixo"]
ContagemLosses = Literal["dia", "seguidos"]
ModoEntrada = Literal["padrao", "proximo_candle"]
EscadaAcao = Literal["manter", "somar", "subtrair"]

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def hhmm_para_min(valor: str) -> int:
    h, m = valor.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class Execucao:
    """Perfil "Ao vivo (candle fechado)" para o WIN. Não é editável nesta etapa."""

    ativo: str = "WIN"
    descricao_ativo: str = "Mini índice"
    perfil: str = "Ao vivo (candle fechado)"
    valor_ponto: float = 0.20      # R$ por ponto por contrato
    contratos: int = 1
    timeframe_min: int = 10        # barras do gráfico/regras
    leitura_min: int = 1           # sub-candles que resolvem a ordem dos eventos
    slippage_pts: float = 5.0      # só em ordens a mercado (stop/zeragem)
    spread_pts: float = 5.0
    tick_pts: float = 5.0
    entrada: str = ("Fade (acima vende, abaixo compra). Modo Padrão: ordem limite, sem custo. "
                    "Modo Próximo candle: a mercado na abertura da barra seguinte, com custo")


EXECUCAO = Execucao()


class Params(BaseModel):
    """Campos editáveis de uma estratégia. Campos ausentes assumem o padrão (arquivos antigos continuam válidos).

    Etapa 1: janela, última entrada, gatilho/média, bracket, book, penetração, parada por losses, operações, stop e alvo.
    Etapa 2: indicadores (média móvel e Bandas de Bollinger, ambas EMA) e o filtro "Afastamento da MM" (desligado por padrão).
    Etapa 6: controles de cauda (parar o dia por perda, tempo máximo na posição) e filtros de regime (gap, volatilidade de ontem,
    largura das Bandas de Bollinger, inclinação da MM), todos desligados por padrão.
    Etapa 5: "Reversões" (quantas, com stop e alvo próprios; 0 = desligado).
    Etapa 3: "Modo de entrada" (padrão ou próximo candle), "Sair ao tocar a MM" e "Rastrear MM" (os dois desligados por padrão).
    """

    model_config = ConfigDict(extra="ignore")

    janela_inicio: str = "09:00"
    janela_fim: str = "17:30"                    # zeragem
    ultima_entrada: Optional[str] = "16:00"      # None = usa a zeragem
    candles_gatilho: int = Field(5, ge=1, le=30)
    candles_media: int = Field(5, ge=2, le=30)
    bracket_fracao: float = Field(0.05, ge=0.05, le=3.0)
    modo_entrada: ModoEntrada = "padrao"          # "proximo_candle": a entrada só acontece na abertura da barra seguinte
    reversoes: int = Field(0, ge=0, le=5)         # stop-and-reverse: quantas vezes um stop com perda reverte a posição (0 = off)
    rev_stop_x_media: float = Field(0.0, ge=0.0, le=10.0)   # stop da posição revertida, em × media_operacao (0 = igual ao da entrada)
    rev_alvo_x_media: float = Field(0.0, ge=0.0, le=10.0)   # alvo da posição revertida, em × media_operacao (0 = igual ao da entrada)
    book: Book = "cont"
    penetracao_ticks: int = Field(1, ge=0, le=5)
    parar_apos_losses: int = Field(0, ge=0, le=20)
    contagem_losses: ContagemLosses = "dia"
    operacoes_por_dia: int = Field(1, ge=1, le=50)
    stop_x_media: float = Field(1.0, ge=0.1, le=5.0)
    alvo_x_media: float = Field(3.0, ge=0.1, le=8.0)

    # --- 03 Indicadores (EMA sobre o fechamento das barras de 10 min, série contínua) ---
    mm_periodo: int = Field(15, ge=2, le=200)
    bb_periodo: int = Field(15, ge=2, le=200)       # EMA central + janela do desvio-padrão
    bb_desvio: float = Field(2.0, ge=0.5, le=5.0)   # k: bandas = EMA ± k × desvio-padrão (populacional)

    # --- 04 Filtros (cada um liga/desliga; desligado = comportamento da Etapa 1) ---
    filtro_afast_mm_ativo: bool = False
    filtro_afast_mm_x_media: float = Field(0.7, ge=0.05, le=10.0)   # afastamento mínimo, em × media_operacao
    rastrear_mm: bool = False                       # acima da MM só vendas; abaixo dela só compras (candle fechado anterior)
    # --- Etapa 6: controle de cauda (0 = desligado) ---
    parar_dia_perda_x_media: float = Field(0.0, ge=0.0, le=20.0)   # para o dia ao perder este tanto (× media_operacao) já realizado
    tempo_max_min: int = Field(0, ge=0, le=480)                    # sai a mercado N minutos depois da entrada de cada perna

    # --- Etapa 6: filtros de regime, decididos ANTES de operar (só dado fechado; cada um liga/desliga) ---
    filtro_gap_ativo: bool = False                                 # bloqueia o DIA se |abertura - fechamento de ontem| for grande
    filtro_gap_max_x_media: float = Field(0.5, ge=0.05, le=5.0)    # em × amplitude média dos 20 pregões anteriores
    filtro_vol_ontem_ativo: bool = False                           # bloqueia o DIA se a amplitude de ontem foi alta
    filtro_vol_ontem_max: float = Field(1.5, ge=0.5, le=5.0)       # amplitude de ontem ÷ média das 20 anteriores a ontem
    filtro_bb_ativo: bool = False                                  # bloqueia a barra se as bandas estão largas (ou estreitas) demais
    filtro_bb_largura_min_pct: float = Field(0.0, ge=0.0, le=5.0)  # largura (banda sup. - inf.) em % da linha central; 0 = sem mínimo
    filtro_bb_largura_max_pct: float = Field(1.0, ge=0.05, le=10.0)
    filtro_inclinacao_ativo: bool = False                          # bloqueia a barra se a MM está inclinada demais (mercado direcional)
    filtro_inclinacao_barras: int = Field(5, ge=2, le=30)          # inclinação = MM(i-1) - MM(i-1-N), em pontos
    filtro_inclinacao_max_x_media: float = Field(0.5, ge=0.05, le=10.0)   # bloqueia se |inclinação| >= X × media_operacao
    escada_contratos: int = Field(0, ge=0, le=100)                 # escada de contratos: contratos no início de CADA pregão (0 = desligada: 1 contrato fixo)
    escada_ganho_acao: EscadaAcao = "manter"                       # depois de uma operação com ganho (pts > 0)
    escada_ganho_qtd: int = Field(1, ge=1, le=20)
    escada_perda_acao: EscadaAcao = "manter"                       # depois de uma operação sem ganho (pts <= 0)
    escada_perda_qtd: int = Field(1, ge=1, le=20)
    escada_min: int = Field(1, ge=1, le=100)                       # piso de contratos
    escada_max: int = Field(5, ge=1, le=100)                       # teto de contratos
    trailing_inicio_r: float = Field(0.0, ge=0.0, le=10.0)         # trailing stop: arma ao avançar X × risco a favor (0 = desligado)
    filtro_candle_discrepante_ativo: bool = False                  # a media_operacao ignora o candle discrepante da janela
    filtro_candle_discrepante_x: float = Field(2.0, ge=1.0, le=10.0)   # discrepante = o maior da janela > X × o 2º maior
    sair_ao_tocar_mm: bool = False                  # com posição aberta: tocar a MM (do fechamento da barra anterior) encerra a operação

    @field_validator("janela_inicio", "janela_fim", "ultima_entrada")
    @classmethod
    def _horario(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _HHMM.match(v):
            raise ValueError("Use o formato HH:MM (ex.: 09:00).")
        return v

    @field_validator("bracket_fracao", "stop_x_media", "alvo_x_media", "bb_desvio", "filtro_afast_mm_x_media",
                     "rev_stop_x_media", "rev_alvo_x_media", "parar_dia_perda_x_media",
                     "filtro_gap_max_x_media", "filtro_vol_ontem_max", "filtro_bb_largura_min_pct", "filtro_bb_largura_max_pct",
                     "filtro_inclinacao_max_x_media", "filtro_candle_discrepante_x", "trailing_inicio_r")
    @classmethod
    def _arredonda(cls, v: float) -> float:
        # 0,05 em passos de 0,05 acumula erro binário (0,15000000000000002); o JSON fica limpo.
        return round(float(v), 4)

    @model_validator(mode="after")
    def _coerencia(self) -> "Params":
        ini, fim = hhmm_para_min(self.janela_inicio), hhmm_para_min(self.janela_fim)
        if ini >= fim:
            raise ValueError("O início da janela precisa ser antes da zeragem (fim).")
        if self.filtro_bb_ativo and self.filtro_bb_largura_min_pct > 0 and self.filtro_bb_largura_min_pct >= self.filtro_bb_largura_max_pct:
            raise ValueError("Largura das bandas: o mínimo precisa ser menor que o máximo.")
        if self.escada_contratos > 0:
            if self.escada_min > self.escada_max:
                raise ValueError("Escada de contratos: o mínimo precisa ser menor ou igual ao máximo.")
            if not (self.escada_min <= self.escada_contratos <= self.escada_max):
                raise ValueError("Escada de contratos: os contratos iniciais precisam estar entre o mínimo e o máximo.")
        if self.ultima_entrada is not None:
            ult = hhmm_para_min(self.ultima_entrada)
            if ult <= ini:
                raise ValueError("A última entrada precisa ser depois do início da janela.")
            if ult > fim:
                raise ValueError("A última entrada não pode ser depois da zeragem.")
        return self

    def chave_motor(self) -> str:
        """Identifica só o que muda o RESULTADO do backtest (chave do cache).

        As Bandas de Bollinger só importam com o filtro de largura ligado. A média móvel só importa com o filtro de
        afastamento, o Rastrear MM, a saída ao tocar a MM ou o filtro de inclinação ligados; o valor de cada filtro,
        só com o próprio filtro ligado.
        """
        d = self.model_dump()
        if not self.filtro_bb_ativo:
            for k in ("bb_periodo", "bb_desvio", "filtro_bb_largura_min_pct", "filtro_bb_largura_max_pct"):
                d.pop(k)
        if self.reversoes == 0:                      # stop/alvo da reversão só importam com reversões
            d.pop("rev_stop_x_media")
            d.pop("rev_alvo_x_media")
        if not self.filtro_gap_ativo:
            d.pop("filtro_gap_max_x_media")
        if not self.filtro_vol_ontem_ativo:
            d.pop("filtro_vol_ontem_max")
        if not self.filtro_inclinacao_ativo:
            d.pop("filtro_inclinacao_barras")
            d.pop("filtro_inclinacao_max_x_media")
        if self.escada_contratos == 0:                 # sem escada, os detalhes dela não mudam o resultado
            for k in ("escada_ganho_acao", "escada_ganho_qtd", "escada_perda_acao", "escada_perda_qtd", "escada_min", "escada_max"):
                d.pop(k)
        if not self.filtro_candle_discrepante_ativo:
            d.pop("filtro_candle_discrepante_x")
        if not self.filtro_afast_mm_ativo:
            d.pop("filtro_afast_mm_x_media")
        if not (self.filtro_afast_mm_ativo or self.sair_ao_tocar_mm or self.rastrear_mm or self.filtro_inclinacao_ativo):
            d.pop("mm_periodo")
        return json.dumps(d, sort_keys=True)


def params_padrao() -> Params:
    """Valores da estratégia `inicial_default` (equivalentes do v6_10min nos campos da Etapa 1; filtros desligados)."""
    return Params()
