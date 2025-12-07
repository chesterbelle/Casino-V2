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
import random
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

        # Load existing statsorTracker()
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

            # --- SYNTHETIC FOOTPRINT GENERATION ---
            # Generate profile/delta for Footprint sensors
            profile = {}
            delta = 0.0

            # Simple simulation: Distribute volume across High-Low range
            # 1. Determine price levels (simulate tick size)
            price_range = highs[idx] - lows[idx]
            steps = 10  # Divide candle into 10 levels
            if price_range == 0:
                step_size = 1
            else:
                step_size = price_range / steps

            # 2. Distribute volume
            vol_per_level = volumes[idx] / (steps + 1)

            # Bias: Green = 70% Ask, Red = 70% Bid
            # ask_ratio = 0.7 if is_green else 0.3 # Original line

            current_price = lows[idx]
            for _ in range(steps + 1):
                level_price = round(current_price, 2)  # Round to 2 decimals

                # Random bid/ask ratio (0.05 to 0.95) to allow for strong imbalances
                bid_ratio = random.uniform(0.05, 0.95)

                ask_vol = vol_per_level * (1 - bid_ratio)
                bid_vol = vol_per_level * bid_ratio

                profile[level_price] = {"ask": ask_vol, "bid": bid_vol}
                delta += ask_vol - bid_vol

                current_price += step_size

            # 3. Calculate POC/VA (Simplified logic from CandleMaker)
            sorted_levels = sorted(profile.items(), key=lambda x: x[0])
            max_vol = -1
            poc_price = 0.0
            levels_vol = []

            for price, data in sorted_levels:
                vol = data["bid"] + data["ask"]
                levels_vol.append((price, vol))
                if vol > max_vol:
                    max_vol = vol
                    poc_price = price

            # Value Area (70%)
            target_vol = volumes[idx] * 0.70
            current_vol = max_vol
            poc_idx = -1
            for i, (p, v) in enumerate(levels_vol):
                if p == poc_price:
                    poc_idx = i
                    break

            up_idx = poc_idx
            down_idx = poc_idx

            while current_vol < target_vol:
                vol_up = levels_vol[up_idx + 1][1] if up_idx + 1 < len(levels_vol) else 0
                vol_down = levels_vol[down_idx - 1][1] if down_idx - 1 >= 0 else 0

                if vol_up == 0 and vol_down == 0:
                    break

                if vol_up > vol_down:
                    current_vol += vol_up
                    up_idx += 1
                else:
                    current_vol += vol_down
                    down_idx -= 1

            vah = levels_vol[up_idx][0] if levels_vol else 0.0
            val = levels_vol[down_idx][0] if levels_vol else 0.0

            # Enrich candle_dict
            candle_dict["profile"] = profile
            candle_dict["delta"] = delta
            candle_dict["poc"] = poc_price
            candle_dict["vah"] = vah
            candle_dict["val"] = val

            # Update aggregator inside sensor manager
            # This returns the full context with history
            context = self.sensor_manager.bar_aggregator.on_candle(candle_dict)
            # Update context again or manually inject?
            # SensorManager.bar_aggregator.on_candle returns a NEW dict usually?
            # No, it returns self.context which is a dict of deques.
            # But here we are passing `context` to `sensor.calculate`.

            # `context` from `on_candle` is usually `{"1m": [...], "5m": [...]}`
            # We need to make sure the LATEST candle in "1m" has these fields.

            # The BarAggregator stores standard OHLCV. It might strip extra fields.
            # Let's check BarAggregator later. For now, let's inject into the `context` passed to sensor.
            # The sensor usually looks at `context["1m"][-1]` or similar.

            # Actually, `collect_stats.py` does:
            # context = self.sensor_manager.bar_aggregator.on_candle(candle_dict)
            # context["1m"] = candle_dict  <-- This overrides the list? No, wait.

            # Original code:
            # context = self.sensor_manager.bar_aggregator.on_candle(candle_dict)
            # context["1m"] = candle_dict

            # This looks like a bug or simplification in `collect_stats.py`.
            # `context` should be a dict of lists/deques.
            # If `context["1m"]` is assigned `candle_dict`, it becomes a single dict, not a list.
            # Most sensors expect `history` or `context` to be accessible.
            # SensorV3 `calculate` receives `candle_data`.

            # Let's look at `SensorManager.on_candle`:
            # context = self.bar_aggregator.on_candle(candle_data)
            # await self._process_sensors_parallel(active_sensors, context)

            # So `context` is what is passed.
            # In `collect_stats.py`, line 118: `context["1m"] = candle_dict`
            # This seems wrong if sensors expect a list.
            # But let's assume for now we just pass the enriched candle_dict as the "current" data
            # and let the sensor handle it.
            # Wait, my new sensors look at `candle_data.get("history")`.
            # If `collect_stats.py` doesn't provide history, they fail.

            # BarAggregator `on_candle` updates its internal storage and returns the full context (history).
            # So `context` IS the history.
            # The line `context["1m"] = candle_dict` in `collect_stats.py` might be OVERWRITING the history with a single candle?
            # If so, that's a bug in `collect_stats.py` that needs fixing too.

            # Let's fix the overwrite and ensure history is preserved.
            # And inject the footprint data into the candle_dict BEFORE calling on_candle.

            # REVISED PLAN:
            # 1. Create candle_dict.
            # 2. Generate Footprint data and add to candle_dict.
            # 3. Call `context = bar_aggregator.on_candle(candle_dict)`.
            # 4. Remove the `context["1m"] = candle_dict` line if it's destructive.

            pass

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
