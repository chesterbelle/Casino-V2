"""
🎛️ Sensor Manager
-----------------
Orquesta los sensores técnicos y entrega señales a Gemini.
Cada sensor devuelve señales crudas con contexto y score de confianza.
"""

import logging
from typing import Dict, Iterable, List, Tuple

from config import sensors as sensors_config

from .mean_reversion import (
    BollingerSqueeze,
    BollingerTouch,
    CCIReversion,
    KeltnerReversion,
    RSIReversion,
    StochasticReversion,
    WilliamsRReversion,
    ZScoreReversion,
)
from .momentum_trend_following import (
    ADXFilter,
    EMACrossover,
    MACDCrossover,
    ParabolicSAR,
    Supertrend,
)
from .volumen_flujo_capital import (
    AccumulationDistribution,
    MFIReversion,
    OBVBreakout,
    VWAPDeviation,
)

SENSOR_REGISTRY: Dict[str, type] = {
    # Mean Reversion (8 sensores)
    "RSIReversion": RSIReversion,
    "BollingerTouch": BollingerTouch,
    "KeltnerReversion": KeltnerReversion,
    "StochasticReversion": StochasticReversion,
    "BollingerSqueeze": BollingerSqueeze,
    "WilliamsRReversion": WilliamsRReversion,
    "CCIReversion": CCIReversion,
    "ZScoreReversion": ZScoreReversion,
    # Momentum / Trend (5 sensores)
    "EMACrossover": EMACrossover,
    "MACDCrossover": MACDCrossover,
    "Supertrend": Supertrend,
    "ADXFilter": ADXFilter,
    "ParabolicSAR": ParabolicSAR,
    # Volume (4 sensores)
    "OBVBreakout": OBVBreakout,
    "VWAPDeviation": VWAPDeviation,
    "MFIReversion": MFIReversion,
    "AccumulationDistribution": AccumulationDistribution,
}


class SensorManager:
    def __init__(self):
        self.logger = logging.getLogger("SensorManager")
        self.sensors = list(self._load_sensors())
        self.cooldown_bars = max(
            0, int(getattr(sensors_config, "SENSOR_COOLDOWN_BARS", getattr(sensors_config, "SENSOR_COOLDOWN", 0)) or 0)
        )
        self._candle_index = -1
        self._last_trigger: Dict[str, int] = {}

    def _load_sensors(self) -> Iterable[Tuple[str, object]]:
        """Instancia sensores activos definidos en config.py."""
        active_cfg: Dict[str, bool] = getattr(sensors_config, "ACTIVE_SENSORS", {}) or {}
        params_cfg: Dict[str, Dict] = getattr(sensors_config, "SENSOR_PARAMS", {}) or {}

        sensors = []
        items = active_cfg.items() if active_cfg else ((name, True) for name in SENSOR_REGISTRY.keys())

        for name, enabled in items:
            if not enabled:
                self.logger.info(f"🛑 Sensor desactivado por config: {name}")
                continue

            sensor_cls = SENSOR_REGISTRY.get(name)
            if sensor_cls is None:
                self.logger.warning(f"⚠️ Sensor '{name}' no registrado. Revísalo en config.ACTIVE_SENSORS.")
                continue

            params = params_cfg.get(name, {})
            try:
                instance = sensor_cls(**params)
            except TypeError as exc:
                self.logger.error(f"❌ No se pudo instanciar {name} con params {params}: {exc}")
                continue

            sensors.append((name, instance))
            self.logger.info(f"✅ Sensor cargado: {name} (params={params or 'default'})")

        if not sensors:
            self.logger.warning("⚠️ Ningún sensor activo. Gemini no recibirá señales.")

        return sensors

    def process_candle(self, candle: dict) -> List[dict]:
        """
        Ejecuta todos los sensores sobre una vela.
        Devuelve una lista de señales (LONG, SHORT o NONE).

        Optimizado con caching para mejorar performance.
        """
        self._candle_index += 1
        per_side: Dict[str, List[Tuple[str, dict]]] = {"LONG": [], "SHORT": []}

        # Process sensors in batches to reduce memory pressure
        batch_size = getattr(sensors_config, "SENSOR_BATCH_SIZE", 5)
        sensor_batches = [self.sensors[i : i + batch_size] for i in range(0, len(self.sensors), batch_size)]

        for batch in sensor_batches:
            for name, sensor in batch:
                # Try cache first for expensive sensors
                from core.cache import sensor_cache

                cached_signal = sensor_cache.get_signal(name, candle)
                if cached_signal is not None:
                    signal = cached_signal
                    self.logger.debug(f"💾 Cache hit for {name}")
                else:
                    signal = sensor.check_signal(candle)
                    if signal:  # Only cache non-empty signals
                        sensor_cache.set_signal(name, candle, signal)

                if not signal:
                    continue

                if not self._can_fire(name):
                    self.logger.debug(f"⏸️ Cooldown activo para {name}; señal ignorada.")
                    continue

                side = signal.get("side", "").upper()
                if side not in per_side:
                    self.logger.debug(f"⚠️ Señal descartada por lado inválido: {signal}")
                    continue

                signal.setdefault("origin", name)
                self.logger.debug(f"📡 Señal detectada: {signal}")
                per_side[side].append((name, signal))
                self._last_trigger[name] = self._candle_index

        # Memory-efficient consolidation using generators
        consolidated: List[dict] = []
        for side, entries in per_side.items():
            if not entries:
                continue

            # Use generator expressions for memory efficiency
            contributors = [origin for origin, _ in entries]
            range_scores = (int(sig.get("range_score", 1) or 0) for _, sig in entries)

            # Calculate aggregates efficiently
            features_iter = ((origin, sig.get("features") or {}) for origin, sig in entries)

            merged_features: Dict[str, float] = {}
            bbw_values = []
            atr_values = []
            rsi_values = []

            for origin, features in features_iter:
                for feat_key, feat_val in features.items():
                    merged_features[f"{origin}.{feat_key}"] = feat_val

                if "bbw" in features:
                    bbw_values.append(float(features["bbw"]))
                if "atr" in features:
                    atr_values.append(float(features["atr"]))
                if "rsi2" in features:
                    rsi_values.append(float(features["rsi2"]))

            # Efficient aggregation
            bucket_features = dict(merged_features)
            if bbw_values:
                bucket_features["bbw"] = sum(bbw_values) / len(bbw_values)
            if atr_values:
                bucket_features["atr"] = sum(atr_values) / len(atr_values)
            if rsi_values:
                bucket_features["rsi2"] = sum(rsi_values) / len(rsi_values)

            total_range_score = sum(range_scores)
            bucket_features["range_score"] = total_range_score if total_range_score > 0 else len(contributors)

            base_signal = {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": side,
                "origin": "Composite",
                "range_score": bucket_features["range_score"],
                "contributors": contributors,
                "features": bucket_features,
            }
            consolidated.append(base_signal)

        return consolidated

    def _can_fire(self, sensor_name: str) -> bool:
        """Aplica cooldown por sensor para evitar señales consecutivas sin reseteo."""
        if self.cooldown_bars <= 0:
            return True
        last_index = self._last_trigger.get(sensor_name)
        if last_index is None:
            return True
        return (self._candle_index - last_index) >= self.cooldown_bars
