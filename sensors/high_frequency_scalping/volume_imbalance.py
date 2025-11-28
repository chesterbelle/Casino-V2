"""
📊 Volume Flow Imbalance (OFI Proxy)
------------------------------------
Estima el desequilibrio de flujo de órdenes analizando la estructura interna de la vela.
Detecta agresión compradora/vendedora oculta.
"""

from collections import deque

import numpy as np


class VolumeFlowImbalance:
    def __init__(self, volume_period: int = 20, imbalance_ratio: float = 3.0):
        self.volume_period = volume_period
        self.imbalance_ratio = imbalance_ratio  # Presión compradora debe ser X veces mayor que la vendedora

        self.volumes = deque(maxlen=volume_period)

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])
        open_p = float(candle["open"])
        volume = float(candle["volume"])

        self.volumes.append(volume)

        if len(self.volumes) < self.volume_period:
            return None

        avg_volume = np.mean(self.volumes)

        # 1. Filtro de Volumen: Solo nos interesa si hay participación institucional
        if volume < avg_volume:
            return None

        # 2. Calcular Presiones (Aproximación por estructura de vela)
        # Buying Pressure: Distancia desde el Low hasta el Close (Empuje hacia arriba)
        # Selling Pressure: Distancia desde el High hasta el Close (Empuje hacia abajo)

        buying_pressure = close - low
        selling_pressure = high - close

        # Evitar división por cero
        if selling_pressure == 0:
            selling_pressure = 0.000001
        if buying_pressure == 0:
            buying_pressure = 0.000001

        signal = None

        # 3. Detectar Imbalance

        # Imbalance Alcista (Mucha compra, poca venta)
        # El precio cerró muy cerca del High, dejando mucha mecha abajo o cuerpo grande verde
        if buying_pressure > (selling_pressure * self.imbalance_ratio):
            # Confirmación adicional: Vela verde
            if close > open_p:
                signal = {"side": "LONG", "type": "buying_imbalance"}

        # Imbalance Bajista (Mucha venta, poca compra)
        # El precio cerró muy cerca del Low
        if selling_pressure > (buying_pressure * self.imbalance_ratio):
            # Confirmación adicional: Vela roja
            if close < open_p:
                signal = {"side": "SHORT", "type": "selling_imbalance"}

        if signal:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": signal["side"],
                "range_score": 2,  # Señal de flujo de órdenes
                "features": {"vol_ratio": volume / avg_volume, "imbalance_type": signal["type"]},
            }

        return None
