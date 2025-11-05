#!/usr/bin/env python3
"""
🧪 TEST TP/SL EXECUTION
========================

Script para probar que las órdenes TP/SL se ejecutan y detectan correctamente.

Estrategia:
1. Conectar a Kraken Demo
2. Abrir posición pequeña con TP/SL MUY CERCANOS (0.1% / 0.1%)
3. Usar leverage alto para que se ejecute rápido
4. Monitorear cada segundo hasta que cierre
5. Verificar que se detecta el cierre

Uso:
    python utils/test_tp_sl_execution.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tables.ccxt_adapter import CCXTAdapter
from tables.connectors.kraken.kraken_connector import KrakenConnector


async def main():
    print("=" * 60)
    print("🧪 TEST TP/SL EXECUTION")
    print("=" * 60)
    print()

    # 1. CONECTAR
    print("🔌 Conectando a Kraken Demo...")
    connector = KrakenConnector(mode="testing")
    await connector.connect()

    adapter = CCXTAdapter(connector=connector, symbol="BTC/USD", timeframe="1m", starting_balance=10000.0)
    await adapter.connect()
    print(f"✅ Conectado | Balance: ${adapter.balance_manager.balance:.2f}")
    print()

    # 2. OBTENER PRECIO ACTUAL
    print("📊 Obteniendo precio actual...")
    candle = await adapter.next_candle()
    current_price = candle["close"]
    print(f"💰 Precio actual: ${current_price:.2f}")
    print()

    # 3. CREAR ORDEN CON TP/SL MÁS AMPLIOS
    print("📝 Creando orden de prueba...")
    print("   - Side: BUY (LONG)")
    print("   - Amount: 0.001 BTC (~$100)")
    print("   - Leverage: 50x")
    print("   - TP: +2% (más amplio para evitar invalidPrice)")
    print("   - SL: -2% (más amplio para evitar invalidPrice)")
    print()

    order = {
        "symbol": "BTC/USD",
        "side": "buy",
        "amount": 0.001,
        "type": "market",
        "take_profit": 1.02,  # +2%
        "stop_loss": 0.98,  # -2%
        "trade_id": "test_tp_sl_001",
        "params": {"leverage": 50},
        "player": "test",
        "timeframe": "1m",
        "cycle_step": 0,
    }

    result = await adapter.execute_order(order)

    print(f"📋 Resultado: {result.get('status')}")

    if result.get("status") not in ["opened", "closed"]:
        print(f"❌ Error ejecutando orden: {result}")
        await connector.close()
        return

    print(f"✅ Orden ejecutada!")
    print(f"   Entry: ${result.get('entry_price', 0):.2f}")
    print(f"   TP: ${result.get('tp_price', 0):.2f}")
    print(f"   SL: ${result.get('sl_price', 0):.2f}")
    print()

    # 4. MONITOREAR HASTA QUE CIERRE
    print("⏳ Monitoreando posición (máx 5 minutos)...")
    print("   Esperando que el precio toque TP o SL...")
    print()

    max_checks = 300  # 5 minutos (1 check por segundo)
    check_count = 0

    while check_count < max_checks:
        check_count += 1

        # Esperar 1 segundo
        await asyncio.sleep(1)

        # Verificar posiciones abiertas
        open_positions = adapter.position_tracker.open_positions

        if len(open_positions) == 0:
            print(f"✅ POSICIÓN CERRADA después de {check_count} segundos!")
            print()
            break

        # Mostrar progreso cada 10 segundos
        if check_count % 10 == 0:
            # Obtener precio actual
            try:
                ticker = await connector.fetch_ticker("BTC/USD")
                current = ticker.get("last", 0)
                entry = result.get("entry_price", 0)
                pnl_pct = ((current - entry) / entry) * 100 if entry > 0 else 0

                print(
                    f"   [{check_count}s] Precio: ${current:.2f} | PnL: {pnl_pct:+.2f}% | Posiciones: {len(open_positions)}"
                )
            except Exception:  # noqa: S110
                print(f"   [{check_count}s] Posiciones abiertas: {len(open_positions)}")

    if check_count >= max_checks:
        print("⏰ Timeout - La posición no cerró en 5 minutos")
        print()

    # 5. VERIFICAR TRADES CERRADOS
    print("📊 Verificando trades cerrados...")

    # Fetch trades from exchange
    try:
        recent_trades = await connector.fetch_my_trades(symbol="BTC/USD", limit=10)
        print(f"✅ Trades recientes: {len(recent_trades)}")

        if recent_trades:
            print()
            print("📋 Últimos trades:")
            for i, trade in enumerate(recent_trades[:5], 1):
                trade_id = trade.get("id", "N/A")
                side = trade.get("side", "N/A")
                price = trade.get("price", 0)
                amount = trade.get("amount", 0)
                timestamp = trade.get("timestamp", 0)
                info = trade.get("info", {})
                reduce_only = info.get("reduceOnly", False)
                realized_pnl = info.get("realizedPnl", 0)

                print(f"   {i}. {side.upper()} {amount:.4f} @ ${price:.2f}")
                print(f"      ID: {trade_id}")
                print(f"      ReduceOnly: {reduce_only}")
                print(f"      Realized PnL: ${realized_pnl:.2f}")
                print(f"      Timestamp: {timestamp}")
                print()
    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        print()

    # 6. STATS FINALES
    print("=" * 60)
    print("📊 RESULTADOS FINALES")
    print("=" * 60)

    stats = adapter.position_tracker.get_stats()
    print(f"Balance final: ${adapter.balance_manager.balance:.2f}")
    print(f"Posiciones abiertas: {stats['open_positions']}")
    print(f"Trades abiertos: {stats['total_trades_opened']}")
    print(f"Trades cerrados: {stats['total_trades_closed']}")
    print(f"Wins: {stats['wins']}")
    print(f"Losses: {stats['losses']}")
    print(f"Win rate: {stats['win_rate']:.2%}")
    print()

    # 7. DESCONECTAR
    print("🔌 Desconectando...")
    await connector.close()
    print("✅ Test completado!")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
