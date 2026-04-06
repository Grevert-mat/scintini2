"""
polymarket_client.py — Interface com a Polymarket CLOB e Gamma API.

Responsabilidades:
- Buscar o preço atual (mid-price) de um token YES/NO
- Buscar metadados do mercado (nome, data de resolução, status)
- Colocar ordens simuladas (paper trading) ou reais (via py-clob-client)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URLs base
# ---------------------------------------------------------------------------

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"


def _safe_get(url: str, params: dict = None, headers: dict = None,
              timeout: int = 15) -> Optional[dict | list]:
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
# Cliente Polymarket
# ---------------------------------------------------------------------------

class PolymarketClient:
    """
    Encapsula as chamadas à Polymarket CLOB e Gamma API.
    Em modo paper trading, as ordens são apenas simuladas (sem chamadas reais).
    """

    def __init__(self):
        self.token_id = config.market.token_id
        self.paper = config.bot.paper_trading

    # ------------------------------------------------------------------
    # Dados de mercado
    # ------------------------------------------------------------------

    def get_market_price(self) -> Optional[float]:
        """
        Retorna o mid-price atual do token YES no CLOB.
        Endpoint: GET /midpoint?token_id={token_id}
        Retorno: preço entre 0 e 1 (ex: 0.55 = 55% de chance)
        """
        url = f"{CLOB_API}/midpoint"
        params = {"token_id": self.token_id}
        data = _safe_get(url, params=params)
        if data is None:
            return None
        try:
            price = float(data["mid"])
            logger.info("Polymarket mid-price: $%.4f (%.1f%%)", price, price * 100)
            return price
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Polymarket get_market_price parse error: %s", exc)
            return None

    def get_orderbook(self) -> Optional[dict]:
        """
        Retorna o livro de ordens do token.
        Endpoint: GET /book?token_id={token_id}
        """
        url = f"{CLOB_API}/book"
        params = {"token_id": self.token_id}
        data = _safe_get(url, params=params)
        if not data:
            return None
        logger.debug("Orderbook obtido com sucesso.")
        return data

    def get_best_ask(self) -> Optional[float]:
        """Retorna o melhor preço de venda (ask mais baixo)."""
        book = self.get_orderbook()
        if not book:
            return None
        try:
            asks = book.get("asks", [])
            if not asks:
                return None
            best = min(float(a["price"]) for a in asks)
            logger.debug("Melhor ask: %.4f", best)
            return best
        except (KeyError, TypeError, ValueError):
            return None

    def get_best_bid(self) -> Optional[float]:
        """Retorna o melhor preço de compra (bid mais alto)."""
        book = self.get_orderbook()
        if not book:
            return None
        try:
            bids = book.get("bids", [])
            if not bids:
                return None
            best = max(float(b["price"]) for b in bids)
            logger.debug("Melhor bid: %.4f", best)
            return best
        except (KeyError, TypeError, ValueError):
            return None

    def get_market_info(self) -> Optional[dict]:
        """
        Busca metadados do mercado na Gamma API.
        Endpoint: GET /markets?clob_token_ids={token_id}
        """
        url = f"{GAMMA_API}/markets"
        params = {"clob_token_ids": self.token_id}
        data = _safe_get(url, params=params)
        if not data:
            return None
        try:
            # Gamma retorna lista de mercados
            markets = data if isinstance(data, list) else data.get("markets", [])
            if not markets:
                return None
            info = markets[0]
            logger.debug("Market info: %s | Status: %s | End: %s",
                         info.get("question", "N/A"),
                         info.get("active", "N/A"),
                         info.get("end_date_iso", "N/A"))
            return info
        except (IndexError, KeyError, TypeError) as exc:
            logger.warning("Gamma API parse error: %s", exc)
            return None

    def is_market_open(self) -> bool:
        """
        Verifica se o mercado ainda está aberto para negociação.
        """
        info = self.get_market_info()
        if info is None:
            logger.warning("Não foi possível verificar status do mercado. Assumindo fechado.")
            return False

        active = info.get("active", False)
        closed = info.get("closed", True)
        end_date_str = info.get("end_date_iso", "")

        if closed or not active:
            logger.info("Mercado está fechado ou inativo.")
            return False

        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) >= end_date:
                    logger.info("Mercado expirou em %s.", end_date_str)
                    return False
            except ValueError:
                pass

        return True

    # ------------------------------------------------------------------
    # Simulação de ordens (Paper Trading)
    # ------------------------------------------------------------------

    def place_buy_order(self, size_usd: float, price: float) -> dict:
        """
        Simula (ou executa) uma ordem de compra.

        Args:
            size_usd: valor em USD a investir
            price:    preço limite por token (0–1)

        Returns:
            dict com detalhes da ordem simulada/executada
        """
        shares = size_usd / price if price > 0 else 0

        if self.paper:
            logger.info(
                "[PAPER] COMPRA simulada — $%.4f a $%.4f/token = %.4f cotas",
                size_usd, price, shares
            )
            return {
                "status": "simulated",
                "side": "BUY",
                "size_usd": size_usd,
                "price": price,
                "shares": shares,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "order_id": f"PAPER-{int(datetime.now().timestamp())}",
            }

        # ---------------------------------------------------------------
        # Modo real: integração via py-clob-client
        # ---------------------------------------------------------------
        try:
            from py_clob_client.client import ClobClient  # type: ignore
            from py_clob_client.clob_types import OrderArgs, OrderType  # type: ignore

            private_key = config.api.__dict__.get("polymarket_private_key", "")
            client = ClobClient(
                host=CLOB_API,
                key=private_key,
                chain_id=137,  # Polygon mainnet
            )
            order_args = OrderArgs(
                token_id=self.token_id,
                price=price,
                size=shares,
                side="BUY",
                order_type=OrderType.GTC,
            )
            resp = client.create_and_post_order(order_args)
            logger.info("Ordem REAL enviada: %s", resp)
            return {"status": "submitted", **resp}
        except ImportError:
            logger.error("py-clob-client não instalado. Instale com: pip install py-clob-client")
            return {"status": "error", "message": "py-clob-client não instalado"}
        except Exception as exc:
            logger.error("Erro ao enviar ordem real: %s", exc)
            return {"status": "error", "message": str(exc)}

    def place_sell_order(self, shares: float, price: float) -> dict:
        """
        Simula (ou executa) uma ordem de venda.

        Args:
            shares: número de cotas a vender
            price:  preço limite por token (0–1)
        """
        proceeds = shares * price

        if self.paper:
            logger.info(
                "[PAPER] VENDA simulada — %.4f cotas a $%.4f/token = $%.4f",
                shares, price, proceeds
            )
            return {
                "status": "simulated",
                "side": "SELL",
                "shares": shares,
                "price": price,
                "proceeds_usd": proceeds,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "order_id": f"PAPER-{int(datetime.now().timestamp())}",
            }

        # Modo real — análogo ao buy
        logger.warning("Venda real não implementada neste exemplo.")
        return {"status": "error", "message": "Venda real não implementada"}
