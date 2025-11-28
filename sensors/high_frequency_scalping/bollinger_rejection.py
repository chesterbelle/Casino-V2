"""
🛡️ Bollinger Band Rejection
---------------------------
Detecta reversiones a la media confirmadas.
No basta con tocar la banda; el precio debe ser rechazado (cerrar dentro tras romper fuera).
"""

from collections import deque

import numpy as np


class BollingerBandRejection:
    def __init__(self, window: int = 20, std_dev: float = 2.0):
        self.window = window
        self.std_dev = std_dev
        self.closes = deque(maxlen=window)

        self.prev_close = None
        self.prev_high = None
        self.prev_low = None
        self.prev_upper = None
        self.prev_lower = None

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])

        self.closes.append(close)

        if len(self.closes) < self.window:
            self.prev_close = close
            self.prev_high = high
            self.prev_low = low
            return None

        # Calcular Bandas Actuales
        sma = np.mean(self.closes)
        std = np.std(self.closes)
        upper = sma + (std * self.std_dev)
        lower = sma - (std * self.std_dev)

        # Necesitamos el estado de la vela ANTERIOR para confirmar el rechazo
        if self.prev_upper is None:
            self.prev_close = close
            self.prev_high = high
            self.prev_low = low
            self.prev_upper = upper
            self.prev_lower = lower
            return None

        # Lógica de Rechazo (Reversal)
        # Buscamos que la vela ANTERIOR haya perforado la banda pero cerrado DENTRO (o cerca)
        # O que la vela ACTUAL confirme el regreso.

        # Estrategia: Vela Anterior rompió fuera, Vela Actual cierra dentro y en dirección contraria.

        signal = None

        # --- RECHAZO ALCISTA (Suelo) ---
        # 1. Vela previa tocó por debajo de la banda inferior
        if self.prev_low < self.prev_lower:
            # 2. Vela actual cierra por encima de la banda inferior (reingreso)
            # Y es una vela verde (close > open/prev_close)
            if close > lower and close > self.prev_close:
                signal = {"side": "LONG", "type": "bullish_rejection"}

        # --- RECHAZO BAJISTA (Techo) ---
        # 1. Vela previa tocó por encima de la banda superior
        if self.prev_high > self.prev_upper:
            # 2. Vela actual cierra por debajo de la banda superior (reingreso)
            # Y es una vela roja
            if close < upper and close < self.prev_close:
                signal = {"side": "SHORT", "type": "bearish_rejection"}

        # Actualizar estado previo
        self.prev_close = close
        self.prev_high = high
        self.prev_low = low
        self.prev_upper = upper
        self.prev_lower = lower

        if signal:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": signal["side"],
                "range_score": 1,
                "features": {"bbw": (upper - lower) / sma, "rejection_type": signal["type"]},
            }

        return None
