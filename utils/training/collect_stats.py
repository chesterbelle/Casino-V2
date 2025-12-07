#!/usr/bin/env python3
"""
Sensor Stats Collector for Casino-V3.
=====================================

Runs all sensors on historical data and simulates trades for EVERY signal generated,
ignoring the SignalAggregator's filtering. This ensures that sensor_stats.json
is populated with performance data for all sensors, enabling data-driven selection.

Usage:
    python utils/training/collect_stats.py --data data/raw/LTCUSDT_1m__30d.csv --symbol LTC/USDT:USDT
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.sensors import get_sensor_params
from core.sensor_manager import SensorManager
from decision.sensor_tracker import SensorTracker

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("StatsCollector")


class MockEngine:
    """Mock engine to satisfy SensorManager dependencies."""

    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_type, handler):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(handler)

    async def dispatch(self, event):
        pass  # We don't need to dispatch events in this script


class StatsCollector:
    def __init__(self, data_path: str, symbol: str):
        self.data_path = Path(data_path)
        self.symbol = symbol
        self.engine = MockEngine()
        self.sensor_manager = SensorManager(self.engine)
        self.tracker = SensorTracker()

        # Fee rate for simulation (0.07% taker)
        self.fee_rate = 0.0007

    def run(self):
        """Run the collection process."""
        logger.info(f"🚀 Starting Stats Collection for {self.symbol}")
        logger.info(f"📂 Data: {self.data_path}")

        # Load data
        try:
            df = pd.read_csv(self.data_path)
            logger.info(f"✅ Loaded {len(df)} candles")
        except Exception as e:
            logger.error(f"❌ Failed to load data: {e}")
            return False

        # Prepare for simulation
        signals_count = 0
        trades_count = 0
        wins = 0
        losses = 0

        # Pre-calculate sensor params
        sensor_params = {}
        for sensor in self.sensor_manager.sensors:
            params = get_sensor_params(sensor.name, "15m")
            sensor_params[sensor.name] = params

        # Convert to numpy for fast access
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        volumes = df["volume"].values
        timestamps = df["timestamp"].values

        total_candles = len(df)

        logger.info("⏳ Processing candles...")
        start_time = time.time()

        # We still need to iterate candles for sensor calculation (stateful)
        # But we can optimize the trade simulation part

        for idx in range(total_candles):
            # 1. Update SensorManager with new candle
            candle_dict = {
                "timestamp": timestamps[idx],
                "open": opens[idx],
                "high": highs[idx],
                "low": lows[idx],
                "close": closes[idx],
                "volume": volumes[idx],
            }

            # Update aggregator inside sensor manager
            context = self.sensor_manager.bar_aggregator.on_candle(candle_dict)
            context["1m"] = candle_dict

            # 2. Run all sensors
            for sensor in self.sensor_manager.sensors:
                try:
                    result = sensor.calculate(context)
                    if not result:
                        continue

                    signals = result if isinstance(result, list) else [result]

                    for signal in signals:
                        if not signal:
                            continue

                        signals_count += 1

                        # 3. Simulate Trade (Vectorized)
                        trade_result = self._simulate_trade_vectorized(
                            signal=signal,
                            entry_idx=idx,
                            highs=highs,
                            lows=lows,
                            closes=closes,
                            params=sensor_params.get(sensor.name, {"tp_pct": 0.015, "sl_pct": 0.01}),
                        )

                        if trade_result:
                            trades_count += 1
                            if trade_result["won"]:
                                wins += 1
                            else:
                                losses += 1

                            self.tracker.update_sensor(
                                sensor_id=sensor.name, pnl=trade_result["pnl"], won=trade_result["won"]
                            )

                except Exception:
                    pass

            if idx % 1000 == 0 and idx > 0:
                progress = (idx / total_candles) * 100
                logger.info(f"   {progress:.1f}% | Signals: {signals_count} | Trades: {trades_count}")
                self.tracker.save_state()

        self.tracker.save_state()

        duration = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ Collection Completed in {duration:.2f}s")
        logger.info(f"📊 Total Signals: {signals_count}")
        logger.info(f"📊 Simulated Trades: {trades_count}")
        logger.info(f"   Wins: {wins} | Losses: {losses}")
        if trades_count > 0:
            logger.info(f"   Win Rate: {(wins/trades_count)*100:.1f}%")
        logger.info("=" * 60)
        print(f"Wins / Losses : {wins} / {losses}")

        return True

    def _simulate_trade_vectorized(
        self, signal: Dict, entry_idx: int, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, params: Dict
    ) -> Dict:
        """
        Vectorized trade simulation using numpy arrays.
        """
        entry_price = closes[entry_idx]
        side = signal["side"]
        tp_pct = params.get("tp_pct", 0.015)
        sl_pct = params.get("sl_pct", 0.01)

        max_bars = 500
        end_idx = min(entry_idx + 1 + max_bars, len(highs))

        if entry_idx + 1 >= end_idx:
            return None

        # Slice future arrays
        future_highs = highs[entry_idx + 1 : end_idx]
        future_lows = lows[entry_idx + 1 : end_idx]

        if side == "LONG":
            tp_price = entry_price * (1 + tp_pct)
            sl_price = entry_price * (1 - sl_pct)

            # Find hits
            sl_hit_mask = future_lows <= sl_price
            tp_hit_mask = future_highs >= tp_price
        else:
            tp_price = entry_price * (1 - tp_pct)
            sl_price = entry_price * (1 + sl_pct)

            sl_hit_mask = future_highs >= sl_price
            tp_hit_mask = future_lows <= tp_price

        # Find first indices
        sl_indices = np.where(sl_hit_mask)[0]
        tp_indices = np.where(tp_hit_mask)[0]

        first_sl = sl_indices[0] if len(sl_indices) > 0 else 999999
        first_tp = tp_indices[0] if len(tp_indices) > 0 else 999999

        if first_sl == 999999 and first_tp == 999999:
            # Timeout - close at end
            close_price = closes[end_idx - 1]
            if side == "LONG":
                raw_pnl = (close_price - entry_price) / entry_price
            else:
                raw_pnl = (entry_price - close_price) / entry_price
            pnl = raw_pnl - (self.fee_rate * 2)
            return {"won": pnl > 0, "pnl": pnl}

        if first_sl < first_tp:
            return {"won": False, "pnl": -sl_pct - (self.fee_rate * 2)}
        else:
            return {"won": True, "pnl": tp_pct - (self.fee_rate * 2)}


def main():
    parser = argparse.ArgumentParser(description="Casino V3 Stats Collector")
    parser.add_argument("--data", required=True, help="Path to CSV data file")
    parser.add_argument("--symbol", required=True, help="Symbol (e.g. LTC/USDT:USDT)")

    args = parser.parse_args()

    collector = StatsCollector(args.data, args.symbol)
    try:
        success = collector.run()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")
        collector.tracker.save_state()
        success = False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
