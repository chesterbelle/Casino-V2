"""
🌊 VWAP Momentum
----------------
Estrategia institucional basada en VWAP (Volume Weighted Average Price).
El VWAP actúa como un imán y soporte/resistencia dinámico para instituciones.
Estrategia:
- Bullish: Precio > VWAP y rebota (retest) en él.
- Bearish: Precio < VWAP y es rechazado por él.
"""


class VWAPMomentum:
    def __init__(self, reset_period: int = 1440):  # Reset diario por defecto (1440 mins)
        self.reset_period = reset_period

        # Acumuladores para VWAP
        self.cum_vol = 0.0
        self.cum_vol_price = 0.0
        self.start_timestamp = None

        self.prev_close = None
        self.prev_vwap = None

    def _calculate_vwap(self, high, low, close, volume, timestamp):
        # Typical Price
        tp = (high + low + close) / 3.0

        # Reset logic (simple daily reset approximation or rolling window if needed)
        # Para scalping continuo, usaremos un "Rolling VWAP" o reset diario si tuvieramos info de dia.
        # Aquí usaremos un enfoque de sesión simplificado: Si pasa mucho tiempo, reseteamos?
        # Mejor: Rolling VWAP de N periodos para adaptarse a crypto 24/7
        # Ojo: El VWAP real es "desde el inicio de la sesión". En crypto 24/7, suele ser 00:00 UTC.
        # Asumiremos reset si detectamos cambio de día (timestamp)

        # Extraer día del timestamp (ms)
        current_day = int(timestamp / (1000 * 60 * 60 * 24))

        if self.start_timestamp is None:
            self.start_timestamp = current_day

        if current_day > self.start_timestamp:
            # Reset diario
            self.cum_vol = 0.0
            self.cum_vol_price = 0.0
            self.start_timestamp = current_day

        self.cum_vol += volume
        self.cum_vol_price += tp * volume

        if self.cum_vol == 0:
            return tp

        return self.cum_vol_price / self.cum_vol

    def check_signal(self, candle: dict):
        timestamp = candle["timestamp"]
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])
        volume = float(candle["volume"])
        open_p = float(candle["open"])

        vwap = self._calculate_vwap(high, low, close, volume, timestamp)

        if self.prev_close is None:
            self.prev_close = close
            self.prev_vwap = vwap
            return None

        signal = None

        # Lógica de Rebote (Retest)

        # CASO LONG: Tendencia Alcista (Close > VWAP)
        # El precio baja a tocar el VWAP y rebota.
        if close > vwap:
            # Vela anterior o actual tocó el VWAP (o estuvo muy cerca, 0.1%)
            dist_pct = abs(low - vwap) / vwap
            if dist_pct < 0.001:  # 0.1% de cercanía
                # Y la vela es alcista (rechazo del VWAP hacia arriba)
                if close > open_p:
                    signal = {"side": "LONG", "type": "vwap_bounce"}

        # CASO SHORT: Tendencia Bajista (Close < VWAP)
        # El precio sube a tocar el VWAP y es rechazado.
        if close < vwap:
            dist_pct = abs(high - vwap) / vwap
            if dist_pct < 0.001:
                # Y la vela es bajista (rechazo del VWAP hacia abajo)
                if close < open_p:
                    signal = {"side": "SHORT", "type": "vwap_rejection"}

        self.prev_close = close
        self.prev_vwap = vwap

        if signal:
            return {
                "timestamp": timestamp,
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": signal["side"],
                "range_score": 2,  # Señal institucional fuerte
                "features": {"vwap": vwap, "dist_pct": abs(close - vwap) / vwap, "type": signal["type"]},
            }

        return None
