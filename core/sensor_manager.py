"""
Sensor Manager for Casino-V3.
Orchestrates sensors, manages cooldowns, and emits SignalEvents.

Optimized with ProcessPoolExecutor for parallel sensor execution.
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Tuple

from .bar_aggregator import BarAggregator
from .events import CandleEvent, EventType, SignalEvent

logger = logging.getLogger(__name__)

# Number of worker processes for parallel sensor execution
# Use half of CPU cores to leave room for other tasks
SENSOR_WORKERS = max(2, (os.cpu_count() or 4) // 2)


def _calculate_sensor(sensor_data: Tuple) -> Tuple[str, dict]:
    """
    Worker function for parallel sensor calculation.

    This runs in a separate process to bypass GIL for CPU-bound numpy operations.

    Args:
        sensor_data: Tuple of (sensor_instance, candle_data)

    Returns:
        Tuple of (sensor_name, signal_or_none)
    """
    sensor, candle_data = sensor_data
    try:
        signal = sensor.calculate(candle_data)
        return (sensor.name, signal)
    except Exception as e:
        return (sensor.name, {"error": str(e)})


class SensorManager:
    """
    Orchestrates V3 Sensors.
    Subscribes to CANDLE events, executes sensors, and emits SIGNAL events.
    """

    def __init__(self, engine, timeframe: str = "1m"):
        self.engine = engine
        self.timeframe = timeframe
        self.sensors = []
        self.cooldown_bars = 5  # Default cooldown
        self._candle_index = -1
        self._last_trigger: Dict[str, int] = {}

        # Bar aggregator for multi-timeframe support
        self.bar_aggregator = BarAggregator()

        # ProcessPoolExecutor for parallel sensor execution
        self._executor = ProcessPoolExecutor(max_workers=SENSOR_WORKERS)
        self._parallel_enabled = True  # Can disable for debugging
        logger.info(f"⚡ SensorManager using {SENSOR_WORKERS} worker processes")

        # Subscribe to Candles
        self.engine.subscribe(EventType.CANDLE, self.on_candle)

        # Load Sensors
        self._load_sensors()

    def _load_sensors(self):
        """Load enabled sensors from config."""
        # Import all V3 sensors
        from config.sensors import ACTIVE_SENSORS
        from sensors.absorption_block import AbsorptionBlockV3
        from sensors.adaptive_rsi import AdaptiveRSIV3
        from sensors.adx_filter import ADXFilterV3
        from sensors.bollinger_rejection import BollingerRejectionV3
        from sensors.bollinger_squeeze import BollingerSqueezeV3
        from sensors.bollinger_touch import BollingerTouchV3
        from sensors.cci_reversion import CCIReversionV3
        from sensors.deceleration_candles import DecelerationCandlesV3
        from sensors.doji_indecision import DojiIndecisionV3
        from sensors.ema50_support import EMA50SupportV3
        from sensors.ema_crossover import EMACrossoverV3
        from sensors.engulfing_pattern import EngulfingPatternV3
        from sensors.extreme_candle_ratio import ExtremeCandleRatioV3
        from sensors.fakeout import FakeoutV3
        from sensors.fvg_retest import FVGRetestV3
        from sensors.higher_tf_trend import HigherTFTrendV3
        from sensors.hurst_regime import HurstRegimeV3
        from sensors.inside_bar_breakout import InsideBarBreakoutV3
        from sensors.keltner_breakout import KeltnerBreakoutV3
        from sensors.keltner_reversion import KeltnerReversionV3
        from sensors.liquidity_void import LiquidityVoidV3
        from sensors.long_tail import LongTailV3
        from sensors.macd_crossover import MACDCrossoverV3
        from sensors.marubozu_momentum import MarubozuMomentumV3
        from sensors.micro_trend import MicroTrendV3
        from sensors.momentum_burst import MomentumBurstV3
        from sensors.morning_star import MorningStarV3
        from sensors.mtf_impulse import MTFImpulseV3
        from sensors.order_block import OrderBlockV3
        from sensors.parabolic_sar import ParabolicSARV3
        from sensors.pinbar_reversal import PinBarReversalV3
        from sensors.rails_pattern import RailsPatternV3
        from sensors.rsi_reversion import RSIReversionV3
        from sensors.smart_range import SmartRangeV3
        from sensors.stochastic_reversion import StochasticReversionV3
        from sensors.supertrend import SupertrendV3
        from sensors.support_resistance import SupportResistanceV3
        from sensors.three_bar import ThreeBarV3
        from sensors.tweezer_pattern import TweezerPatternV3
        from sensors.vcp_pattern import VCPPatternV3
        from sensors.volatility_wakeup import VolatilityWakeupV3
        from sensors.volume_imbalance import VolumeImbalanceV3
        from sensors.volume_spike import VolumeSpikeV3
        from sensors.vsa_reversal import VSAReversalV3
        from sensors.vwap_breakout import VWAPBreakoutV3
        from sensors.vwap_deviation import VWAPDeviationV3
        from sensors.vwap_momentum import VWAPMomentumV3
        from sensors.wick_rejection import WickRejectionV3
        from sensors.williams_r_reversion import WilliamsRReversionV3
        from sensors.wyckoff_spring import WyckoffSpringV3
        from sensors.zscore_reversion import ZScoreReversionV3

        # Map of sensor class names (or names) to classes
        sensor_classes = [
            EMACrossoverV3,
            PinBarReversalV3,
            RailsPatternV3,
            EMA50SupportV3,
            MarubozuMomentumV3,
            VWAPBreakoutV3,
            ExtremeCandleRatioV3,
            InsideBarBreakoutV3,
            DecelerationCandlesV3,
            VWAPDeviationV3,
            VCPPatternV3,
            EngulfingPatternV3,
            RSIReversionV3,
            BollingerTouchV3,
            KeltnerReversionV3,
            MACDCrossoverV3,
            SupertrendV3,
            StochasticReversionV3,
            CCIReversionV3,
            WilliamsRReversionV3,
            ZScoreReversionV3,
            ADXFilterV3,
            BollingerSqueezeV3,
            ParabolicSARV3,
            MomentumBurstV3,
            VolumeImbalanceV3,
            OrderBlockV3,
            FVGRetestV3,
            DojiIndecisionV3,
            MorningStarV3,
            LongTailV3,
            AbsorptionBlockV3,
            LiquidityVoidV3,
            FakeoutV3,
            HigherTFTrendV3,
            MTFImpulseV3,
            AdaptiveRSIV3,
            BollingerRejectionV3,
            HurstRegimeV3,
            KeltnerBreakoutV3,
            MicroTrendV3,
            SmartRangeV3,
            VolatilityWakeupV3,
            VSAReversalV3,
            VWAPMomentumV3,
            WickRejectionV3,
            WyckoffSpringV3,
            VolumeSpikeV3,
            TweezerPatternV3,
            ThreeBarV3,
            SupportResistanceV3,
        ]

        # Get sensors from enabled strategies
        from config.strategies import get_active_sensors, get_enabled_strategies

        strategy_sensors = get_active_sensors()
        enabled_strategies = get_enabled_strategies()

        if strategy_sensors:
            logger.info(f"📊 Active strategies: {enabled_strategies}")
            logger.info(f"📊 Strategy sensors: {len(strategy_sensors)} sensors")

        # Instantiate sensors that are:
        # 1. Enabled in ACTIVE_SENSORS (legacy filter)
        # 2. Part of an enabled strategy (new filter)
        for sensor_cls in sensor_classes:
            sensor = sensor_cls()

            # Check legacy ACTIVE_SENSORS first
            if not ACTIVE_SENSORS.get(sensor.name, False):
                continue

            # If strategies are defined, also check strategy membership
            if strategy_sensors and sensor.name not in strategy_sensors:
                logger.debug(f"⏭️ Skipping {sensor.name} - not in active strategy")
                continue

            self.sensors.append(sensor)

        logger.info(f"✅ SensorManager loaded {len(self.sensors)} sensors " f"for timeframe {self.timeframe}")

    async def on_candle(self, event: CandleEvent):
        """
        Process new candle with parallel sensor execution.

        Uses ProcessPoolExecutor to run CPU-bound sensor calculations
        in parallel, bypassing Python's GIL.
        """
        self._candle_index += 1
        start_time = time.time()

        candle_data = {
            "timestamp": event.timestamp,
            "open": event.open,
            "high": event.high,
            "low": event.low,
            "close": event.close,
            "volume": event.volume,
        }

        # Build MTF context using BarAggregator
        context = self.bar_aggregator.on_candle(candle_data)

        # Filter sensors by cooldown first
        active_sensors = [s for s in self.sensors if self._can_fire(s.name)]

        if not active_sensors:
            return

        if self._parallel_enabled and len(active_sensors) > 1:
            # Parallel execution using ProcessPoolExecutor
            await self._process_sensors_parallel(active_sensors, context)
        else:
            # Sequential fallback (for debugging or single sensor)
            await self._process_sensors_sequential(active_sensors, context)

        # Log timing every 100 candles
        if self._candle_index % 100 == 0:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"⚡ Candle {self._candle_index} | " f"{len(active_sensors)} sensors | {elapsed:.1f}ms")

    async def _process_sensors_parallel(self, active_sensors: List, candle_data: dict):
        """Execute sensors in parallel using ProcessPoolExecutor."""
        loop = asyncio.get_event_loop()

        # Create tasks for parallel execution
        # Note: We pass (sensor, candle_data) tuples to the worker function
        tasks = [
            loop.run_in_executor(self._executor, _calculate_sensor, (sensor, candle_data)) for sensor in active_sensors
        ]

        # Wait for all sensors to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for sensor, result in zip(active_sensors, results):
            if isinstance(result, Exception):
                logger.error(f"❌ Sensor {sensor.name} exception: {result}")
                continue

            sensor_name, signal = result

            if signal:
                if "error" in signal:
                    logger.error(f"❌ Sensor {sensor_name}: {signal['error']}")
                else:
                    await self._emit_signal(signal, sensor_name)
                    self._last_trigger[sensor_name] = self._candle_index

    async def _process_sensors_sequential(self, active_sensors: List, candle_data: dict):
        """Execute sensors sequentially (fallback mode)."""
        for sensor in active_sensors:
            try:
                signal = sensor.calculate(candle_data)
                if signal:
                    await self._emit_signal(signal, sensor.name)
                    self._last_trigger[sensor.name] = self._candle_index
            except Exception as e:
                logger.error(f"❌ Error in sensor {sensor.name}: {e}")

    def _can_fire(self, sensor_name: str) -> bool:
        """Check cooldown."""
        last_index = self._last_trigger.get(sensor_name)
        if last_index is None:
            return True
        return (self._candle_index - last_index) >= self.cooldown_bars

    async def _emit_signal(self, signal_data: dict, sensor_name: str):
        """Emit SignalEvent."""
        from config.sensors import get_sensor_params

        metadata = signal_data.get("metadata", {})

        # Inject TP/SL from config (timeframe-specific)
        sensor_config = get_sensor_params(sensor_name, self.timeframe)
        if "tp_pct" in sensor_config:
            metadata["tp_pct"] = sensor_config["tp_pct"]
        if "sl_pct" in sensor_config:
            metadata["sl_pct"] = sensor_config["sl_pct"]

        event = SignalEvent(
            type=EventType.SIGNAL,
            timestamp=time.time(),
            symbol=self.engine.data_feed.adapter.symbol,
            side=signal_data["side"],
            sensor_id=sensor_name,  # Changed from strategy_name to sensor_id
            score=signal_data.get("score", 1.0),
            metadata=metadata,
        )
        logger.info(f"📡 Signal Detected: {sensor_name} -> {signal_data['side']}")
        await self.engine.dispatch(event)
