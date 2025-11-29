"""
Sensor Manager for Casino-V3.
Orchestrates sensors, manages cooldowns, and emits SignalEvents.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple

from .events import Event, CandleEvent, SignalEvent, EventType
from config import sensors as sensors_config

logger = logging.getLogger(__name__)

class SensorManager:
    """
    Orchestrates V3 Sensors.
    Subscribes to CANDLE events, executes sensors, and emits SIGNAL events.
    """
    def __init__(self, engine):
        self.engine = engine
        self.sensors = []
        self.cooldown_bars = 5 # Default cooldown
        self._candle_index = -1
        self._last_trigger: Dict[str, int] = {}
        
        # Subscribe to Candles
        self.engine.subscribe(EventType.CANDLE, self.on_candle)
        
        # Load Sensors
        self._load_sensors()

    def _load_sensors(self):
        """Load enabled sensors from config."""
        # Import all V3 sensors
        from strategies.v3.sensors.ema_crossover import EMACrossoverV3
        from strategies.v3.sensors.pinbar_reversal import PinBarReversalV3
        from strategies.v3.sensors.rails_pattern import RailsPatternV3
        from strategies.v3.sensors.ema50_support import EMA50SupportV3
        from strategies.v3.sensors.marubozu_momentum import MarubozuMomentumV3
        from strategies.v3.sensors.vwap_breakout import VWAPBreakoutV3
        from strategies.v3.sensors.extreme_candle_ratio import ExtremeCandleRatioV3
        from strategies.v3.sensors.inside_bar_breakout import InsideBarBreakoutV3
        from strategies.v3.sensors.deceleration_candles import DecelerationCandlesV3
        from strategies.v3.sensors.vwap_deviation import VWAPDeviationV3
        from strategies.v3.sensors.vcp_pattern import VCPPatternV3
        from strategies.v3.sensors.engulfing_pattern import EngulfingPatternV3
        from strategies.v3.sensors.rsi_reversion import RSIReversionV3
        from strategies.v3.sensors.bollinger_touch import BollingerTouchV3
        from strategies.v3.sensors.keltner_reversion import KeltnerReversionV3
        from strategies.v3.sensors.macd_crossover import MACDCrossoverV3
        from strategies.v3.sensors.supertrend import SupertrendV3
        from strategies.v3.sensors.stochastic_reversion import StochasticReversionV3
        from strategies.v3.sensors.cci_reversion import CCIReversionV3
        from strategies.v3.sensors.williams_r_reversion import WilliamsRReversionV3
        from strategies.v3.sensors.zscore_reversion import ZScoreReversionV3
        from strategies.v3.sensors.adx_filter import ADXFilterV3
        from strategies.v3.sensors.bollinger_squeeze import BollingerSqueezeV3
        from strategies.v3.sensors.parabolic_sar import ParabolicSARV3
        from strategies.v3.sensors.momentum_burst import MomentumBurstV3
        from strategies.v3.sensors.volume_imbalance import VolumeImbalanceV3
        from strategies.v3.sensors.order_block import OrderBlockV3
        from strategies.v3.sensors.fvg_retest import FVGRetestV3
        from strategies.v3.sensors.doji_indecision import DojiIndecisionV3
        from strategies.v3.sensors.morning_star import MorningStarV3
        from strategies.v3.sensors.long_tail import LongTailV3
        from strategies.v3.sensors.absorption_block import AbsorptionBlockV3
        from strategies.v3.sensors.liquidity_void import LiquidityVoidV3
        from strategies.v3.sensors.fakeout import FakeoutV3
        from strategies.v3.sensors.higher_tf_trend import HigherTFTrendV3
        from strategies.v3.sensors.mtf_impulse import MTFImpulseV3
        from strategies.v3.sensors.adaptive_rsi import AdaptiveRSIV3
        from strategies.v3.sensors.bollinger_rejection import BollingerRejectionV3
        from strategies.v3.sensors.hurst_regime import HurstRegimeV3
        from strategies.v3.sensors.keltner_breakout import KeltnerBreakoutV3
        from strategies.v3.sensors.micro_trend import MicroTrendV3
        from strategies.v3.sensors.smart_range import SmartRangeV3
        from strategies.v3.sensors.volatility_wakeup import VolatilityWakeupV3
        from strategies.v3.sensors.vsa_reversal import VSAReversalV3
        from strategies.v3.sensors.vwap_momentum import VWAPMomentumV3
        from strategies.v3.sensors.wick_rejection import WickRejectionV3
        from strategies.v3.sensors.wyckoff_spring import WyckoffSpringV3
        from strategies.v3.sensors.volume_spike import VolumeSpikeV3
        from strategies.v3.sensors.tweezer_pattern import TweezerPatternV3
        from strategies.v3.sensors.three_bar import ThreeBarV3
        from strategies.v3.sensors.support_resistance import SupportResistanceV3
        
        # Instantiate all sensors
        self.sensors.extend([
            EMACrossoverV3(), PinBarReversalV3(), RailsPatternV3(),
            EMA50SupportV3(), MarubozuMomentumV3(), VWAPBreakoutV3(),
            ExtremeCandleRatioV3(), InsideBarBreakoutV3(), DecelerationCandlesV3(),
            VWAPDeviationV3(), VCPPatternV3(), EngulfingPatternV3(),
            RSIReversionV3(), BollingerTouchV3(), KeltnerReversionV3(),
            MACDCrossoverV3(), SupertrendV3(), StochasticReversionV3(),
            CCIReversionV3(), WilliamsRReversionV3(), ZScoreReversionV3(),
            ADXFilterV3(), BollingerSqueezeV3(), ParabolicSARV3(),
            MomentumBurstV3(), VolumeImbalanceV3(), OrderBlockV3(),
            FVGRetestV3(), DojiIndecisionV3(), MorningStarV3(),
            LongTailV3(), AbsorptionBlockV3(), LiquidityVoidV3(),
            FakeoutV3(), HigherTFTrendV3(), MTFImpulseV3(),
            AdaptiveRSIV3(), BollingerRejectionV3(), HurstRegimeV3(),
            KeltnerBreakoutV3(), MicroTrendV3(), SmartRangeV3(),
            VolatilityWakeupV3(), VSAReversalV3(), VWAPMomentumV3(),
            WickRejectionV3(), WyckoffSpringV3(), VolumeSpikeV3(),
            TweezerPatternV3(), ThreeBarV3(), SupportResistanceV3()
        ])
        
        logger.info(f"✅ SensorManager loaded {len(self.sensors)} sensors.")

    async def on_candle(self, event: CandleEvent):
        """Process new candle."""
        self._candle_index += 1
        candle_data = {
            "timestamp": event.timestamp,
            "open": event.open,
            "high": event.high,
            "low": event.low,
            "close": event.close,
            "volume": event.volume
        }
        
        if self._candle_index % 100 == 0:
            print(f"DEBUG: Processing candle {self._candle_index}")
            logger.debug(f"🕯️ Processing candle {self._candle_index} | Close: {event.close}")
        
        for sensor in self.sensors:
            try:
                # Check Cooldown
                if not self._can_fire(sensor.name):
                    continue
                
                # Calculate Signal
                signal = sensor.calculate(candle_data)
                
                if signal:
                    # Emit Signal Event
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
        event = SignalEvent(
            type=EventType.SIGNAL,
            timestamp=time.time(),
            symbol=self.engine.data_feed.adapter.symbol,
            side=signal_data["side"],
            strategy_name=sensor_name,
            score=signal_data.get("score", 1.0),
            metadata=signal_data.get("metadata", {})
        )
        logger.info(f"📡 Signal Detected: {sensor_name} -> {signal_data['side']}")
        await self.engine.dispatch(event)
