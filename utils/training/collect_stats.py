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

        # Iterate through candles
        total_candles = len(df)

        # Pre-calculate sensor params to avoid lookups
        sensor_params = {}
        for sensor in self.sensor_manager.sensors:
            # Use 15m params as default baseline for simulation if not specified
            params = get_sensor_params(sensor.name, "15m")
            sensor_params[sensor.name] = params

        logger.info("⏳ Processing candles...")

        start_time = time.time()

        for idx, row in df.iterrows():
            # 1. Update SensorManager with new candle
            # Create candle dict for context (CandleEvent not needed, using dict directly)
            candle_dict = {
                "timestamp": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }

            # We manually trigger what SensorManager.on_candle would do,
            # but we want to capture the return values directly.
            # Since SensorManager is async and designed for event loop,
            # we'll access the sensors directly for synchronous execution.

            # Prepare context
            candle_dict = {
                "timestamp": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }

            # Update aggregator inside sensor manager (for MTF)
            # BarAggregator expects a dict, not an event object
            context = self.sensor_manager.bar_aggregator.on_candle(candle_dict)
            # Ensure current timeframe is in context
            context["1m"] = candle_dict

            # 2. Run all sensors
            for sensor in self.sensor_manager.sensors:
                try:
                    # Calculate signal
                    result = sensor.calculate(context)

                    if not result:
                        continue

                    # Handle list of signals or single signal
                    signals = result if isinstance(result, list) else [result]

                    for signal in signals:
                        if not signal:
                            continue

                        signals_count += 1

                        # 3. Simulate Trade
                        trade_result = self._simulate_trade(
                            signal=signal,
                            entry_idx=idx,
                            df=df,
                            params=sensor_params.get(sensor.name, {"tp_pct": 0.015, "sl_pct": 0.01}),
                        )

                        if trade_result:
                            trades_count += 1
                            if trade_result["won"]:
                                wins += 1
                            else:
                                losses += 1

                            # 4. Update Tracker
                            self.tracker.update_sensor(
                                sensor_id=sensor.name, pnl=trade_result["pnl"], won=trade_result["won"]
                            )

                except Exception:
                    # Silently skip sensors that fail
                    pass

            if idx % 100 == 0 and idx > 0:
                progress = (idx / total_candles) * 100
                logger.info(f"   {progress:.1f}% | Signals: {signals_count} | Trades: {trades_count}")

            if idx % 1000 == 0 and idx > 0:
                self.tracker.save_state()

        # Save final stats
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

        # Print output for train_pipeline to parse
        print(f"Wins / Losses : {wins} / {losses}")

        return True

    def _simulate_trade(self, signal: Dict, entry_idx: int, df: pd.DataFrame, params: Dict) -> Dict:
        """
        Simulate a trade outcome based on TP/SL.
        Returns dict with 'won' (bool) and 'pnl' (float).
        """
        entry_price = df.iloc[entry_idx]["close"]
        side = signal["side"]

        tp_pct = params.get("tp_pct", 0.015)
        sl_pct = params.get("sl_pct", 0.01)

        # Calculate TP/SL prices
        if side == "LONG":
            tp_price = entry_price * (1 + tp_pct)
            sl_price = entry_price * (1 - sl_pct)
        else:
            tp_price = entry_price * (1 - tp_pct)
            sl_price = entry_price * (1 + sl_pct)

        # Look forward to find outcome
        # Limit lookahead to avoid infinite loops (e.g. 500 bars)
        max_bars = 500
        future_df = df.iloc[entry_idx + 1 : entry_idx + 1 + max_bars]

        if len(future_df) == 0:
            return None

        for _, row in future_df.iterrows():
            high = row["high"]
            low = row["low"]

            if side == "LONG":
                # Check SL first (conservative)
                if low <= sl_price:
                    pnl = -sl_pct - (self.fee_rate * 2)
                    return {"won": False, "pnl": pnl}
                if high >= tp_price:
                    pnl = tp_pct - (self.fee_rate * 2)
                    return {"won": True, "pnl": pnl}
            else:  # SHORT
                if high >= sl_price:
                    pnl = -sl_pct - (self.fee_rate * 2)
                    return {"won": False, "pnl": pnl}
                if low <= tp_price:
                    pnl = tp_pct - (self.fee_rate * 2)
                    return {"won": True, "pnl": pnl}

        # If timeout (no TP/SL hit in max_bars), close at end
        close_price = future_df.iloc[-1]["close"]
        if side == "LONG":
            raw_pnl = (close_price - entry_price) / entry_price
        else:
            raw_pnl = (entry_price - close_price) / entry_price

        pnl = raw_pnl - (self.fee_rate * 2)
        return {"won": pnl > 0, "pnl": pnl}


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
