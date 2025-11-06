"""Placeholder Hyperliquid connector for Casino V2 v1.9.

Implementación planificada para v2.1. Este módulo solo expone una clase que
cumple con la interfaz `BaseConnector`, pero cada método arroja
`NotImplementedError`. El objetivo es mantener la arquitectura lista sin
proveer funcionalidad aún.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..connector_base import BaseConnector


class HyperliquidConnector(BaseConnector):
    """Placeholder Hyperliquid connector."""

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

    async def connect(self) -> None:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    async def close(self) -> None:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    async def fetch_balance(self) -> Dict[str, Any]:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    def normalize_symbol(self, symbol: str) -> str:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    def denormalize_symbol(self, exchange_symbol: str) -> str:
        raise NotImplementedError("HyperliquidConnector estará disponible en v2.1")

    @property
    def exchange_name(self) -> str:
        return "hyperliquid"

    @property
    def is_connected(self) -> bool:
        return False
