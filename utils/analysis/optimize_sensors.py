#!/usr/bin/env python3
"""
Sensor Optimization Tool V2

Analyzes historical MFE/MAE for each sensor to determine the optimal
TP/SL configuration that maximizes expectancy.

Improvements over V1:
- Expanded grid search ranges (TP up to 10%, SL up to 6%)
- Minimum trade threshold (30 trades for statistical significance)
- TP/SL ratio constraints (ratio >= 0.5)
- Profit Factor metric
- JSON output for programmatic use
- Better console output with rankings

Usage:
    python utils/analysis/optimize_sensors.py --files data/raw/LTCUSDT_1m__90d.csv
    python utils/analysis/optimize_sensors.py --files data/raw/*.csv --min-trades 50
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SensorOptimizer")


# =====================================================
# CONFIGURATION
# =====================================================

# Grid search ranges by timeframe (expanded for better optimization)
GRID_RANGES = {
    "1m": {
        "tp": np.arange(0.003, 0.101, 0.002),  # 0.3% to 10.0%
        "sl": np.arange(0.005, 0.061, 0.002),  # 0.5% to 6.0%
    },
    "5m": {
        "tp": np.arange(0.005, 0.121, 0.003),  # 0.5% to 12.0%
        "sl": np.arange(0.008, 0.081, 0.003),  # 0.8% to 8.0%
    },
    "15m": {
        "tp": np.arange(0.010, 0.151, 0.005),  # 1.0% to 15.0%
        "sl": np.arange(0.010, 0.101, 0.005),  # 1.0% to 10.0%
    },
    "1h": {
        "tp": np.arange(0.020, 0.251, 0.010),  # 2.0% to 25.0%
        "sl": np.arange(0.020, 0.151, 0.010),  # 2.0% to 15.0%
    },
}

# Fee rate (taker + taker for round trip)
FEE_RATE = 0.0007  # 0.07% per trade

# Minimum TP/SL ratio (avoid configs where SL >> TP)
MIN_TP_SL_RATIO = 0.5


class SensorOptimizer:
    """Optimizes TP/SL for sensors based on MFE/MAE analysis."""

    def __init__(self, max_bars: int = 120, min_trades: int = 30):
        """
        Args:
            max_bars: Maximum bars to analyze for MFE/MAE
            min_trades: Minimum trades required for optimization (statistical significance)
        """
        self.max_bars = max_bars
        self.min_trades = min_trades
        self.sensors = self._load_sensors()

        # Store MFE/MAE data for each sensor
        # {sensor_name: [{'mfe': float, 'mae': float, 'side': str}, ...]}
        self.sensor_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def _load_sensors(self) -> List:
        """Load all V3 sensors."""
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
        logger.info(f"✅ Loaded {len(sensors)} sensors")
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

        self.sensor_data[signal["sensor_id"]].append(
            {
                "mfe": mfe,
                "mae": mae,
                "final_pnl": final_pnl,
                "side": side,
                "entry_price": entry_price,
            }
        )

    def process_file(self, csv_file: Path, timeframe: str = "1m"):
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

            # Wrap candle in context format that sensors expect
            # Sensors call context.get("1m") to get the candle
            context = {timeframe: candle_dict}

            for sensor in self.sensors:
                try:
                    # Set the optimal timeframe to match the data we're passing
                    sensor._optimal_tf = timeframe

                    signal = sensor.calculate(context)
                    if signal:
                        if "sensor_id" not in signal:
                            signal["sensor_id"] = sensor.name

                        self.analyze_signal(signal, idx, df)
                        signals_count += 1
                except Exception:
                    pass

            if idx % 10000 == 0 and idx > 0:
                logger.info(f"   Processed {idx} candles... ({signals_count} signals)")

        logger.info(f"   ✅ Completed: {signals_count} signals collected")

    def _optimize_single_sensor(
        self, sensor_name: str, data: List[Dict], tp_range: np.ndarray, sl_range: np.ndarray
    ) -> Dict[str, Any]:
        """Optimize TP/SL for a single sensor."""
        df = pd.DataFrame(data)

        mfe_arr = df["mfe"].values
        mae_arr = df["mae"].values
        final_pnl_arr = df["final_pnl"].values

        best_expectancy = -float("inf")
        best_config = None

        for tp in tp_range:
            for sl in sl_range:
                # Skip if TP/SL ratio is too low (risky config)
                if tp / sl < MIN_TP_SL_RATIO:
                    continue

                # Determine outcome for each trade
                is_loss = mae_arr >= sl
                is_win = (mfe_arr >= tp) & (~is_loss)
                is_timeout = (~is_win) & (~is_loss)

                wins = np.sum(is_win)
                losses = np.sum(is_loss)
                timeouts = np.sum(is_timeout)

                total_trades = len(mfe_arr)
                win_rate = wins / total_trades

                # Calculate PnL components
                gross_profit = wins * tp
                gross_loss = losses * sl
                timeout_pnl = np.sum(final_pnl_arr[is_timeout])

                # Total PnL with fees
                total_pnl = gross_profit - gross_loss + timeout_pnl - (total_trades * FEE_RATE)
                avg_pnl = total_pnl / total_trades

                # Profit factor (avoid division by zero)
                profit_factor = gross_profit / max(gross_loss, 0.0001)

                if avg_pnl > best_expectancy:
                    best_expectancy = avg_pnl
                    best_config = {
                        "tp": tp,
                        "sl": sl,
                        "win_rate": win_rate,
                        "wins": wins,
                        "losses": losses,
                        "timeouts": timeouts,
                        "profit_factor": profit_factor,
                        "gross_profit": gross_profit,
                        "gross_loss": gross_loss,
                    }

        return {
            "sensor": sensor_name,
            "trades": len(data),
            "best_config": best_config,
            "expectancy": best_expectancy,
        }

    def optimize_sensors(self, timeframe: str = "1m") -> List[Dict[str, Any]]:
        """Find optimal TP/SL for each sensor."""
        logger.info("\n" + "=" * 80)
        logger.info("🔍 SENSOR OPTIMIZATION RESULTS")
        logger.info("=" * 80)

        # Get grid ranges for this timeframe
        ranges = GRID_RANGES.get(timeframe, GRID_RANGES["1m"])
        tp_range = ranges["tp"]
        sl_range = ranges["sl"]

        logger.info(f"📊 Timeframe: {timeframe}")
        logger.info(f"📊 TP Range: {tp_range[0]*100:.1f}% - {tp_range[-1]*100:.1f}%")
        logger.info(f"📊 SL Range: {sl_range[0]*100:.1f}% - {sl_range[-1]*100:.1f}%")
        logger.info(f"📊 Min Trades: {self.min_trades}")
        logger.info(f"📊 Min TP/SL Ratio: {MIN_TP_SL_RATIO}")

        results = []

        for sensor_name, data in self.sensor_data.items():
            if len(data) < self.min_trades:
                logger.debug(f"⏭️ Skipping {sensor_name}: only {len(data)} trades (min: {self.min_trades})")
                continue

            result = self._optimize_single_sensor(sensor_name, data, tp_range, sl_range)
            if result["best_config"]:
                results.append(result)

        # Sort by expectancy (descending)
        results.sort(key=lambda x: x["expectancy"], reverse=True)

        # Print results table
        print("\n" + "=" * 100)
        print(
            f"{'Rank':<5} {'Sensor':<25} {'TP%':<7} {'SL%':<7} {'Ratio':<6} {'WR%':<7} {'PF':<6} {'Exp%':<8} {'Trades':<8}"
        )
        print("=" * 100)

        for i, r in enumerate(results, 1):
            cfg = r["best_config"]
            ratio = cfg["tp"] / cfg["sl"]
            print(
                f"{i:<5} {r['sensor']:<25} "
                f"{cfg['tp']*100:>5.2f}   {cfg['sl']*100:>5.2f}   "
                f"{ratio:>4.2f}   {cfg['win_rate']*100:>5.1f}   "
                f"{cfg['profit_factor']:>4.2f}   {r['expectancy']*100:>6.3f}   "
                f"{r['trades']:>6}"
            )

        print("=" * 100)

        # Generate output config
        self._generate_config_output(results, timeframe)

        return results

    def _generate_config_output(self, results: List[Dict], timeframe: str):
        """Generate Python config and JSON output."""
        # Python dict format
        print("\n" + "=" * 80)
        print("📋 COPY TO config/sensors.py SENSOR_PARAMS:")
        print("=" * 80)

        config_output = ""
        profitable_count = 0

        for r in results:
            if r["expectancy"] > 0:
                profitable_count += 1
                cfg = r["best_config"]
                config_output += f'    "{r["sensor"]}": {{\n'
                config_output += f'        "{timeframe}": {{"tp_pct": {cfg["tp"]:.4f}, "sl_pct": {cfg["sl"]:.4f}}},  # Exp: {r["expectancy"]*100:.3f}%\n'
                config_output += f"    }},\n"

        print(config_output)
        print(f"\n✅ {profitable_count} sensors with positive expectancy")

        # Save to JSON
        json_output = {
            "generated_at": datetime.now().isoformat(),
            "timeframe": timeframe,
            "min_trades": self.min_trades,
            "fee_rate": FEE_RATE,
            "sensors": {},
        }

        for r in results:
            if r["expectancy"] > 0:
                cfg = r["best_config"]
                json_output["sensors"][r["sensor"]] = {
                    "tp_pct": round(cfg["tp"], 4),
                    "sl_pct": round(cfg["sl"], 4),
                    "win_rate": round(cfg["win_rate"], 4),
                    "expectancy": round(r["expectancy"], 6),
                    "profit_factor": round(cfg["profit_factor"], 4),
                    "trades": r["trades"],
                }

        output_file = Path("config/optimized_params.json")
        with open(output_file, "w") as f:
            json.dump(json_output, f, indent=2)

        print(f"💾 Saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Optimize TP/SL for all sensors")
    parser.add_argument(
        "--files",
        type=str,
        required=True,
        help="Comma-separated list of CSV files or glob pattern",
    )
    parser.add_argument(
        "--max-bars",
        type=int,
        default=120,
        help="Max bars for MFE/MAE analysis (default: 120)",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=30,
        help="Minimum trades for optimization (default: 30)",
    )
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

    optimizer = SensorOptimizer(max_bars=args.max_bars, min_trades=args.min_trades)

    # Handle glob patterns
    import glob

    files = []
    for pattern in args.files.split(","):
        pattern = pattern.strip()
        if "*" in pattern:
            files.extend([Path(f) for f in glob.glob(pattern)])
        else:
            files.append(Path(pattern))

    if not files:
        logger.error("❌ No files found")
        sys.exit(1)

    logger.info(f"📂 Processing {len(files)} file(s)")

    for f in files:
        if f.exists():
            optimizer.process_file(f, timeframe=timeframe)
        else:
            logger.error(f"File not found: {f}")

    # Run optimization
    optimizer.optimize_sensors(timeframe=timeframe)


if __name__ == "__main__":
    main()
