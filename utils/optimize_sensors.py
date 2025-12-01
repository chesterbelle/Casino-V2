#!/usr/bin/env python3
"""
Sensor Optimization Tool

Analyzes historical MFE/MAE for each sensor to determine the optimal
TP/SL configuration that maximizes expectancy.

Usage:
    python utils/optimize_sensors.py --files data/raw/LTCUSDT_1m__90d.csv
"""

import argparse
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import trading

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SensorOptimizer")


class SensorOptimizer:
    """Optimizes TP/SL for sensors based on MFE/MAE analysis."""

    def __init__(self, max_bars: int = 120):
        self.max_bars = max_bars
        self.sensors = self._load_sensors()

        # Store MFE/MAE data for each sensor
        # {sensor_name: [{'mfe': float, 'mae': float, 'side': str}, ...]}
        self.sensor_data = defaultdict(list)

    def _load_sensors(self) -> List:
        """Load all V3 sensors."""
        # Import all sensors
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

        # Instantiate all sensors
        sensors = [
            EMACrossoverV3(),
            PinBarReversalV3(),
            RailsPatternV3(),
            EMA50SupportV3(),
            MarubozuMomentumV3(),
            VWAPBreakoutV3(),
            ExtremeCandleRatioV3(),
            InsideBarBreakoutV3(),
            DecelerationCandlesV3(),
            VWAPDeviationV3(),
            VCPPatternV3(),
            EngulfingPatternV3(),
            RSIReversionV3(),
            BollingerTouchV3(),
            KeltnerReversionV3(),
            MACDCrossoverV3(),
            SupertrendV3(),
            StochasticReversionV3(),
            CCIReversionV3(),
            WilliamsRReversionV3(),
            ZScoreReversionV3(),
            ADXFilterV3(),
            BollingerSqueezeV3(),
            ParabolicSARV3(),
            MomentumBurstV3(),
            VolumeImbalanceV3(),
            OrderBlockV3(),
            FVGRetestV3(),
            DojiIndecisionV3(),
            MorningStarV3(),
            LongTailV3(),
            AbsorptionBlockV3(),
            LiquidityVoidV3(),
            FakeoutV3(),
            HigherTFTrendV3(),
            MTFImpulseV3(),
            AdaptiveRSIV3(),
            BollingerRejectionV3(),
            HurstRegimeV3(),
            KeltnerBreakoutV3(),
            MicroTrendV3(),
            SmartRangeV3(),
            VolatilityWakeupV3(),
            VSAReversalV3(),
            VWAPMomentumV3(),
            WickRejectionV3(),
            WyckoffSpringV3(),
            VolumeSpikeV3(),
            TweezerPatternV3(),
            ThreeBarV3(),
            SupportResistanceV3(),
        ]
        return sensors

    def analyze_signal(self, signal: Dict, entry_idx: int, candles: pd.DataFrame):
        """Calculate MFE and MAE for a signal."""
        if entry_idx >= len(candles) - 1:
            return

        entry_price = candles.iloc[entry_idx]["close"]
        side = signal["side"]

        # Get future window
        max_idx = min(entry_idx + self.max_bars, len(candles))
        future_candles = candles.iloc[entry_idx + 1 : max_idx]

        if len(future_candles) == 0:
            return

        highs = future_candles["high"].values
        lows = future_candles["low"].values

        if side == "LONG":
            max_price = np.max(highs)
            min_price = np.min(lows)
            mfe = (max_price - entry_price) / entry_price
            mae = (entry_price - min_price) / entry_price
            final_pnl = (future_candles.iloc[-1]["close"] - entry_price) / entry_price
        else:  # SHORT
            max_price = np.max(highs)
            min_price = np.min(lows)
            mfe = (entry_price - min_price) / entry_price
            mae = (max_price - entry_price) / entry_price
            final_pnl = (entry_price - future_candles.iloc[-1]["close"]) / entry_price

        self.sensor_data[signal["sensor_id"]].append({"mfe": mfe, "mae": mae, "final_pnl": final_pnl, "side": side})

    def process_file(self, csv_file: Path):
        """Process a single CSV file."""
        logger.info(f"📂 Processing: {csv_file.name}")
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            logger.error(f"❌ Failed to load {csv_file}: {e}")
            return

        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            logger.error(f"❌ Missing required columns in {csv_file}")
            return

        logger.info(f"   Loaded {len(df)} candles")

        signals_count = 0

        for idx, row in df.iterrows():
            candle_dict = {
                "timestamp": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }

            for sensor in self.sensors:
                try:
                    signal = sensor.calculate(candle_dict)
                    if signal:
                        # Add sensor_id if missing (some sensors might not add it in calculate)
                        if "sensor_id" not in signal:
                            signal["sensor_id"] = sensor.name

                        self.analyze_signal(signal, idx, df)
                        signals_count += 1
                except Exception:
                    pass

            if idx % 5000 == 0 and idx > 0:
                logger.info(f"   Processed {idx} candles... ({signals_count} signals)")

    def optimize_sensors(self, timeframe: str = "1m"):
        """Find optimal TP/SL for each sensor."""
        logger.info("\n🔍 OPTIMIZATION RESULTS")
        logger.info("=" * 80)

        # Grid search parameters (Timeframe-specific ranges)
        if timeframe == "1m":
            tp_range = np.arange(0.002, 0.051, 0.001)  # 0.2% to 5.0%
            sl_range = np.arange(0.002, 0.031, 0.001)  # 0.2% to 3.0%
        elif timeframe == "5m":
            tp_range = np.arange(0.005, 0.081, 0.002)  # 0.5% to 8.0%
            sl_range = np.arange(0.005, 0.051, 0.002)  # 0.5% to 5.0%
        elif timeframe == "15m":
            tp_range = np.arange(0.010, 0.121, 0.003)  # 1.0% to 12.0%
            sl_range = np.arange(0.010, 0.081, 0.003)  # 1.0% to 8.0%
        elif timeframe == "1h":
            tp_range = np.arange(0.020, 0.201, 0.005)  # 2.0% to 20.0%
            sl_range = np.arange(0.020, 0.151, 0.005)  # 2.0% to 15.0%
        else:
            # Default to 1m
            tp_range = np.arange(0.002, 0.051, 0.001)
            sl_range = np.arange(0.002, 0.031, 0.001)

        fee_rate = 0.0007  # 0.07% per trade (Taker+Taker)

        results = []

        for sensor_name, data in self.sensor_data.items():
            if len(data) < 1:  # Analyze everything, even with 1 trade
                continue

            df = pd.DataFrame(data)

            best_expectancy = -float("inf")
            best_config = None

            # Vectorized optimization
            mfe_arr = df["mfe"].values
            mae_arr = df["mae"].values
            final_pnl_arr = df["final_pnl"].values

            for tp in tp_range:
                for sl in sl_range:
                    # Determine outcome for each trade
                    is_loss = mae_arr >= sl
                    is_win = (mfe_arr >= tp) & (~is_loss)
                    is_timeout = (~is_win) & (~is_loss)

                    wins = np.sum(is_win)
                    losses = np.sum(is_loss)
                    timeouts = np.sum(is_timeout)

                    win_rate = wins / len(mfe_arr)

                    # Calculate total PnL
                    total_pnl = (
                        wins * (tp - fee_rate)
                        + losses * (-sl - fee_rate)
                        + np.sum(final_pnl_arr[is_timeout] - fee_rate)
                    )

                    avg_pnl = total_pnl / len(mfe_arr)

                    if avg_pnl > best_expectancy:
                        best_expectancy = avg_pnl
                        best_config = {"tp": tp, "sl": sl, "wr": win_rate, "trades": len(mfe_arr), "timeouts": timeouts}

            if best_config:
                results.append(
                    {
                        "sensor": sensor_name,
                        "tp": best_config["tp"],
                        "sl": best_config["sl"],
                        "wr": best_config["wr"] * 100,
                        "expectancy": best_expectancy * 100,
                        "trades": best_config["trades"],
                        "timeouts_pct": (best_config["timeouts"] / best_config["trades"]) * 100,
                    }
                )

        # Sort by expectancy
        results.sort(key=lambda x: x["expectancy"], reverse=True)

        print(f"{'Sensor':<25} {'TP%':<8} {'SL%':<8} {'WR%':<8} {'Exp%':<8} {'Trades':<8} {'Timeouts%':<10}")
        print("-" * 85)

        config_output = "SENSOR_PARAMS = {\n"

        for r in results[:30]:  # Show top 30
            print(
                f"{r['sensor']:<25} {r['tp']*100:>6.2f}   {r['sl']*100:>6.2f}   {r['wr']:>6.1f}   {r['expectancy']:>6.3f}   {r['trades']:>6}   {r['timeouts_pct']:>9.1f}"
            )

            if r["expectancy"] > 0:
                config_output += f'    "{r["sensor"]}": {{\n'
                config_output += f'        "{timeframe}": {{"tp_pct": {r["tp"]:.4f}, "sl_pct": {r["sl"]:.4f}}},\n'
                config_output += f"    }},\n"

        config_output += "}"
        print("\n" + "=" * 80)
        print("📋 COPY TO config/sensors.py:")
        print("=" * 80)
        print(config_output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=str, required=True, help="Comma-separated list of CSV files")
    parser.add_argument("--max-bars", type=int, default=120, help="Max bars for MFE/MAE analysis")
    parser.add_argument(
        "--timeframe",
        type=str,
        default=None,
        help="Timeframe (1m, 5m, 15m, 1h). Auto-detected from filename if not specified.",
    )
    args = parser.parse_args()

    # Auto-detect timeframe from first filename if not specified
    if args.timeframe is None:
        import re

        first_file = args.files.split(",")[0].strip()
        match = re.search(r"_(\d+[mh])_", first_file)
        timeframe = match.group(1) if match else "1m"
        logger.info(f"📊 Auto-detected timeframe: {timeframe}")
    else:
        timeframe = args.timeframe
        logger.info(f"📊 Using specified timeframe: {timeframe}")

    optimizer = SensorOptimizer(max_bars=args.max_bars)

    files = [Path(f.strip()) for f in args.files.split(",")]
    for f in files:
        if f.exists():
            optimizer.process_file(f)
        else:
            logger.error(f"File not found: {f}")

    optimizer.optimize_sensors(timeframe=timeframe)


if __name__ == "__main__":
    main()
