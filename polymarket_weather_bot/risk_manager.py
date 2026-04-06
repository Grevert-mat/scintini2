"""
risk_manager.py — Gestão de risco e dimensionamento de apostas.

Implementa:
- Kelly Criterion fracionário para bet sizing
- Limite máximo de 5% da banca por trade
- Margem de segurança mínima (edge) de 10%
- Controle de posições abertas simultâneas
- Cálculo de probabilidade climática a partir do consenso de temperatura
"""

import logging
import math

from config import config

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Responsável por:
    1. Converter temperatura de consenso → probabilidade do evento de mercado
    2. Verificar se há vantagem (edge) suficiente para apostar
    3. Calcular o tamanho ótimo da aposta (Kelly Criterion fracionário)
    4. Controlar limites de risco
    """

    def __init__(self, current_bankroll: float = None):
        self.cfg = config.risk
        self.market = config.market
        self.bankroll = current_bankroll if current_bankroll is not None else self.cfg.initial_bankroll

    def update_bankroll(self, new_bankroll: float):
        """Atualiza a banca (chamado pelo TradingEngine após cada trade)."""
        self.bankroll = new_bankroll
        logger.debug("Banca atualizada: $%.4f", self.bankroll)

    # ------------------------------------------------------------------
    # Conversão de temperatura → probabilidade do evento
    # ------------------------------------------------------------------

    def temperature_to_probability(self, consensus_temp: float) -> float:
        """
        Converte a temperatura de consenso em uma probabilidade (0–1)
        de que o evento do mercado ocorra.

        Usa uma sigmoid centrada no limiar do mercado.
        A "inclinação" controla quão rapidamente a probabilidade muda.

        Exemplo (limiar = 30°C, direção = "above"):
          - 25°C → prob ≈ 0.07  (muito improvável)
          - 29°C → prob ≈ 0.38
          - 30°C → prob = 0.50  (exatamente no limiar)
          - 31°C → prob ≈ 0.62
          - 35°C → prob ≈ 0.93
        """
        threshold = self.market.threshold_celsius
        direction = self.market.direction

        # Sigmoid com inclinação k — ajuste k conforme a volatilidade histórica local
        # k maior = curva mais íngreme (mais confiante nas previsões)
        k = 0.8

        diff = consensus_temp - threshold
        if direction == "below":
            diff = -diff  # inverte: evento é "abaixo do limiar"

        sigmoid = 1.0 / (1.0 + math.exp(-k * diff))
        logger.info(
            "Temperatura de consenso: %.2f°C | Limiar: %.2f°C | Direção: %s → Prob. calculada: %.2f%%",
            consensus_temp, threshold, direction, sigmoid * 100
        )
        return sigmoid

    # ------------------------------------------------------------------
    # Cálculo de vantagem (edge)
    # ------------------------------------------------------------------

    def calculate_edge(self, my_probability: float, market_price: float) -> float:
        """
        Edge = Diferença entre nossa probabilidade e o preço do mercado.
        Edge positivo = mercado está subprecificando o evento (oportunidade de compra).

        Args:
            my_probability: probabilidade calculada pelo bot (0–1)
            market_price:   preço atual do token YES no Polymarket (0–1)

        Returns:
            edge em decimal (ex: 0.15 = 15% de vantagem)
        """
        edge = my_probability - market_price
        logger.info(
            "Edge calculado: %.2f%% (Minha prob: %.2f%% | Mercado: %.2f%%)",
            edge * 100, my_probability * 100, market_price * 100
        )
        return edge

    def has_sufficient_edge(self, edge: float) -> bool:
        """Verifica se a vantagem é suficiente para apostar."""
        sufficient = edge >= self.cfg.min_edge
        if not sufficient:
            logger.info(
                "Edge insuficiente: %.2f%% < %.2f%% (mínimo). Aguardando...",
                edge * 100, self.cfg.min_edge * 100
            )
        return sufficient

    def is_probability_strong(self, probability: float) -> bool:
        """Verifica se a probabilidade é alta o suficiente para operar."""
        strong = probability >= self.cfg.min_probability
        if not strong:
            logger.info(
                "Probabilidade fraca: %.2f%% < %.2f%% (mínimo). Aguardando...",
                probability * 100, self.cfg.min_probability * 100
            )
        return strong

    # ------------------------------------------------------------------
    # Dimensionamento da aposta — Kelly Criterion fracionário
    # ------------------------------------------------------------------

    def calculate_bet_size(self, my_probability: float, market_price: float) -> float:
        """
        Calcula o tamanho ideal da aposta usando Kelly Criterion fracionário.

        Fórmula Kelly:
          f* = (b*p - q) / b
          onde:
            p = probabilidade de ganho
            q = probabilidade de perda = 1 - p
            b = odds decimal - 1 = (1/price) - 1

        Usamos Kelly fracionário (1/4 do Kelly completo) para conservadorismo.
        O resultado é ainda limitado ao máximo de 5% da banca.

        Returns:
            valor em USD a apostar (já limitado)
        """
        if market_price <= 0 or market_price >= 1:
            return 0.0

        p = my_probability
        q = 1.0 - p
        b = (1.0 / market_price) - 1.0  # lucro por unidade apostada

        kelly_fraction = (b * p - q) / b if b > 0 else 0.0
        kelly_fraction = max(0.0, kelly_fraction)  # Kelly negativo = não apostar

        # Kelly fracionário (25% do Kelly completo = mais conservador)
        fractional_kelly = kelly_fraction * 0.25

        # Limita ao máximo permitido por trade
        max_bet = self.bankroll * self.cfg.max_bet_pct
        bet_size = min(self.bankroll * fractional_kelly, max_bet)

        # Garante um mínimo de $0.01 (resolução mínima do Polymarket)
        bet_size = max(0.01, round(bet_size, 4)) if bet_size > 0.01 else 0.0

        logger.info(
            "Kelly: f*=%.4f | Kelly Frac (25%%): %.4f | Max/trade: $%.4f | Aposta: $%.4f",
            kelly_fraction, fractional_kelly, max_bet, bet_size
        )
        return bet_size

    # ------------------------------------------------------------------
    # Validação completa antes de abrir posição
    # ------------------------------------------------------------------

    def should_open_position(
        self,
        my_probability: float,
        market_price: float,
        open_positions_count: int,
    ) -> tuple[bool, str, float]:
        """
        Avaliação completa de risco antes de abrir uma nova posição.

        Returns:
            (deve_apostar: bool, motivo: str, tamanho_aposta: float)
        """
        # 1. Número máximo de posições abertas
        if open_positions_count >= self.cfg.max_open_positions:
            return False, f"Máximo de posições abertas atingido ({self.cfg.max_open_positions})", 0.0

        # 2. Probabilidade mínima
        if not self.is_probability_strong(my_probability):
            return False, f"Probabilidade baixa: {my_probability:.2%}", 0.0

        # 3. Edge mínimo
        edge = self.calculate_edge(my_probability, market_price)
        if not self.has_sufficient_edge(edge):
            return False, f"Edge insuficiente: {edge:.2%}", 0.0

        # 4. Banca suficiente
        min_bet = 0.01
        if self.bankroll < min_bet:
            return False, "Banca insuficiente", 0.0

        # 5. Calcular tamanho
        bet_size = self.calculate_bet_size(my_probability, market_price)
        if bet_size <= 0:
            return False, "Kelly negativo (sem vantagem)", 0.0

        return True, f"Edge de {edge:.2%} — apostar ${bet_size:.4f}", bet_size

    # ------------------------------------------------------------------
    # Avaliação de saída (sell)
    # ------------------------------------------------------------------

    def should_close_position(
        self,
        entry_price: float,
        current_price: float,
        my_probability: float,
    ) -> tuple[bool, str]:
        """
        Decide se deve fechar uma posição aberta.

        Returns:
            (deve_fechar: bool, motivo: str)
        """
        # Lucro: mercado convergiu para nossa estimativa
        if current_price >= my_probability * 0.95:
            return True, f"Alvo atingido: preço {current_price:.4f} ≥ estimativa {my_probability:.4f}"

        # Stop-loss: preço caiu mais de stop_loss_pct do preço de entrada
        stop_price = entry_price * (1.0 - self.cfg.stop_loss_pct)
        if current_price <= stop_price:
            return True, f"Stop-loss ativado: preço {current_price:.4f} ≤ stop {stop_price:.4f}"

        # Edge invertido: mercado virou contra nós
        edge = self.calculate_edge(my_probability, current_price)
        if edge < -self.cfg.min_edge:
            return True, f"Edge invertido: {edge:.2%}"

        return False, "Manter posição"
