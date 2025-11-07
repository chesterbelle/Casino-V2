"""
Descarga de Datos Históricos en formato CSV.

Este script descarga datos OHLCV de Kraken y los guarda en formato CSV
compatible con BacktestDataSource.

Usage:
    python tests/validation/download_historical_data_csv.py \
        --start "2024-11-06T20:00:00Z" \
        --end "2024-11-06T21:00:00Z" \
        --output data/validation/BTC_USD_60candles.csv
"""

import argparse
import asyncio
import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from exchanges.connectors import KrakenConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def download_and_save_csv(
    symbol: str,
    timeframe: str,
    start_time: datetime,
    end_time: datetime,
    output_path: str,
):
    """
    Descarga datos y los guarda en CSV.

    Args:
        symbol: Trading pair (e.g., "BTC/USD:USD")
        timeframe: Timeframe (e.g., "1m")
        start_time: Start datetime
        end_time: End datetime
        output_path: Output CSV file path
    """
    logger.info("=" * 80)
    logger.info("📥 DESCARGA DE DATOS HISTÓRICOS")
    logger.info("=" * 80)

    # Conectar a Kraken
    connector = KrakenConnector(testnet=True)
    await connector.connect()
    logger.info("✅ Conectado a Kraken")

    try:
        # Calcular número de velas
        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        logger.info(f"\n📊 Configuración:")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Timeframe: {timeframe}")
        logger.info(f"  Start: {start_time.isoformat()}")
        logger.info(f"  End: {end_time.isoformat()}")
        logger.info(f"  Expected candles: {duration_minutes}")

        # Descargar datos
        since = int(start_time.timestamp() * 1000)
        ohlcv_data = await connector.fetch_ohlcv(
            symbol=symbol, timeframe=timeframe, limit=duration_minutes, since=since
        )

        logger.info(f"✅ Descargadas {len(ohlcv_data)} velas")

        # Crear directorio si no existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Guardar en CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header compatible con BacktestDataSource
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume", "symbol"])

            # Datos
            for candle in ohlcv_data:
                writer.writerow(
                    [
                        candle["timestamp"],
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                        candle["volume"],
                        "BTC/USD",  # Normalizado para BacktestDataSource
                    ]
                )

        logger.info(f"\n💾 Datos guardados en: {output_path}")
        logger.info(f"📊 Total de velas: {len(ohlcv_data)}")

        # Mostrar preview
        logger.info("\n📋 Preview (primeras 3 velas):")
        for i, candle in enumerate(ohlcv_data[:3]):
            dt = datetime.fromtimestamp(candle["timestamp"] / 1000)
            logger.info(
                f"  [{i+1}] {dt.isoformat()} | "
                f"O: ${candle['open']:,.2f} | "
                f"H: ${candle['high']:,.2f} | "
                f"L: ${candle['low']:,.2f} | "
                f"C: ${candle['close']:,.2f}"
            )

        logger.info("\n" + "=" * 80)
        logger.info("✅ DESCARGA COMPLETADA")
        logger.info("=" * 80)

    finally:
        await connector.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Descarga datos históricos en CSV")
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTC/USD:USD",
        help="Trading pair (default: BTC/USD:USD)",
    )
    parser.add_argument("--timeframe", type=str, default="1m", help="Timeframe (default: 1m)")
    parser.add_argument("--start", type=str, required=True, help="Start time (ISO format)")
    parser.add_argument("--end", type=str, required=True, help="End time (ISO format)")
    parser.add_argument(
        "--output",
        type=str,
        default="data/validation/historical_data.csv",
        help="Output CSV file path",
    )

    args = parser.parse_args()

    # Parse datetimes
    start_time = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(args.end.replace("Z", "+00:00"))

    # Run
    asyncio.run(download_and_save_csv(args.symbol, args.timeframe, start_time, end_time, args.output))


if __name__ == "__main__":
    main()
