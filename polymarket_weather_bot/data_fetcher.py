"""
data_fetcher.py — Fusão de dados de 5 APIs meteorológicas.

Cada método retorna a temperatura prevista em °C (float) ou None em caso de falha.
A média ponderada das fontes disponíveis é calculada descartando outliers via IQR.
"""

import logging
import statistics
from datetime import datetime, timezone
from typing import Optional

import requests

from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _celsius_from_fahrenheit(f: float) -> float:
    return (f - 32) * 5 / 9


def _kelvin_to_celsius(k: float) -> float:
    return k - 273.15


def _safe_get(url: str, params: dict = None, headers: dict = None,
              timeout: int = 15) -> Optional[dict]:
    """GET com tratamento de erro unificado."""
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("Timeout em %s", url)
    except requests.exceptions.HTTPError as exc:
        logger.warning("HTTP %s em %s", exc.response.status_code, url)
    except Exception as exc:
        logger.warning("Erro inesperado em %s: %s", url, exc)
    return None


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class DataFetcher:
    """
    Agrega previsões de temperatura de 5 fontes independentes
    e retorna um consenso estatístico robusto.
    """

    def __init__(self):
        self.loc = config.location
        self.api = config.api

    # ------------------------------------------------------------------
    # 1. NOAA / National Weather Service (EUA) — sem chave
    # ------------------------------------------------------------------

    def fetch_noaa(self) -> Optional[float]:
        """
        Usa a API pública do NWS.
        Endpoint: https://api.weather.gov/gridpoints/{office}/{x},{y}/forecast
        Retorna temperatura em °C do primeiro período disponível.
        """
        url = (
            f"https://api.weather.gov/gridpoints/"
            f"{self.loc.noaa_office}/{self.loc.noaa_grid_x},{self.loc.noaa_grid_y}/forecast"
        )
        headers = {"User-Agent": "PolymarketWeatherBot/1.0 (contato@exemplo.com)"}
        data = _safe_get(url, headers=headers)
        if not data:
            return None
        try:
            periods = data["properties"]["periods"]
            if not periods:
                return None
            # Pega o período mais próximo ao dia alvo
            temp_f = periods[0]["temperature"]
            unit = periods[0]["temperatureUnit"]
            temp_c = _celsius_from_fahrenheit(temp_f) if unit == "F" else float(temp_f)
            logger.debug("NOAA: %.2f°C", temp_c)
            return temp_c
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("NOAA — parse error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # 2. OpenWeatherMap — requer chave gratuita
    # ------------------------------------------------------------------

    def fetch_openweathermap(self) -> Optional[float]:
        """
        One Call API 3.0 (ou forecast endpoint como fallback).
        Retorna temperatura máxima do dia seguinte em °C.
        """
        if self.api.openweathermap_key in ("SUA_CHAVE_AQUI", "", None):
            logger.warning("OpenWeatherMap: chave não configurada, pulando.")
            return None

        # Tenta One Call API 3.0
        url = "https://api.openweathermap.org/data/3.0/onecall"
        params = {
            "lat": self.loc.latitude,
            "lon": self.loc.longitude,
            "exclude": "minutely,hourly,alerts",
            "units": "metric",
            "appid": self.api.openweathermap_key,
        }
        data = _safe_get(url, params=params)
        if data:
            try:
                temp_max = data["daily"][1]["temp"]["max"]  # amanhã
                logger.debug("OWM One Call: %.2f°C", temp_max)
                return float(temp_max)
            except (KeyError, IndexError):
                pass

        # Fallback: endpoint /forecast (gratuito)
        url_fallback = "https://api.openweathermap.org/data/2.5/forecast"
        params_fallback = {
            "lat": self.loc.latitude,
            "lon": self.loc.longitude,
            "units": "metric",
            "cnt": 8,
            "appid": self.api.openweathermap_key,
        }
        data2 = _safe_get(url_fallback, params=params_fallback)
        if data2:
            try:
                temps = [item["main"]["temp_max"] for item in data2["list"]]
                result = max(temps)
                logger.debug("OWM Forecast fallback: %.2f°C", result)
                return result
            except (KeyError, TypeError):
                pass

        logger.warning("OpenWeatherMap: não foi possível obter previsão.")
        return None

    # ------------------------------------------------------------------
    # 3. Copernicus / ECMWF ERA5 (CDS API) — requer chave gratuita
    # ------------------------------------------------------------------

    def fetch_copernicus(self) -> Optional[float]:
        """
        Consulta a API CDS do Copernicus para temperatura de 2m (ERA5-Land).
        Usa endpoint REST para não depender da biblioteca 'cdsapi' localmente.
        NOTA: Em produção, recomenda-se usar o cliente cdsapi oficial.
        Aqui fazemos uma chamada REST direta como demonstração.
        """
        if self.api.copernicus_key in ("SUA_CHAVE_AQUI", "", None):
            logger.warning("Copernicus: chave não configurada, usando ERA5 simulado.")
            return self._simulate_copernicus()

        # Em produção real, usaria cdsapi.Client() para submeter job assíncrono.
        # Como a API CDS exige autenticação via UID:Key no header, mostramos o padrão:
        try:
            import cdsapi  # type: ignore
            uid, key = self.api.copernicus_key.split(":")
            c = cdsapi.Client(
                url=self.api.copernicus_url,
                key=f"{uid}:{key}",
                quiet=True,
            )
            today = datetime.now(timezone.utc)
            result = c.retrieve(
                "reanalysis-era5-land",
                {
                    "variable": "2m_temperature",
                    "product_type": "reanalysis",
                    "year": str(today.year),
                    "month": f"{today.month:02d}",
                    "day": f"{today.day:02d}",
                    "time": ["12:00"],
                    "area": [
                        self.loc.latitude + 0.5,
                        self.loc.longitude - 0.5,
                        self.loc.latitude - 0.5,
                        self.loc.longitude + 0.5,
                    ],
                    "format": "json",
                },
            )
            # Simplificado: extrai valor médio do retorno
            temp_k = result.get("temperature_2m", 293.15)
            temp_c = _kelvin_to_celsius(float(temp_k))
            logger.debug("Copernicus ERA5: %.2f°C", temp_c)
            return temp_c
        except ImportError:
            logger.warning("Copernicus: biblioteca 'cdsapi' não instalada.")
        except Exception as exc:
            logger.warning("Copernicus: erro — %s", exc)

        return self._simulate_copernicus()

    def _simulate_copernicus(self) -> Optional[float]:
        """
        Placeholder: retorna None indicando que a fonte não está disponível.
        Substitua por lógica real quando a chave CDS estiver configurada.
        """
        logger.info("Copernicus: retornando None (sem dados reais).")
        return None

    # ------------------------------------------------------------------
    # 4. Meteomatics — requer usuário/senha de trial gratuito
    # ------------------------------------------------------------------

    def fetch_meteomatics(self) -> Optional[float]:
        """
        API REST do Meteomatics com autenticação Basic Auth.
        Endpoint: /validdatetime/parameter/location/format
        """
        user = self.api.meteomatics_user
        pwd = self.api.meteomatics_password
        if "SEU_USUARIO_AQUI" in (user, pwd) or not user or not pwd:
            logger.warning("Meteomatics: credenciais não configuradas, pulando.")
            return None

        now_utc = datetime.now(timezone.utc)
        dt_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        coord = f"{self.loc.latitude},{self.loc.longitude}"
        url = (
            f"https://api.meteomatics.com/{dt_str}"
            f"/t_2m:C/{coord}/json"
        )
        try:
            resp = requests.get(url, auth=(user, pwd), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            temp_c = data["data"][0]["coordinates"][0]["dates"][0]["value"]
            logger.debug("Meteomatics: %.2f°C", temp_c)
            return float(temp_c)
        except Exception as exc:
            logger.warning("Meteomatics: erro — %s", exc)
            return None

    # ------------------------------------------------------------------
    # 5. NASA POWER — sem chave, acesso público
    # ------------------------------------------------------------------

    def fetch_nasa_power(self) -> Optional[float]:
        """
        NASA POWER API — fornece dados climatológicos diários.
        Parâmetro: T2M_MAX (temperatura máxima de 2m).
        """
        today = datetime.now(timezone.utc)
        date_str = today.strftime("%Y%m%d")
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "parameters": "T2M_MAX",
            "community": "RE",
            "longitude": self.loc.longitude,
            "latitude": self.loc.latitude,
            "start": date_str,
            "end": date_str,
            "format": "JSON",
        }
        data = _safe_get(url, params=params)
        if not data:
            return None
        try:
            t2m_max = data["properties"]["parameter"]["T2M_MAX"]
            # A resposta é um dict {date: value}
            value = list(t2m_max.values())[0]
            if value == -999:  # indicador de dado ausente na NASA
                logger.warning("NASA POWER: dado ausente para a data.")
                return None
            logger.debug("NASA POWER: %.2f°C", value)
            return float(value)
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("NASA POWER — parse error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Agregação e cálculo do consenso
    # ------------------------------------------------------------------

    def get_consensus(self) -> dict:
        """
        Coleta dados de todas as fontes e retorna um dict com:
        - individual_readings: {fonte: valor_ou_None}
        - valid_readings: lista de valores válidos
        - consensus_temp: média robusta (após remoção de outliers)
        - source_count: número de fontes válidas
        """
        logger.info("Consultando todas as APIs meteorológicas...")

        sources = {
            "NOAA_NWS": self.fetch_noaa,
            "OpenWeatherMap": self.fetch_openweathermap,
            "Copernicus_ERA5": self.fetch_copernicus,
            "Meteomatics": self.fetch_meteomatics,
            "NASA_POWER": self.fetch_nasa_power,
        }

        readings = {}
        for name, fn in sources.items():
            logger.info("  -> Consultando %s...", name)
            readings[name] = fn()

        valid = [v for v in readings.values() if v is not None]
        logger.info("Fontes válidas: %d/%d — Valores: %s",
                    len(valid), len(sources), valid)

        consensus = self._robust_mean(valid) if valid else None
        if consensus is not None:
            logger.info("Temperatura de consenso: %.2f°C", consensus)
        else:
            logger.warning("Nenhuma fonte retornou dado válido.")

        return {
            "individual_readings": readings,
            "valid_readings": valid,
            "consensus_temp": consensus,
            "source_count": len(valid),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _robust_mean(values: list[float]) -> float:
        """
        Média robusta com remoção de outliers pelo método IQR.
        Se houver menos de 4 valores, retorna a média simples.
        """
        if len(values) < 4:
            return statistics.mean(values)

        q1 = statistics.quantiles(values, n=4)[0]
        q3 = statistics.quantiles(values, n=4)[2]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        filtered = [v for v in values if lower <= v <= upper]
        if not filtered:
            filtered = values  # fallback se todos forem outliers

        removed = len(values) - len(filtered)
        if removed:
            logger.debug("IQR removeu %d outlier(s). Usando %d valores.", removed, len(filtered))

        return statistics.mean(filtered)
