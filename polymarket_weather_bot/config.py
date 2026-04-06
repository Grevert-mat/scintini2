"""
config.py — Configurações centrais do bot.
Edite este arquivo com suas chaves de API antes de rodar.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Chaves de API (lidas de variáveis de ambiente ou definidas diretamente)
# ---------------------------------------------------------------------------

@dataclass
class APIConfig:
    # OpenWeatherMap — https://openweathermap.org/api
    openweathermap_key: str = os.getenv("OWM_API_KEY", "SUA_CHAVE_AQUI")

    # Meteomatics — https://www.meteomatics.com/
    meteomatics_user: str = os.getenv("METEOMATICS_USER", "SEU_USUARIO_AQUI")
    meteomatics_password: str = os.getenv("METEOMATICS_PASS", "SUA_SENHA_AQUI")

    # Copernicus CDS — https://cds.climate.copernicus.eu/
    copernicus_key: str = os.getenv("CDS_API_KEY", "SUA_CHAVE_AQUI")
    copernicus_url: str = "https://cds.climate.copernicus.eu/api/v2"

    # NOAA / NWS — gratuito, sem chave obrigatória
    # NASA POWER — gratuito, sem chave obrigatória


# ---------------------------------------------------------------------------
# Alvo geográfico (lat/lon da cidade monitorada)
# ---------------------------------------------------------------------------

@dataclass
class LocationConfig:
    city: str = "New York"
    latitude: float = 40.7128
    longitude: float = -74.0060
    # Usado pelo NWS (NOAA) — formato "latitude,longitude"
    noaa_point: str = "40.7128,-74.0060"
    # Código do grid NWS — obtido uma vez via /points/{lat},{lon}
    noaa_office: str = "OKX"
    noaa_grid_x: int = 33
    noaa_grid_y: int = 37


# ---------------------------------------------------------------------------
# Mercado alvo no Polymarket
# ---------------------------------------------------------------------------

@dataclass
class MarketConfig:
    # token_id do mercado "YES" no Polymarket CLOB
    token_id: str = "SEU_TOKEN_ID_AQUI"
    # Descrição legível (para logs e relatórios)
    market_name: str = "Will the temperature in NYC exceed 30°C on YYYY-MM-DD?"
    # Temperatura limiar usada pelo mercado (em °C)
    threshold_celsius: float = 30.0
    # Direção: "above" = acima do limiar, "below" = abaixo
    direction: str = "above"


# ---------------------------------------------------------------------------
# Gestão de risco e paper trading
# ---------------------------------------------------------------------------

@dataclass
class RiskConfig:
    initial_bankroll: float = 10.00          # Banca inicial simulada (USD)
    max_bet_pct: float = 0.05               # Máx 5% da banca por trade
    min_edge: float = 0.10                  # Margem mínima de vantagem (10%)
    min_probability: float = 0.55          # Prob. mínima para apostar
    max_open_positions: int = 3            # Máx de posições abertas simultâneas
    stop_loss_pct: float = 0.50            # Fechar se odds cairem 50%


# ---------------------------------------------------------------------------
# Operação do bot
# ---------------------------------------------------------------------------

@dataclass
class BotConfig:
    poll_interval_seconds: int = 300       # Intervalo entre verificações (5 min)
    paper_trading: bool = True             # True = simulação, False = real
    db_path: str = "trades.db"            # Banco SQLite
    log_level: str = "INFO"               # DEBUG | INFO | WARNING | ERROR
    log_file: Optional[str] = "bot.log"   # None = apenas console


# ---------------------------------------------------------------------------
# Objeto raiz agregador
# ---------------------------------------------------------------------------

@dataclass
class Config:
    api: APIConfig = field(default_factory=APIConfig)
    location: LocationConfig = field(default_factory=LocationConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    bot: BotConfig = field(default_factory=BotConfig)


# Instância global usada pelos módulos
config = Config()
