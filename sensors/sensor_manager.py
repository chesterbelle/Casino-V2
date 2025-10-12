"""
🎛️ Sensor Manager
-----------------
Orquesta los sensores técnicos y entrega señales a Gemini.
Cada sensor devuelve señales crudas con contexto y score de confianza.
"""

import logging
from typing import Dict, Iterable, List, Tuple

import config
from .reversion import BollingerTouch, KeltnerReversion, RSIReversion


SENSOR_REGISTRY: Dict[str, type] = {
    "RSIReversion": RSIReversion,
    "BollingerTouch": BollingerTouch,
    "KeltnerReversion": KeltnerReversion,
}


class SensorManager:
    def __init__(self):
        self.logger = logging.getLogger("SensorManager")
        self.sensors = list(self._load_sensors())
        self.cooldown_bars = max(0, int(getattr(config, "SENSOR_COOLDOWN_BARS", getattr(config, "SENSOR_COOLDOWN", 0)) or 0))
        self._candle_index = -1
        self._last_trigger: Dict[str, int] = {}

    def _load_sensors(self) -> Iterable[Tuple[str, object]]:
        """Instancia sensores activos definidos en config.py."""
        active_cfg: Dict[str, bool] = getattr(config, "ACTIVE_SENSORS", {}) or {}
        params_cfg: Dict[str, Dict] = getattr(config, "SENSOR_PARAMS", {}) or {}

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
        """
        self._candle_index += 1
        per_side: Dict[str, List[Tuple[str, dict]]] = {"LONG": [], "SHORT": []}

        for name, sensor in self.sensors:
            signal = sensor.check_signal(candle)
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

        consolidated: List[dict] = []
        for side, entries in per_side.items():
            if not entries:
                continue

            contributors = []
            range_score = 0
            merged_features: Dict[str, float] = {}

            sum_bbw = 0.0
            bbw_count = 0
            sum_atr = 0.0
            atr_count = 0
            avg_rsi = 0.0
            rsi_weight = 0

            for origin, sig in entries:
                contributors.append(origin)
                range_score += int(sig.get("range_score", 1) or 0)
                features = sig.get("features") or {}
                for feat_key, feat_val in features.items():
                    merged_features[f"{origin}.{feat_key}"] = feat_val

                if "bbw" in features:
                    sum_bbw += float(features["bbw"])
                    bbw_count += 1
                if "atr" in features:
                    sum_atr += float(features["atr"])
                    atr_count += 1
                if "rsi2" in features:
                    avg_rsi += float(features["rsi2"])
                    rsi_weight += 1

            bucket_features = dict(merged_features)
            if bbw_count > 0:
                bucket_features["bbw"] = sum_bbw / bbw_count
            if atr_count > 0:
                bucket_features["atr"] = sum_atr / atr_count
            if rsi_weight > 0:
                bucket_features["rsi2"] = avg_rsi / rsi_weight

            bucket_features["range_score"] = range_score if range_score > 0 else len(contributors)

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
