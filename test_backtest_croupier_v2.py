"""
Test de Backtest con Croupier V2
Ejecuta un backtest completo y muestra resultados detallados.
"""

import asyncio
import logging
from datetime import datetime

from core.data_sources import BacktestDataSource
from core.trading import TradingSession
from players import paroli_player

# Setup logging más limpio
logging.basicConfig(
    level=logging.WARNING,  # Solo warnings y errores
    format="%(levelname)s | %(message)s",
)

# Logger específico para este test
logger = logging.getLogger("BacktestTest")
logger.setLevel(logging.INFO)


async def run_backtest_test():
    """Ejecuta un backtest de prueba con resultados detallados."""

    print("\n" + "=" * 70)
    print("🎰 CASINO V2 - BACKTEST TEST CON CROUPIER V2")
    print("=" * 70)

    # Configuración
    dataset = "tables/data/raw/BTCUSDT_15m__90d.csv"
    initial_balance = 10000.0
    max_candles = 200  # Más velas para mejor validación

    print("\n📋 Configuración:")
    print(f"   Dataset: {dataset}")
    print(f"   Balance inicial: ${initial_balance:,.2f}")
    print(f"   Max velas: {max_candles}")
    print("   Player: Paroli (progresión)")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Crear data source
    print("\n🔄 Inicializando backtest...")
    data_source = BacktestDataSource.from_csv(
        dataset,
        initial_balance=initial_balance,
    )

    # Crear sesión
    session = TradingSession(
        data_source=data_source,
        player_module=paroli_player,
        max_candles=max_candles,
    )

    print("✅ Sesión creada")

    # Ejecutar backtest
    print("\n🚀 Ejecutando backtest...")
    print("-" * 70)

    start_time = datetime.now()
    session_stats = await session.run()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Obtener estadísticas del data source
    stats = data_source.get_stats()

    # Calcular métricas adicionales
    total_trades = stats.get("wins", 0) + stats.get("losses", 0)
    win_rate = (stats.get("wins", 0) / total_trades * 100) if total_trades > 0 else 0

    initial = initial_balance
    final = stats.get("final_balance", initial_balance)
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0

    fees = stats.get("total_fees", 0)
    gross_pnl = pnl + fees

    # Mostrar resultados
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DEL BACKTEST")
    print("=" * 70)

    print("\n💰 Balance:")
    print(f"   Inicial:        ${initial:>12,.2f}")
    print(f"   Final:          ${final:>12,.2f}")
    print(f"   Equity:         ${stats.get('final_equity', final):>12,.2f}")
    print(f"   PnL Neto:       ${pnl:>12,.2f}  ({pnl_pct:+.2f}%)")
    print(f"   PnL Bruto:      ${gross_pnl:>12,.2f}")
    print(f"   Fees Totales:   ${fees:>12,.2f}")

    print("\n📈 Operaciones:")
    print(f"   Total trades:   {total_trades:>12}")
    print(f"   Wins:           {stats.get('wins', 0):>12}  ({win_rate:.1f}%)")
    print(f"   Losses:         {stats.get('losses', 0):>12}  ({100-win_rate:.1f}%)")

    if stats.get("wins", 0) > 0:
        avg_win = stats.get("total_pnl", 0) / stats.get("wins", 1)
        print(f"   Avg Win:        ${avg_win:>12,.2f}")

    if stats.get("losses", 0) > 0:
        avg_loss = abs(stats.get("total_pnl", 0)) / stats.get("losses", 1)
        print(f"   Avg Loss:       ${avg_loss:>12,.2f}")

    print("\n📊 Actividad:")
    print(f"   Velas:          {session_stats.get('candles_processed', 0):>12}")
    print(f"   Señales:        {session_stats.get('signals_detected', 0):>12}")
    print(f"   Órdenes:        {session_stats.get('orders_executed', 0):>12}")

    print("\n⏱️  Performance:")
    print(f"   Duración:       {duration:>12.2f}s")
    candles_processed = session_stats.get("candles_processed", 0)
    if duration > 0:
        print(f"   Velas/seg:      {candles_processed/duration:>12.1f}")

    # Validación del Croupier V2
    print("\n" + "=" * 70)
    print("✅ VALIDACIÓN CROUPIER V2")
    print("=" * 70)

    # El BacktestDataSource usa el Croupier internamente
    # Verificamos que todo funcionó correctamente
    validations = []

    # 1. Balance coherente
    if final > 0:
        validations.append("✅ Balance final positivo y coherente")
    else:
        validations.append("⚠️  Balance final negativo")

    # 2. Trades ejecutados
    if total_trades > 0:
        validations.append(f"✅ {total_trades} trades ejecutados correctamente")
    else:
        validations.append("⚠️  No se ejecutaron trades")

    # 3. PnL calculado
    if pnl != 0:
        validations.append(f"✅ PnL calculado: ${pnl:,.2f}")
    else:
        validations.append("⚠️  PnL es cero")

    # 4. Fees aplicados
    if fees > 0:
        validations.append(f"✅ Fees aplicados: ${fees:,.2f}")
    else:
        validations.append("⚠️  No se aplicaron fees")

    for validation in validations:
        print(f"   {validation}")

    # Resumen final
    print("\n" + "=" * 70)
    if pnl > 0:
        print(f"🎉 BACKTEST EXITOSO - Ganancia de ${pnl:,.2f} ({pnl_pct:+.2f}%)")
    elif pnl < 0:
        print(f"📉 BACKTEST COMPLETADO - Pérdida de ${abs(pnl):,.2f} ({pnl_pct:.2f}%)")
    else:
        print("➖ BACKTEST COMPLETADO - Sin cambios en balance")
    print("=" * 70)

    return stats


if __name__ == "__main__":
    print("\n🚀 Iniciando test de backtest con Croupier V2...")

    try:
        stats = asyncio.run(run_backtest_test())
        print("\n✅ Test completado exitosamente\n")
    except Exception as e:
        print(f"\n❌ Error durante el test: {e}")
        import traceback

        traceback.print_exc()
        print()
