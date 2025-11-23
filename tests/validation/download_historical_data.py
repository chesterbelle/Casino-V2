#!/usr/bin/env python3
"""
Download Historical Data - Casino V2

Descarga datos históricos usando CCXTAdapter para mantener consistencia
arquitectural con el resto del sistema.

Uso:
    python tests/validation/download_historical_data.py \
        --start "2024-11-07 19:00:00" \
        --end "2024-11-07 19:10:00" \
        --symbol LTC/USDT:USDT \
        --interval 1m \
        --output data/validation/historical_10candles.csv \
        --exchange binance

Validaciones:
    - Número de velas correcto
    - Timestamps continuos
    - Sin gaps en los datos
    - Formato compatible con BacktestDataSource
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.binance.binance_connector import BinanceConnector
from exchanges.connectors.bybit.bybit_connector import BybitConnector

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")

logger = logging.getLogger("DownloadHistoricalData")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Download historical data using CCXTAdapter")

    parser.add_argument("--start", type=str, required=True, help='Start datetime (format: "YYYY-MM-DD HH:MM:SS")')

    parser.add_argument("--end", type=str, required=True, help='End datetime (format: "YYYY-MM-DD HH:MM:SS")')

    parser.add_argument("--symbol", type=str, default="LTC/USDT:USDT", help="Trading pair (default: LTC/USDT:USDT)")

    parser.add_argument("--interval", type=str, default="1m", help="Candle interval (default: 1m)")

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV file path (default: data/validation/historical_TIMESTAMP.csv)",
    )

    parser.add_argument(
        "--exchange",
        type=str,
        default="binance",
        choices=["binance", "bybit"],
        help="Exchange to download from (default: binance)",
    )

    return parser.parse_args()


def parse_datetime(dt_str: str) -> datetime:
    """
    Parse datetime string.

    Args:
        dt_str: Datetime string in format "YYYY-MM-DD HH:MM:SS"

    Returns:
        datetime object
    """
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            # Try ISO format
            return datetime.fromisoformat(dt_str)
        except ValueError:
            raise ValueError(f"Invalid datetime format: {dt_str}. " f"Use 'YYYY-MM-DD HH:MM:SS' or ISO format")


def get_interval_ms(interval: str) -> int:
    """
    Get interval in milliseconds.

    Args:
        interval: Interval string (e.g., '1m', '5m', '1h')

    Returns:
        Interval in milliseconds
    """
    unit = interval[-1]
    value = int(interval[:-1])

    if unit == "m":
        return value * 60 * 1000
    elif unit == "h":
        return value * 60 * 60 * 1000
    elif unit == "d":
        return value * 24 * 60 * 60 * 1000
    else:
        raise ValueError(f"Invalid interval unit: {unit}")


async def download_data(
    adapter: CCXTAdapter, symbol: str, interval: str, start_dt: datetime, end_dt: datetime
) -> pd.DataFrame:
    """
    Download OHLCV data using CCXTAdapter.

    Args:
        adapter: CCXTAdapter instance
        symbol: Trading pair (e.g., 'LTC/USDT:USDT')
        interval: Candle interval (e.g., '1m')
        start_dt: Start datetime
        end_dt: End datetime

    Returns:
        DataFrame with OHLCV data
    """
    logger.info(f"📡 Downloading data using CCXTAdapter...")

    # Convert datetimes to timestamps
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    logger.info(f"📊 Downloading data...")
    logger.info(f"   Symbol: {symbol}")
    logger.info(f"   Interval: {interval}")
    logger.info(f"   Start: {start_dt}")
    logger.info(f"   End: {end_dt}")

    # Download data
    all_candles = []
    current_ts = start_ts
    interval_ms = get_interval_ms(interval)

    while current_ts < end_ts:
        # Fetch candles using adapter
        logger.info(f"   Fetching with limit=1000 from {current_ts}")
        candles = await adapter.connector.fetch_ohlcv(
            symbol=symbol, timeframe=interval, since=current_ts, limit=1000  # Max per request
        )

        if not candles:
            break

        # Filter candles within range
        for candle in candles:
            if isinstance(candle, dict):
                candle_ts = candle.get("timestamp")
            else:
                candle_ts = candle[0]
            if candle_ts and start_ts <= candle_ts < end_ts:
                # Normalize candle format
                if isinstance(candle, dict):
                    all_candles.append(candle)
                else:
                    # Convert list format to dict
                    all_candles.append(
                        {
                            "timestamp": candle[0],
                            "open": candle[1],
                            "high": candle[2],
                            "low": candle[3],
                            "close": candle[4],
                            "volume": candle[5],
                        }
                    )

        # Move to next batch
        last_candle = candles[-1]
        if isinstance(last_candle, dict):
            last_ts = last_candle.get("timestamp")
        else:
            last_ts = last_candle[0]
        current_ts = last_ts + interval_ms

        logger.info(f"   Downloaded {len(all_candles)} candles so far...")

        # Avoid rate limits
        await asyncio.sleep(0.1)

    logger.info(f"✅ Downloaded {len(all_candles)} candles")

    # Convert to DataFrame
    df = pd.DataFrame(all_candles)

    # Ensure we have the required columns
    if "timestamp" not in df.columns:
        raise ValueError("Downloaded data missing 'timestamp' column")

    # Add metadata
    df["symbol"] = symbol.replace("/", "")  # LTC/USDT:USDT -> LTCUSDTUSDT
    df["timeframe"] = interval

    return df


def validate_data(df: pd.DataFrame, interval: str, expected_candles: int = None) -> bool:
    """
    Validate downloaded data.

    Args:
        df: DataFrame with OHLCV data
        interval: Candle interval
        expected_candles: Expected number of candles (optional)

    Returns:
        True if valid, False otherwise
    """
    logger.info(f"\n🔍 Validating data...")

    issues = []

    # Check if empty
    if df.empty:
        issues.append("❌ No data downloaded")
        return False

    # Check number of candles
    if expected_candles and len(df) != expected_candles:
        issues.append(f"⚠️  Expected {expected_candles} candles, got {len(df)}")

    # Check for gaps
    interval_ms = get_interval_ms(interval)
    timestamps = df["timestamp"].values

    gaps = []
    for i in range(1, len(timestamps)):
        diff = timestamps[i] - timestamps[i - 1]
        if diff != interval_ms:
            gaps.append((i, diff / interval_ms))

    if gaps:
        issues.append(f"⚠️  Found {len(gaps)} gaps in timestamps")
        for idx, ratio in gaps[:5]:  # Show first 5
            logger.warning(f"   Gap at index {idx}: {ratio:.1f}x interval")

    # Check for duplicates
    duplicates = df["timestamp"].duplicated().sum()
    if duplicates > 0:
        issues.append(f"❌ Found {duplicates} duplicate timestamps")

    # Check for missing values
    missing = df[["open", "high", "low", "close", "volume"]].isnull().sum().sum()
    if missing > 0:
        issues.append(f"❌ Found {missing} missing values")

    # Check OHLC consistency
    invalid_ohlc = (
        (df["high"] < df["low"])
        | (df["high"] < df["open"])
        | (df["high"] < df["close"])
        | (df["low"] > df["open"])
        | (df["low"] > df["close"])
    ).sum()

    if invalid_ohlc > 0:
        issues.append(f"❌ Found {invalid_ohlc} invalid OHLC candles")

    # Print results
    if issues:
        for issue in issues:
            logger.warning(issue)
        logger.warning("⚠️  Data has issues but will be saved anyway")
        return False
    else:
        logger.info("✅ Data validation passed")
        logger.info(f"   Candles: {len(df)}")
        logger.info(f"   Start: {datetime.fromtimestamp(df['timestamp'].iloc[0]/1000)}")
        logger.info(f"   End: {datetime.fromtimestamp(df['timestamp'].iloc[-1]/1000)}")
        return True


def save_data(df: pd.DataFrame, output_path: str):
    """
    Save data to CSV file.

    Args:
        df: DataFrame with OHLCV data
        output_path: Output file path
    """
    # Create directory if needed
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    df.to_csv(output_file, index=False)

    logger.info(f"\n💾 Data saved to: {output_file}")
    logger.info(f"   Size: {output_file.stat().st_size / 1024:.2f} KB")


async def main():
    """Main function."""
    args = parse_args()

    try:
        # Parse datetimes
        start_dt = parse_datetime(args.start)
        end_dt = parse_datetime(args.end)

        # Calculate expected candles
        duration_seconds = (end_dt - start_dt).total_seconds()
        interval_seconds = get_interval_ms(args.interval) / 1000
        expected_candles = int(duration_seconds / interval_seconds)

        logger.info("=" * 80)
        logger.info("📥 DOWNLOAD HISTORICAL DATA (CCXTAdapter)")
        logger.info("=" * 80)
        logger.info(f"Exchange: {args.exchange.upper()}")
        logger.info(f"Symbol: {args.symbol}")
        logger.info(f"Interval: {args.interval}")
        logger.info(f"Period: {start_dt} → {end_dt}")
        logger.info(f"Expected candles: {expected_candles}")
        logger.info("=" * 80 + "\n")

        # Create connector based on exchange
        if args.exchange == "binance":
            connector = BinanceConnector(mode="demo")
        elif args.exchange == "bybit":
            connector = BybitConnector(testnet=True)
        else:
            raise ValueError(f"Unsupported exchange: {args.exchange}")

        # Create adapter
        adapter = CCXTAdapter(connector=connector, symbol=args.symbol, timeframe=args.interval)
        await adapter.connect()

        # Connection already established
        logger.info(f"✅ Connected to {args.exchange.upper()}\n")

        try:
            # Download data
            df = await download_data(adapter, args.symbol, args.interval, start_dt, end_dt)

            # Validate data
            validate_data(df, args.interval, expected_candles)

            # Generate output path if not provided
            if not args.output:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                args.output = f"data/validation/historical_{timestamp}.csv"

            # Save data
            save_data(df, args.output)

            logger.info("\n" + "=" * 80)
            logger.info("✅ DOWNLOAD COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)

            return 0

        finally:
            await adapter.disconnect()
            logger.info("🔌 Disconnected from exchange")

    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
