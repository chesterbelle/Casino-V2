"""Placeholder Binance connector for Casino V2 v1.9.

Este conector se incluirá completamente en la versión v2.0. Por ahora solo
expone la firma requerida por `BaseConnector` y levanta `NotImplementedError`
para cada operación. Esto permite importar la arquitectura sin romper el
sistema mientras el desarrollo está en curso.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..connector_base import BaseConnector


class BinanceConnector(BaseConnector):
    """Placeholder Binance connector (testnet/mainnet)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        *,
        mode: str = "testing",
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.mode = mode

    # =========================================================
    # 🔌 CONNECTION MANAGEMENT
    # =========================================================
    async def connect(self) -> None:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    async def close(self) -> None:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    # =========================================================
    # 📊 MARKET DATA
    # =========================================================
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    # =========================================================
    # 💰 ACCOUNT DATA
    # =========================================================
    async def fetch_balance(self) -> Dict[str, Any]:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    # =========================================================
    # 📝 ORDER EXECUTION
    # =========================================================
    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    # =========================================================
    # 🔧 UTILITY METHODS
    # =========================================================
    def normalize_symbol(self, symbol: str) -> str:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    def denormalize_symbol(self, exchange_symbol: str) -> str:
        raise NotImplementedError("BinanceConnector estará disponible en v2.0")

    # =========================================================
    # 📊 PROPERTIES
    # =========================================================
    @property
    def exchange_name(self) -> str:
        return "binance"

    @property
    def is_connected(self) -> bool:
        return False
