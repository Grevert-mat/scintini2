"""
trading_engine.py — Núcleo de lógica de trading.

Orquestra:
1. Coleta de dados climáticos (DataFetcher)
2. Consulta de preço e status do mercado (PolymarketClient)
3. Avaliação de risco e dimensionamento (RiskManager)
4. Execução e registro de operações (Storage)

Loop principal:
  - Verifica mercado a cada `poll_interval_seconds`
  - Abre posições quando há edge suficiente
  - Monitora posições abertas e fecha quando atingem alvo ou stop-loss
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from config import config
from data_fetcher import DataFetcher
from polymarket_client import PolymarketClient
from risk_manager import RiskManager
from storage import Storage

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Motor de trading principal.
    Instancie e chame .run() para iniciar o loop contínuo,
    ou .run_once() para um único ciclo (útil para testes).
    """

    def __init__(self):
        self.cfg = config
        self.fetcher = DataFetcher()
        self.poly = PolymarketClient()
        self.storage = Storage()
        self.risk = RiskManager(
            current_bankroll=self._load_bankroll()
        )

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def _load_bankroll(self) -> float:
        """
        Tenta recuperar a banca atual do último trade registrado.
        Se não houver histórico, usa o valor inicial da configuração.
        """
        trades = self.storage.get_all_trades(limit=1)
        if trades:
            last = trades[0]
            if last.get("bankroll_after") is not None:
                logger.info("Banca recuperada do histórico: $%.4f", last["bankroll_after"])
                return last["bankroll_after"]
            # Posição aberta sem banca_after registrada
            if last.get("bankroll_before") is not None:
                return last["bankroll_before"] - last.get("bet_size_usd", 0)
        logger.info("Nenhum histórico encontrado. Usando banca inicial: $%.2f",
                    config.risk.initial_bankroll)
        return config.risk.initial_bankroll

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------

    def run(self):
        """Loop contínuo. Pressione Ctrl+C para interromper."""
        mode = "PAPER TRADING" if self.cfg.bot.paper_trading else "TRADING REAL"
        logger.info("=" * 60)
        logger.info("  POLYMARKET WEATHER BOT iniciado — Modo: %s", mode)
        logger.info("  Mercado: %s", self.cfg.market.market_name)
        logger.info("  Banca atual: $%.4f", self.risk.bankroll)
        logger.info("  Intervalo de verificação: %ds", self.cfg.bot.poll_interval_seconds)
        logger.info("=" * 60)

        try:
            while True:
                try:
                    self.run_once()
                except Exception as exc:
                    logger.error("Erro no ciclo de trading: %s", exc, exc_info=True)

                logger.info("Aguardando %ds até próxima verificação...\n",
                            self.cfg.bot.poll_interval_seconds)
                time.sleep(self.cfg.bot.poll_interval_seconds)

        except KeyboardInterrupt:
            logger.info("Bot interrompido pelo usuário.")
            self.storage.print_report()

    def run_once(self):
        """Executa um único ciclo completo de análise e decisão."""
        logger.info("--- Início do ciclo: %s ---",
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))

        # 1. Verificar se o mercado está ativo
        logger.info("Verificando status do mercado...")
        if not self.poly.is_market_open():
            logger.info("Mercado fechado. Verificando posições abertas para liquidação...")
            self._check_open_positions(force_close=True)
            return

        # 2. Coletar preço atual do Polymarket
        logger.info("Obtendo preço atual do Polymarket...")
        market_price = self.poly.get_market_price()
        if market_price is None:
            logger.warning("Não foi possível obter o preço do mercado. Abortando ciclo.")
            return

        # 3. Coletar dados climáticos
        weather = self.fetcher.get_consensus()
        consensus_temp = weather["consensus_temp"]
        if consensus_temp is None:
            logger.warning("Consenso climático indisponível. Abortando ciclo.")
            return

        # 4. Converter temperatura → probabilidade
        my_probability = self.risk.temperature_to_probability(consensus_temp)

        # 5. Avaliar posições abertas (monitoramento contínuo)
        self._check_open_positions(
            current_market_price=market_price,
            my_probability=my_probability,
        )

        # 6. Avaliar abertura de nova posição
        open_positions = self.storage.get_open_trades()
        should_open, reason, bet_size = self.risk.should_open_position(
            my_probability=my_probability,
            market_price=market_price,
            open_positions_count=len(open_positions),
        )

        if should_open:
            logger.info("Oportunidade identificada! %s", reason)
            self._open_position(
                market_price=market_price,
                bet_size=bet_size,
                weather=weather,
                consensus_temp=consensus_temp,
                my_probability=my_probability,
            )
        else:
            logger.info("Sem oportunidade agora. Motivo: %s", reason)

        logger.info("Banca atual: $%.4f", self.risk.bankroll)

    # ------------------------------------------------------------------
    # Abertura de posição
    # ------------------------------------------------------------------

    def _open_position(
        self,
        market_price: float,
        bet_size: float,
        weather: dict,
        consensus_temp: float,
        my_probability: float,
    ):
        """Abre uma nova posição e registra no banco."""
        trade_id = f"TRD-{uuid.uuid4().hex[:10].upper()}"
        edge = self.risk.calculate_edge(my_probability, market_price)

        logger.info(
            "[ABRINDO POSIÇÃO] ID=%s | Preço=$%.4f | Aposta=$%.4f | "
            "Prob=%.2f%% | Edge=%.2f%%",
            trade_id, market_price, bet_size, my_probability * 100, edge * 100
        )

        # Executar ordem (simulada ou real)
        order = self.poly.place_buy_order(size_usd=bet_size, price=market_price)
        if order.get("status") == "error":
            logger.error("Falha ao executar ordem: %s", order.get("message"))
            return

        shares = order.get("shares", bet_size / market_price)
        bankroll_before = self.risk.bankroll
        new_bankroll = bankroll_before - bet_size
        self.risk.update_bankroll(new_bankroll)

        # Persistir no banco
        self.storage.save_trade_open(
            trade_id=trade_id,
            token_id=self.cfg.market.token_id,
            market_name=self.cfg.market.market_name,
            entry_price=market_price,
            bet_size_usd=bet_size,
            shares=shares,
            bankroll_before=bankroll_before,
            weather_sources=weather["individual_readings"],
            consensus_temp=consensus_temp,
            my_probability=my_probability,
            market_price=market_price,
            edge=edge,
            paper_trade=self.cfg.bot.paper_trading,
        )

        logger.info(
            "Posição aberta com sucesso! Banca: $%.4f → $%.4f",
            bankroll_before, new_bankroll
        )

    # ------------------------------------------------------------------
    # Monitoramento e fechamento de posições
    # ------------------------------------------------------------------

    def _check_open_positions(
        self,
        current_market_price: float = None,
        my_probability: float = None,
        force_close: bool = False,
    ):
        """Verifica todas as posições abertas e fecha as que atingiram alvo/stop."""
        open_trades = self.storage.get_open_trades()
        if not open_trades:
            logger.debug("Nenhuma posição aberta para monitorar.")
            return

        logger.info("Monitorando %d posição(ões) aberta(s)...", len(open_trades))

        # Se não temos preço atual, buscar agora
        if current_market_price is None:
            current_market_price = self.poly.get_market_price()
            if current_market_price is None:
                logger.warning("Não foi possível obter preço para monitoramento.")
                return

        for trade in open_trades:
            trade_id = trade["trade_id"]
            entry_price = trade["entry_price"]
            shares = trade["shares"]
            stored_prob = trade.get("my_probability", my_probability)

            if force_close:
                reason = "Mercado encerrado — liquidação forçada"
                should_close = True
            elif stored_prob is not None and my_probability is not None:
                should_close, reason = self.risk.should_close_position(
                    entry_price=entry_price,
                    current_price=current_market_price,
                    my_probability=stored_prob,
                )
            else:
                should_close, reason = False, "Aguardando dados completos"

            logger.info(
                "  Trade %s | Entrada=$%.4f | Atual=$%.4f | %s",
                trade_id, entry_price, current_market_price,
                "FECHAR" if should_close else "MANTER"
            )

            if should_close:
                self._close_position(trade_id, shares, current_market_price, reason)

    def _close_position(
        self,
        trade_id: str,
        shares: float,
        exit_price: float,
        reason: str,
    ):
        """Fecha uma posição e atualiza a banca."""
        logger.info("[FECHANDO POSIÇÃO] ID=%s | Preço=$%.4f | Motivo: %s",
                    trade_id, exit_price, reason)

        # Executar venda (simulada ou real)
        order = self.poly.place_sell_order(shares=shares, price=exit_price)

        proceeds = order.get("proceeds_usd", shares * exit_price)
        new_bankroll = self.risk.bankroll + proceeds
        self.risk.update_bankroll(new_bankroll)

        self.storage.save_trade_close(
            trade_id=trade_id,
            exit_price=exit_price,
            bankroll_after=new_bankroll,
            close_reason=reason,
        )

        logger.info(
            "Posição fechada! Recebido: $%.4f | Banca: $%.4f",
            proceeds, new_bankroll
        )

    # ------------------------------------------------------------------
    # Relatório instantâneo
    # ------------------------------------------------------------------

    def print_status(self):
        """Imprime o status atual do bot."""
        self.storage.print_report()
        open_trades = self.storage.get_open_trades()
        if open_trades:
            logger.info("Posições abertas:")
            for t in open_trades:
                logger.info(
                    "  %s | Entrada: $%.4f | Cotas: %.4f | Prob: %.2f%%",
                    t["trade_id"], t["entry_price"], t["shares"],
                    (t.get("my_probability") or 0) * 100,
                )
