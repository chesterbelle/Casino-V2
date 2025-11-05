#!/usr/bin/env python3
"""
Descarga OHLCV de un período exacto usando CCXT directamente
"""
import asyncio
import sys
from pathlib import Path

import ccxt.async_support as ccxt
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def download_exact_period(start_ts: int, end_ts: int, output: str):
    """
    Descarga OHLCV de un período exacto.

    Args:
        start_ts: Timestamp inicio en ms
        end_ts: Timestamp fin en ms
        output: Ruta del archivo CSV
    """
    print("=" * 60)
    print("📥 DOWNLOAD EXACT PERIOD")
    print("=" * 60)

    # Crear exchange
    exchange = ccxt.krakenfutures(
        {
            "enableRateLimit": True,
        }
    )

    try:
        print("\n🔌 Conectando a Kraken Futures...")
        await exchange.load_markets()
        print("✅ Conectado")

        # Descargar datos
        print(f"\n📊 Descargando período...")
        print(f"   Start: {start_ts} ({pd.to_datetime(start_ts, unit='ms')})")
        print(f"   End:   {end_ts} ({pd.to_datetime(end_ts, unit='ms')})")

        all_candles = []
        current_ts = start_ts

        while current_ts < end_ts:
            # Fetch batch
            candles = await exchange.fetch_ohlcv(symbol="BTC/USD:USD", timeframe="1m", since=current_ts, limit=500)

            if not candles:
                break

            # Filter candles within range
            for candle in candles:
                if start_ts <= candle[0] <= end_ts:
                    all_candles.append(candle)

            # Update current timestamp
            current_ts = candles[-1][0] + 60000  # +1 minute

            print(f"   Descargadas: {len(all_candles)} velas...")

            if current_ts >= end_ts:
                break

        if not all_candles:
            print("❌ No se obtuvieron datos")
            return

        print(f"✅ Total: {len(all_candles)} velas")

        # Convertir a DataFrame
        df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]

        # Preview
        print(f"\n📊 Preview:")
        print(df.head(3))
        print("...")
        print(df.tail(3))

        # Guardar
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        print(f"\n💾 Guardado en: {output_path}")
        print(f"   Velas: {len(df)}")
        print(f"   Tamaño: {output_path.stat().st_size / 1024:.2f} KB")

    finally:
        await exchange.close()
        print("\n🔌 Desconectado")

    print("\n" + "=" * 60)
    print("✅ COMPLETADO")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python download_exact_period.py <start_ts> <end_ts> <output.csv>")
        print("Ejemplo: python download_exact_period.py 1762346100000 1762349640000 data/round1.csv")
        sys.exit(1)

    start_ts = int(sys.argv[1])
    end_ts = int(sys.argv[2])
    output = sys.argv[3]

    asyncio.run(download_exact_period(start_ts, end_ts, output))
