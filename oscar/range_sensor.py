"""
Range sensor exclusivo para el modo Oscar.

Este módulo reimplementa la lógica del RangeDetector del bot original
Range Grinder Futures 2.0 en un formato utilizable dentro de Casino V2
sin tocar el `SensorManager` existente. La idea es que el orquestador
Oscar consuma este sensor directamente para decidir entradas y salidas,
mientras el resto de sensores siguen alimentando sus propias memorias.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Optional, Tuple, Dict, Any

import numpy as np

logger = logging.getLogger("OscarRangeSensor")


class RangeDetector:
    """
    Detector de rangos simple basado únicamente en la serie de precios.

    Mantiene una ventana de cierres recientes y:
      • Detecta swing highs / swing lows para identificar soportes y resistencias.
      • Verifica que la volatilidad relativa esté por debajo de un umbral
        (mercado “en rango”).
      • Devuelve soporte/resistencia ajustados con un spread mínimo.
    """

    def __init__(
        self,
        window: int = 75,
        atr_period: int = 14,
        consolidation_threshold: float = 0.01,
        min_spread_ratio: float = 0.005,
    ) -> None:
        self.window = window
        self.atr_period = atr_period
        self.consolidation_threshold = consolidation_threshold
        self.min_spread_ratio = min_spread_ratio
        self.price_history: deque[float] = deque(maxlen=window)

    def add_price(self, price: float) -> None:
        self.price_history.append(price)

    # ------------------------------------------------------
    # Detección de rangos
    # ------------------------------------------------------
    def _detect_levels(self) -> Tuple[Optional[float], Optional[float]]:
        if len(self.price_history) < self.window:
            return None, None

        prices = list(self.price_history)
        swing_highs = []
        swing_lows = []
        lookback = 1  # sensibilidad alta

        for i in range(lookback, len(prices) - lookback):
            price = prices[i]
            if all(price > prices[i - j] and price > prices[i + j] for j in range(1, lookback + 1)):
                swing_highs.append(price)
            if all(price < prices[i - j] and price < prices[i + j] for j in range(1, lookback + 1)):
                swing_lows.append(price)

        support = min(swing_lows[-5:]) if swing_lows else None
        resistance = max(swing_highs[-5:]) if swing_highs else None

        if support and resistance and support >= resistance:
            return None, None

        if support and resistance:
            spread = resistance - support
            min_spread = support * self.min_spread_ratio
            if spread < min_spread:
                adjustment = (min_spread - spread) / 2
                support -= adjustment
                resistance += adjustment

        return support, resistance

    def _is_in_range(self) -> bool:
        if len(self.price_history) < self.window:
            return False

        prices = np.asarray(self.price_history)
        mean_price = prices.mean()
        if mean_price == 0:
            return False

        volatility = prices.std() / mean_price
        return volatility < self.consolidation_threshold

    def get_range(self) -> Tuple[Optional[float], Optional[float]]:
        support, resistance = self._detect_levels()
        if not support or not resistance:
            return None, None
        if not self._is_in_range():
            return None, None
        return support, resistance


class RangeSensor:
    """
    Wrapper ligero que expone una interfaz tipo sensor:

        sensor = RangeSensor()
        signal = sensor.process(candle)

    Retorna None si no hay rango válido o dict con señal LONG/SHORT
    cuando el precio se aproxima al soporte/resistencia detectados.
    """

    def __init__(
        self,
        window: int = 75,
        consolidation_threshold: float = 0.01,
        buffer_percent: float = 0.005,
        min_spread_ratio: float = 0.005,
    ) -> None:
        self.detector = RangeDetector(
            window=window,
            atr_period=14,
            consolidation_threshold=consolidation_threshold,
            min_spread_ratio=min_spread_ratio,
        )
        self.buffer_percent = buffer_percent

    def process(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Actualiza el detector con la vela actual y, si corresponde, devuelve
        una señal con formato estandarizado.
        """
        try:
            close = float(candle["close"])
        except (KeyError, TypeError, ValueError):
            logger.debug("Vela sin precio de cierre válido, ignorando.")
            return None

        self.detector.add_price(close)
        support, resistance = self.detector.get_range()

        if support is None or resistance is None:
            return None

        side: Optional[str] = None
        buy_zone = support * (1 + self.buffer_percent)
        sell_zone = resistance * (1 - self.buffer_percent)

        if close <= buy_zone:
            side = "LONG"
        elif close >= sell_zone:
            side = "SHORT"

        if side is None:
            return None

        signal = {
            "timestamp": candle.get("timestamp"),
            "symbol": candle.get("symbol", "UNKNOWN"),
            "timeframe": candle.get("timeframe", "UNKNOWN"),
            "side": side,
            "price": close,
            "support": support,
            "resistance": resistance,
            "buffer_percent": self.buffer_percent,
        }

        logger.debug("RangeSensor emitió señal: %s", signal)
        return signal

