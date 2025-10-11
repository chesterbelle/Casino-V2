"""
🎛️ Sensor Manager
-----------------
Orquesta los sensores técnicos y entrega señales a Gemini.
Cada sensor devuelve señales crudas con contexto y score de confianza.
"""

import logging
from .rsi_reversion import RSIReversion
from .bollinger_touch import BollingerTouch
from .keltner_reversion import KeltnerReversion


class SensorManager:
    def __init__(self):
        self.logger = logging.getLogger("SensorManager")
        self.sensors = [
            RSIReversion(),
            BollingerTouch(),
            KeltnerReversion()
        ]

    def process_candle(self, candle: dict):
        """
        Ejecuta todos los sensores sobre una vela.
        Devuelve una lista de señales (LONG, SHORT o NONE).
        """
        signals = []
        for sensor in self.sensors:
            s = sensor.check_signal(candle)
            if s:
                self.logger.debug(f"📡 Señal detectada: {s}")
                signals.append(s)
        return signals

