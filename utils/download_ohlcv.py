#!/usr/bin/env python3
"""
Download OHLCV - Casino V2

Descarga datos OHLCV de Kraken Futures para comparación testing vs backtest.

Usage:
    # Últimas 60 velas
    python utils/download_ohlcv.py --symbol=BTC/USD --interval=1m --last-n-candles=60

    # Período específico
    python utils/download_ohlcv.py --symbol=BTC/USD --interval=1m \
        --start=1762333140000 --end=1762336740000

    # Con output personalizado
    python utils/download_ohlcv.py --symbol=BTC/USD --interval=1m \
        --last-n-candles=60 --output=data/my_test.csv
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exchanges.connectors.kraken.kraken_connector import KrakenConnector


async def download_ohlcv(
    symbol: str,
    interval: str,
    start_ts: int = None,
    end_ts: int = None,
    last_n_candles: int = None,
    output: str = None,
):
    """
    Descarga OHLCV de Kraken Futures.

    Args:
        symbol: Par de trading (ej: BTC/USD)
        interval: Timeframe (1m, 5m, 15m, 1h, etc)
        start_ts: Timestamp inicio en ms (opcional)
        end_ts: Timestamp fin en ms (opcional)
        last_n_candles: Número de velas recientes (alternativa a start/end)
        output: Ruta del archivo CSV de salida
    """
    print("=" * 60)
    print("📥 DOWNLOAD OHLCV - Casino V2")
    print("=" * 60)

    # Crear connector
    connector = KrakenConnector(mode="testing")

    try:
        # Conectar
        print(f"\n🔌 Conectando a Kraken Futures...")
        await connector.connect()
        print("✅ Conectado")

        # Determinar parámetros de descarga
        if last_n_candles:
            # Calcular timestamps basado en last_n_candles
            print(f"\n📊 Descargando últimas {last_n_candles} velas...")
            limit = last_n_candles
        elif start_ts and end_ts:
            # Usar timestamps específicos
            print(f"\n📊 Descargando período específico...")
            print(f"   Inicio: {datetime.fromtimestamp(start_ts/1000)}")
            print(f"   Fin:    {datetime.fromtimestamp(end_ts/1000)}")
            # Calcular número de velas necesarias
            duration_ms = end_ts - start_ts
            interval_ms = 60000  # 1m = 60000ms (simplificado, debería parsear interval)
            limit = int(duration_ms / interval_ms) + 10  # +10 para asegurar que tenemos suficientes
        else:
            raise ValueError("Debes especificar --last-n-candles o --start y --end")

        # Descargar datos
        print(f"   Symbol: {symbol}")
        print(f"   Interval: {interval}")
        print(f"   Limit: {limit}")

        ohlcv = await connector.fetch_ohlcv(symbol=symbol, timeframe=interval, limit=limit)

        if not ohlcv:
            print("❌ No se obtuvieron datos")
            return

        print(f"✅ Descargadas {len(ohlcv)} velas")

        # Convertir a DataFrame
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Agregar columna de fecha legible
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")

        # Reordenar columnas
        df = df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]

        # Mostrar preview
        print(f"\n📊 Preview de datos:")
        print(df.head(3))
        print("...")
        print(df.tail(3))

        # Estadísticas
        print(f"\n📈 Estadísticas:")
        print(f"   Velas: {len(df)}")
        print(f"   Período: {df['datetime'].iloc[0]} → {df['datetime'].iloc[-1]}")
        print(f"   Precio: ${df['close'].iloc[0]:.2f} → ${df['close'].iloc[-1]:.2f}")
        print(f"   Rango: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

        # Guardar CSV
        if not output:
            # Generar nombre automático
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"data/ohlcv_{symbol.replace('/', '_')}_{interval}_{timestamp_str}.csv"

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_path, index=False)
        print(f"\n💾 Guardado en: {output_path}")
        print(f"   Tamaño: {output_path.stat().st_size / 1024:.2f} KB")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

    finally:
        # Desconectar
        await connector.close()
        print("\n🔌 Desconectado")

    print("\n" + "=" * 60)
    print("✅ DESCARGA COMPLETADA")
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Descarga OHLCV de Kraken Futures para testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Últimas 60 velas de 1 minuto
  python utils/download_ohlcv.py --symbol=BTC/USD --interval=1m --last-n-candles=60

  # Período específico
  python utils/download_ohlcv.py --symbol=BTC/USD --interval=1m \\
      --start=1762333140000 --end=1762336740000

  # Con output personalizado
  python utils/download_ohlcv.py --symbol=BTC/USD --interval=1m \\
      --last-n-candles=60 --output=data/round1_comparison.csv
        """,
    )

    parser.add_argument("--symbol", type=str, required=True, help="Par de trading (ej: BTC/USD)")

    parser.add_argument(
        "--interval",
        type=str,
        required=True,
        help="Timeframe (1m, 5m, 15m, 1h, etc)",
    )

    parser.add_argument(
        "--last-n-candles",
        type=int,
        help="Número de velas recientes a descargar",
    )

    parser.add_argument("--start", type=int, help="Timestamp inicio en milisegundos")

    parser.add_argument("--end", type=int, help="Timestamp fin en milisegundos")

    parser.add_argument(
        "--output",
        type=str,
        help="Ruta del archivo CSV de salida (default: auto-generado)",
    )

    args = parser.parse_args()

    # Validar argumentos
    if not args.last_n_candles and not (args.start and args.end):
        parser.error("Debes especificar --last-n-candles o --start y --end")

    if args.last_n_candles and (args.start or args.end):
        parser.error("No puedes usar --last-n-candles con --start/--end")

    # Ejecutar descarga
    asyncio.run(
        download_ohlcv(
            symbol=args.symbol,
            interval=args.interval,
            start_ts=args.start,
            end_ts=args.end,
            last_n_candles=args.last_n_candles,
            output=args.output,
        )
    )


if __name__ == "__main__":
    main()
