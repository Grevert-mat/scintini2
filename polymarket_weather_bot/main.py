"""
main.py — Ponto de entrada do Polymarket Weather Bot.

Uso:
    python main.py                  # Inicia o bot em loop contínuo
    python main.py --once           # Executa um único ciclo e sai
    python main.py --report         # Exibe relatório de performance e sai
    python main.py --demo           # Demonstra a lógica sem fazer chamadas de API reais

Credenciais: coloque no arquivo .env na mesma pasta (nunca enviado ao git):
    OWM_API_KEY          OpenWeatherMap API Key
    METEOMATICS_USER     Meteomatics username
    METEOMATICS_PASS     Meteomatics password
    CDS_API_KEY          Copernicus CDS key (formato UID:TOKEN)
    POLYMARKET_PRIVATE_KEY  Chave privada Polygon (somente trading real)
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# Carrega .env antes de qualquer import que leia os.getenv()
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv não instalado; variáveis de ambiente manuais ainda funcionam

from config import config
from trading_engine import TradingEngine


# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------

def setup_logging():
    level = getattr(logging, config.bot.log_level.upper(), logging.INFO)
    handlers = [logging.StreamHandler(sys.stdout)]

    if config.bot.log_file:
        handlers.append(logging.FileHandler(config.bot.log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    # Silenciar logs verbosos de bibliotecas externas
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Modo demo (sem chaves reais)
# ---------------------------------------------------------------------------

def run_demo():
    """
    Demonstra a lógica de decisão sem necessitar de chaves de API reais.
    Injeta dados fictícios para mostrar o fluxo completo.
    """
    log = logging.getLogger("demo")
    log.info("=" * 60)
    log.info("  DEMO — Simulação da lógica de decisão")
    log.info("=" * 60)

    from risk_manager import RiskManager
    from storage import Storage

    risk = RiskManager(current_bankroll=10.00)
    storage = Storage(db_path=":memory:")  # banco em memória, sem arquivo

    # Cenário 1: temperatura alta → deve apostar
    log.info("\n[Cenário 1] Temperatura: 34°C | Limiar: 30°C | Preço mercado: 55%")
    prob = risk.temperature_to_probability(34.0)
    edge = risk.calculate_edge(prob, 0.55)
    should, reason, bet = risk.should_open_position(
        my_probability=prob, market_price=0.55, open_positions_count=0
    )
    log.info("Decisão: %s | Motivo: %s | Aposta: $%.4f", "COMPRAR" if should else "AGUARDAR",
             reason, bet)

    # Cenário 2: temperatura baixa → não deve apostar
    log.info("\n[Cenário 2] Temperatura: 26°C | Limiar: 30°C | Preço mercado: 55%")
    prob2 = risk.temperature_to_probability(26.0)
    edge2 = risk.calculate_edge(prob2, 0.55)
    should2, reason2, bet2 = risk.should_open_position(
        my_probability=prob2, market_price=0.55, open_positions_count=0
    )
    log.info("Decisão: %s | Motivo: %s | Aposta: $%.4f", "COMPRAR" if should2 else "AGUARDAR",
             reason2, bet2)

    # Cenário 3: edge insuficiente
    log.info("\n[Cenário 3] Temperatura: 31°C | Limiar: 30°C | Preço mercado: 58%")
    prob3 = risk.temperature_to_probability(31.0)
    edge3 = risk.calculate_edge(prob3, 0.58)
    should3, reason3, bet3 = risk.should_open_position(
        my_probability=prob3, market_price=0.58, open_positions_count=0
    )
    log.info("Decisão: %s | Motivo: %s | Aposta: $%.4f", "COMPRAR" if should3 else "AGUARDAR",
             reason3, bet3)

    log.info("\n[Demo] Registrando trade de exemplo no banco em memória...")
    storage.save_trade_open(
        trade_id="TRD-DEMO001",
        token_id="DEMO_TOKEN",
        market_name="[DEMO] NYC temp > 30°C",
        entry_price=0.55,
        bet_size_usd=0.25,
        shares=0.25 / 0.55,
        bankroll_before=10.00,
        weather_sources={
            "NOAA_NWS": 34.1, "OpenWeatherMap": 33.8,
            "Copernicus_ERA5": None, "Meteomatics": 34.5, "NASA_POWER": 33.2,
            "Open_Meteo": 33.6, "FCCC_CobraCoral": 34.0,
        },
        consensus_temp=33.9,
        my_probability=prob,
        market_price=0.55,
        edge=edge,
        paper_trade=True,
    )
    storage.print_report()
    log.info("[Demo] Concluído com sucesso.")


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def main():
    setup_logging()
    log = logging.getLogger("main")

    parser = argparse.ArgumentParser(
        description="Polymarket Weather Bot — Value Betting em mercados de clima"
    )
    parser.add_argument("--once", action="store_true",
                        help="Executa um único ciclo e sai")
    parser.add_argument("--report", action="store_true",
                        help="Exibe relatório de performance e sai")
    parser.add_argument("--demo", action="store_true",
                        help="Executa demonstração sem chaves de API")
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    if args.report:
        from storage import Storage
        Storage().print_report()
        return

    # Aviso de segurança para modo real
    if not config.bot.paper_trading:
        log.warning("=" * 55)
        log.warning("  ATENÇÃO: Modo de trading REAL ativado!")
        log.warning("  O bot usará capital real. Certifique-se de que")
        log.warning("  as chaves de API e carteira estão configuradas.")
        log.warning("=" * 55)
        confirm = input("Digite 'CONFIRMAR' para continuar: ").strip()
        if confirm != "CONFIRMAR":
            log.info("Operação cancelada pelo usuário.")
            return

    engine = TradingEngine()

    if args.once:
        log.info("Executando ciclo único...")
        engine.run_once()
        engine.print_status()
    else:
        engine.run()


if __name__ == "__main__":
    main()
