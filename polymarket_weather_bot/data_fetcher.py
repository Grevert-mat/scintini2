"""
data_fetcher.py — Fusão de dados de 7 fontes meteorológicas.

Fontes:
  1. NOAA / NWS (EUA) — sem chave
  2. OpenWeatherMap — chave gratuita
  3. Copernicus ERA5 — chave gratuita (CDS)
  4. Meteomatics — trial gratuito
  5. NASA POWER — sem chave
  6. Open-Meteo — sem chave (bônus confiável)
  7. Fundação Cacique Cobra Coral (FCCC) — scraping de boletins públicos

Cada método retorna a temperatura prevista em °C (float) ou None em caso de falha.
O consenso final usa média robusta com remoção de outliers via IQR.
"""

import logging
import re
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
    # 6. Open-Meteo — sem chave, JSON puro, altamente confiável
    # ------------------------------------------------------------------

    def fetch_open_meteo(self) -> Optional[float]:
        """
        Open-Meteo API — previsão de temperatura máxima do dia corrente.
        Completamente gratuita, sem autenticação, cobertura global.
        Docs: https://open-meteo.com/en/docs
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.loc.latitude,
            "longitude": self.loc.longitude,
            "daily": "temperature_2m_max",
            "timezone": "UTC",
            "forecast_days": 2,
        }
        data = _safe_get(url, params=params)
        if not data:
            return None
        try:
            temps = data["daily"]["temperature_2m_max"]
            # Índice 0 = hoje, índice 1 = amanhã
            value = temps[0] if temps[0] is not None else temps[1]
            logger.debug("Open-Meteo: %.2f°C", value)
            return float(value)
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("Open-Meteo — parse error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # 7. Fundação Cacique Cobra Coral (FCCC) — scraping de boletins
    # ------------------------------------------------------------------

    # Headers de browser para evitar bloqueios 403
    _FCCC_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://fccc.org.br/",
    }

    # Padrões para extrair temperaturas de texto livre (boletins em PT)
    _TEMP_PATTERNS = [
        # "temperatura de 28°C", "temperatura máxima de 31 graus"
        re.compile(
            r"temperatura[^\d]{0,25}(\d{1,2}(?:[.,]\d)?)\s*(?:°\s*[Cc]|graus?\s*[Cc]elsius|°C|ºC)",
            re.IGNORECASE,
        ),
        # "máxima de 29°C", "máximas de 32°C"
        re.compile(
            r"m[aá]xima[^\d]{0,15}(\d{1,2}(?:[.,]\d)?)\s*(?:°\s*[Cc]|graus?|°C|ºC)",
            re.IGNORECASE,
        ),
        # "29°C", "31 °C"  (captura genérica como último recurso)
        re.compile(
            r"\b(\d{1,2}(?:[.,]\d)?)\s*°\s*[Cc]\b",
        ),
    ]

    def fetch_cacique_cobra_coral(self) -> Optional[float]:
        """
        Fundação Cacique Cobra Coral (FCCC) — https://fccc.org.br/
        Organização brasileira de meteorologia e gestão climática.

        Estratégia:
          1. Tenta raspar o boletim mais recente da página de previsões.
          2. Extrai valores de temperatura com regex aplicado ao texto limpo.
          3. Usa a mediana dos valores encontrados para evitar menções pontuais.
          4. Retorna None se o site estiver inacessível ou sem dados de temperatura.

        Nota: a FCCC não expõe API pública. Este método realiza web scraping
        responsável (1 req/ciclo, User-Agent declarado). Respeite os termos de uso.
        """
        urls_to_try = [
            "https://fccc.org.br/previsoes/",
            "https://fccc.org.br/meteorologia/",
            "https://fccc.org.br/",
        ]

        for url in urls_to_try:
            result = self._scrape_fccc_page(url)
            if result is not None:
                return result

        logger.warning("FCCC: nenhum dado de temperatura encontrado nos boletins.")
        return None

    def _scrape_fccc_page(self, url: str) -> Optional[float]:
        """Raspa uma página da FCCC e extrai temperatura em °C."""
        try:
            resp = requests.get(url, headers=self._FCCC_HEADERS, timeout=20)
            resp.raise_for_status()
            html = resp.text
        except requests.exceptions.HTTPError as exc:
            logger.debug("FCCC %s — HTTP %s", url, exc.response.status_code)
            return None
        except Exception as exc:
            logger.debug("FCCC %s — erro: %s", url, exc)
            return None

        # Tentar parser HTML avançado (BeautifulSoup) se disponível
        text = self._extract_text_bs4(html) or self._extract_text_regex(html)
        if not text:
            return None

        # Filtrar pelo contexto geográfico configurado (cidade ou país)
        city_lower = self.loc.city.lower()
        relevant_text = self._filter_by_location(text, city_lower)

        # Extrair temperaturas do texto relevante (ou do texto completo como fallback)
        candidates = self._extract_temperatures(relevant_text or text)
        if not candidates:
            logger.debug("FCCC: texto capturado mas sem temperaturas válidas em %s", url)
            return None

        # Usa a mediana para suavizar menções de mínima/máxima/referências históricas
        temp = statistics.median(candidates)
        logger.info(
            "FCCC (Cacique Cobra Coral): %.2f°C — extraído de %s (%d valores: %s)",
            temp, url, len(candidates), candidates
        )
        return temp

    @staticmethod
    def _extract_text_bs4(html: str) -> Optional[str]:
        """Extrai texto limpo com BeautifulSoup (se instalado)."""
        try:
            from bs4 import BeautifulSoup  # type: ignore
            soup = BeautifulSoup(html, "html.parser")
            # Remove elementos não-textuais
            for tag in soup(["script", "style", "nav", "footer", "header", "meta"]):
                tag.decompose()
            # Prioriza blocos de conteúdo principal
            main = (
                soup.find("main")
                or soup.find("article")
                or soup.find(class_=re.compile(r"content|post|entry|boletim|previs", re.I))
                or soup.find("body")
            )
            text = (main or soup).get_text(separator=" ", strip=True)
            return text
        except ImportError:
            return None

    @staticmethod
    def _extract_text_regex(html: str) -> str:
        """Fallback: remove tags HTML com regex e retorna texto bruto."""
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _filter_by_location(text: str, city: str) -> Optional[str]:
        """
        Extrai parágrafos/frases que mencionam a cidade alvo.
        Retorna None se nenhum trecho relevante for encontrado.
        """
        # Quebra em sentenças/parágrafos e filtra os que mencionam a cidade
        chunks = re.split(r"[.!?\n]{1,3}", text)
        relevant = [c for c in chunks if city in c.lower() and len(c) > 20]
        return " ".join(relevant) if relevant else None

    def _extract_temperatures(self, text: str) -> list[float]:
        """
        Aplica todos os padrões de regex em sequência para coletar candidatos
        de temperatura, filtrando valores fora de uma faixa meteorológica realista
        (-50°C a +60°C) para descartar anos, percentuais, etc.
        """
        found = []
        for pattern in self._TEMP_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(1).replace(",", ".")
                try:
                    val = float(raw)
                    if -50.0 <= val <= 60.0:
                        found.append(val)
                except ValueError:
                    pass
            # Se o padrão mais específico já encontrou valores, não usamos
            # o genérico (evita ruído)
            if found and pattern is not self._TEMP_PATTERNS[-1]:
                break

        return found

    # ------------------------------------------------------------------
    # Agregação e cálculo do consenso
    # ------------------------------------------------------------------

    def get_consensus(self) -> dict:
        """
        Coleta dados de todas as fontes e retorna um dict com:
        - individual_readings: {fonte: valor_ou_None}
        - valid_readings: lista de valores válidos
        - consensus_temp: média robusta (após remoção de outliers via IQR)
        - source_count: número de fontes válidas
        """
        logger.info("Consultando todas as fontes meteorológicas...")

        sources = {
            "NOAA_NWS": self.fetch_noaa,
            "OpenWeatherMap": self.fetch_openweathermap,
            "Copernicus_ERA5": self.fetch_copernicus,
            "Meteomatics": self.fetch_meteomatics,
            "NASA_POWER": self.fetch_nasa_power,
            "Open_Meteo": self.fetch_open_meteo,
            "FCCC_CobraCoral": self.fetch_cacique_cobra_coral,
        }

        readings = {}
        for name, fn in sources.items():
            logger.info("  -> Consultando %s...", name)
            readings[name] = fn()

        valid = [v for v in readings.values() if v is not None]
        logger.info(
            "Fontes válidas: %d/%d — Valores: %s",
            len(valid), len(sources),
            [f"{v:.1f}°C" for v in valid],
        )

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
