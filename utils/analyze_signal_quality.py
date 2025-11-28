import json
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def load_data(filepath):
    df = pd.read_csv(filepath)
    # Ensure timestamp is datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def analyze_signals(data_path, logs_path, horizon_candles=10):
    """
    Analiza la calidad de la señal calculando MFE (Max Favorable Excursion)
    y MAE (Max Adverse Excursion) para las siguientes N velas.
    """
    print(f"📉 Loading market data from {data_path}...")
    df = load_data(data_path)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)

    # Debug: Print index info
    print(f"📊 Market Data Index: {df.index.dtype} | Start: {df.index[0]} | End: {df.index[-1]}")

    print(f"📋 Loading signals/trades from {logs_path}...")
    with open(logs_path, "r") as f:
        results = json.load(f)

    trades = results.get("closed_trades", [])
    if not trades:
        print("❌ No trades found in logs.")
        return

    print(f"🔍 Analyzing {len(trades)} trades over {horizon_candles} candles horizon...")

    stats = []

    for trade in trades:
        entry_time = pd.to_datetime(trade["entry_time"], unit="ms", utc=True)
        entry_price = trade["entry_price"]
        position_side = trade["position_side"]  # LONG or SHORT

        # Find the index of the entry candle
        try:
            # Use nearest matching to avoid exact timestamp issues
            idx = df.index.get_indexer([entry_time], method="nearest")[0]

            if idx == -1:
                print(f"⚠️ Timestamp {entry_time} out of bounds")
                continue

            future_candles = df.iloc[idx : idx + horizon_candles + 1]

            if len(future_candles) < 2:
                continue

            # Exclude the entry candle itself for excursion calculation if we want strict future
            # But usually we include it to see immediate reaction. Let's keep it.

            highs = future_candles["high"].values
            lows = future_candles["low"].values

            if position_side == "LONG":
                max_price = np.max(highs)
                min_price = np.min(lows)
                mfe = (max_price - entry_price) / entry_price
                mae = (entry_price - min_price) / entry_price
                final_pnl = (future_candles.iloc[-1]["close"] - entry_price) / entry_price
            else:  # SHORT
                max_price = np.max(highs)  # Adverse for short
                min_price = np.min(lows)  # Favorable for short
                mfe = (entry_price - min_price) / entry_price
                mae = (max_price - entry_price) / entry_price
                final_pnl = (entry_price - future_candles.iloc[-1]["close"]) / entry_price

            stats.append(
                {
                    "trade_id": trade["id"],
                    "side": position_side,
                    "mfe": mfe * 100,  # in %
                    "mae": mae * 100,  # in %
                    "final_pnl": final_pnl * 100,
                    "mfe_mae_ratio": mfe / (mae + 1e-9),
                }
            )

        except KeyError:
            print(f"⚠️ Timestamp {entry_time} not found in market data")
            continue

    if not stats:
        print("❌ No valid trades could be analyzed.")
        return

    df_stats = pd.DataFrame(stats)

    print("\n📊 Signal Quality Analysis (Horizon: 10 candles)")
    print("==============================================")
    print(f"Total Trades Analyzed: {len(df_stats)}")
    print(f"Avg MFE (Potential Profit): {df_stats['mfe'].mean():.4f}%")
    print(f"Avg MAE (Potential Drawdown): {df_stats['mae'].mean():.4f}%")
    print(f"Avg MFE/MAE Ratio: {df_stats['mfe_mae_ratio'].mean():.4f}")
    print(f"Win Rate (if TP=0.6% / SL=0.6%): {(df_stats['mfe'] >= 0.6).mean() * 100:.2f}% (Theoretical)")
    print(f"Win Rate (if TP=0.3% / SL=0.3%): {(df_stats['mfe'] >= 0.3).mean() * 100:.2f}% (Theoretical)")

    print("\n💡 Interpretation:")
    if df_stats["mfe"].mean() > df_stats["mae"].mean():
        print("✅ Signals have POSITIVE predictive edge (Price moves more in favor than against).")
    else:
        print("❌ Signals have NEGATIVE or NO predictive edge (Price moves more against than in favor).")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 utils/analyze_signal_quality.py <data_csv> <backtest_json_log>")
        sys.exit(1)

    data_file = sys.argv[1]
    log_file = sys.argv[2]

    analyze_signals(data_file, log_file)
