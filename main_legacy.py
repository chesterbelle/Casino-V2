"""
====================================================
🎰 CASINO V2 — Main con arquitectura Gemini + Player
====================================================

NUEVA ARQUITECTURA (Fase 1 - Separación de Responsabilidades):
---------------------------------------------------------------
1) Gemini valida oportunidades → retorna Verdict
2) Player decide tamaño → retorna size_fraction
3) Gemini construye orden → make_order_from_verdict()
4) Croupier ejecuta → route_order()
5) Gemini actualiza memoria → on_trade_result()

Ventajas sobre main.py:
-----------------------
✅ Gemini solo valida probabilidades (responsabilidad única)
✅ Players intercambiables (Kelly, Fixed%, Adaptive, etc.)
✅ Testing independiente de validación vs sizing
✅ Extensible para múltiples players simultáneos

Uso:
----
    python main_v2.py              # Usa Kelly Player (default)
    python main_v2.py --player=fixed  # Usa Fixed Player

Compatibilidad:
---------------
• Usa las mismas mesas, sensores y croupiers que V1
• Memoria Gemini 100% compatible
• Resultados matemáticamente idénticos a main.py (con Kelly)
"""

from __future__ import annotations

import logging
import os
import sys

# Add current directory to path for config import
sys.path.insert(0, os.getcwd())

from core import (  # noqa: E402
    ask_initial_balance,
    config,
    print_session_summary,
    run_session_with_player,
)
from core.testing_session import run_testing_session  # noqa: E402
from players import fixed_player, kelly_player, paroli_player  # noqa: E402

try:
    from live_session import run_live_session  # noqa: E402
except ImportError:
    from core.live_session import run_live_session  # noqa: E402


# ============================================================
# 🪙 LOGGING GLOBAL
# ============================================================
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("MainV2")


# ============================================================
# 🎮 CONFIGURACIÓN DE PLAYERS
# ============================================================
AVAILABLE_PLAYERS = {
    "kelly": kelly_player,
    "fixed": fixed_player,
    "paroli": paroli_player,
}

# Player por defecto
DEFAULT_PLAYER = "paroli"


# ============================================================
# 🛠️ FUNCIONES AUXILIARES
# ============================================================
def _print_help():
    """Imprime información de ayuda sobre el uso del sistema."""
    print("\n" + "=" * 60)
    print("🎰 CASINO V2 - Sistema de Trading Automatizado")
    print("=" * 60)
    print("\nUSO:")
    print("  python main.py [opciones]")
    print("\nOPCIONES GENERALES:")
    print("  --player=<nombre>    Seleccionar player (kelly, fixed, paroli)")
    print("                       Por defecto: paroli")
    print("  --help, -h           Mostrar esta ayuda")
    print("\nOPCIONES MODO LIVE:")
    print("  --symbol=<symbol>    Símbolo a operar (ej: BTC, LTC, ETH)")
    print("                       Por defecto: BTC")
    print("  --interval=<time>    Intervalo de tiempo (ej: 1m, 5m, 15m, 1h)")
    print("                       Por defecto: 1m")
    print("  --max-candles=<n>    Máximo de velas antes de detenerse")
    print("                       Por defecto: ilimitado")
    print("\nOPCIONES BACKTEST:")
    print("  --multi-asset        Ejecutar backtest multi-asset")
    print("  --ccxt-live          Forzar modo live con CCXT")
    print("\nMODOS:")
    print("  El modo se configura en core/config.py:")
    print("  - MODE = 'backtest'  → Simulación con datos históricos")
    print("  - MODE = 'testing'  → Kraken Demo / modo paper trading")
    print("  - MODE = 'live'     → Trading en vivo (placeholder v2.4+)")
    print("\nEXCHANGES SOPORTADOS (modo live):")
    print("  - Kraken Futures Demo")
    print("  - Binance Futures Testnet")
    print("  - Hyperliquid")
    print("\nEJEMPLOS:")
    print("  # Backtest con player por defecto")
    print("  python main.py")
    print("")
    print("  # Backtest con Kelly player")
    print("  python main.py --player=kelly")
    print("")
    print("  # Live trading con LTC, 1m, máximo 100 velas")
    print("  python main.py --symbol=LTC --interval=1m --max-candles=100")
    print("")
    print("  # Live trading con BTC, sin límite de velas")
    print("  python main.py --symbol=BTC --interval=5m")
    print("\nCONFIGURACIÓN:")
    print("  Editar core/config.py para cambiar:")
    print("  - MODE (backtest/live)")
    print("  - EXCHANGE (KRAKEN, BINANCE, HYPERLIQUID)")
    print("  - DATASET_PATH (para backtest)")
    print("  - Otros parámetros del sistema")
    print("\nCREDENCIALES:")
    print("  Las API keys se configuran en el archivo .env")
    print("  Ver docs/guides/development-setup.md para más información")
    print("=" * 60 + "\n")


def _validate_exchange_credentials(exchange: str) -> bool:
    """
    Valida que las credenciales del exchange estén configuradas correctamente.

    Args:
        exchange: Nombre del exchange (KRAKEN_DEMO, BINANCE_FUTURES_TESTNET, etc.)

    Returns:
        True si las credenciales son válidas, False en caso contrario
    """
    exchange_upper = exchange.upper()

    if "HYPERLIQUID" in exchange_upper:
        try:
            from utils.exchanges.hyperliquid_env_loader import (
                load_hyperliquid_config,
                validate_hyperliquid_config,
            )

            if not validate_hyperliquid_config(load_hyperliquid_config()):
                print("❌ Credenciales de Hyperliquid no configuradas.")
                print("Configura HYPERLIQUID_API_KEY y HYPERLIQUID_API_SECRET en tu .env")
                return False
            print("✅ Credenciales de Hyperliquid validadas")
            return True
        except Exception as e:
            logger.error(f"Error validando Hyperliquid: {e}")
            print(f"❌ Error validando credenciales de Hyperliquid: {e}")
            return False

    elif "KRAKEN" in exchange_upper:
        try:
            from utils.exchanges.kraken_env_loader import (
                load_kraken_config,
                validate_kraken_config,
            )

            if not validate_kraken_config(load_kraken_config()):
                print("❌ Credenciales de Kraken no configuradas.")
                print("Configura KRAKEN_FUTURES_API_KEY y KRAKEN_FUTURES_API_SECRET en tu .env")
                return False
            print("✅ Credenciales de Kraken validadas")
            print("🎯 Usando Kraken Futures Demo - Exchange confiable para testing")
            return True
        except Exception as e:
            logger.error(f"Error validando Kraken: {e}")
            print(f"❌ Error validando credenciales de Kraken: {e}")
            return False

    elif "BINANCE" in exchange_upper:
        try:
            from utils.exchanges.binance_env_loader import (
                load_binance_config,
                validate_binance_config,
            )

            if not validate_binance_config(load_binance_config()):
                print("❌ Credenciales de Binance no configuradas.")
                print("Configura BINANCE_TESTNET_API_KEY y BINANCE_TESTNET_SECRET en tu .env")
                return False
            print("✅ Credenciales de Binance validadas")
            return True
        except Exception as e:
            logger.error(f"Error validando Binance: {e}")
            print(f"❌ Error validando credenciales de Binance: {e}")
            return False

    else:
        logger.warning(f"Exchange desconocido: {exchange}, asumiendo válido")
        return True


# ============================================================
# 🚀 ENTRYPOINT
# ============================================================
def main() -> None:
    """Main unificado: detecta MODE de config y ejecuta live o backtest"""
    try:
        mode = getattr(config, "MODE", "backtest").lower()
    except Exception as e:
        logger.error(f"❌ Error leyendo MODE de config: {e}")
        mode = "backtest"

    player_name = DEFAULT_PLAYER
    symbol = None
    interval = None
    max_candles = None

    # Parsear argumentos de línea de comandos
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            arg_lower = arg.lower()
            if arg_lower.startswith("--player="):
                player_name = arg_lower.replace("--player=", "")
            elif arg_lower.startswith("--symbol="):
                symbol = arg.split("=", 1)[1]  # Mantener case original
            elif arg_lower.startswith("--interval="):
                interval = arg_lower.replace("--interval=", "")
            elif arg_lower.startswith("--max-candles="):
                try:
                    max_candles = int(arg_lower.replace("--max-candles=", ""))
                except ValueError:
                    logger.warning(f"⚠️ Valor inválido para --max-candles: {arg}")
            elif arg_lower == "--multi-asset":
                mode = "multi_asset_backtest"
            elif arg_lower == "--ccxt-live":
                mode = "live_ccxt"
            elif arg_lower in ["--help", "-h"]:
                _print_help()
                return

    if player_name not in AVAILABLE_PLAYERS:
        logger.warning(f"⚠️ Player '{player_name}' no encontrado. Usando {DEFAULT_PLAYER}")
        print(f"⚠️ Player '{player_name}' no encontrado. Usando {DEFAULT_PLAYER}")
        print(f"Players disponibles: {', '.join(AVAILABLE_PLAYERS.keys())}")
        player_name = DEFAULT_PLAYER

    player_module = AVAILABLE_PLAYERS[player_name]

    # =====================================================
    # 🎯 DETECCIÓN AUTOMÁTICA DE MODO
    # =====================================================

    if mode == "live":
        print("\n🎰 Casino V2 — Live Trading (Testnet)\n")
        print(f"🎮 Player seleccionado: {player_name.upper()}")
        print(f"🏦 Exchange: {getattr(config, 'EXCHANGE', 'HYPERLIQUID')}")

        # Verificar credenciales antes de iniciar
        exchange = getattr(config, "EXCHANGE", "HYPERLIQUID")

        if not _validate_exchange_credentials(exchange):
            logger.error(f"❌ Validación de credenciales falló para {exchange}")
            return

        # Ejecutar live session integrada con manejo de errores (async)
        try:
            import asyncio

            asyncio.run(
                run_live_session(
                    symbol=symbol,
                    interval=interval,
                    max_candles=max_candles,
                    player_module=player_module,
                    player_name=player_name,
                )
            )
        except KeyboardInterrupt:
            logger.info("\n⚠️ Sesión interrumpida por usuario (Ctrl+C)")
            print("\n⚠️ Sesión interrumpida por usuario")
        except Exception as e:
            logger.error(f"❌ Error en sesión live: {e}", exc_info=True)
            print(f"\n❌ Error en sesión live: {e}")
            print("Revisa los logs para más detalles")
        return

    if mode == "testing":
        print("\n🎰 Casino V2 — Testing Mode (Kraken Demo)\n")
        print(f"🎮 Player seleccionado: {player_name.upper()}")
        print(f"🏦 Exchange: {getattr(config, 'EXCHANGE', 'KRAKEN')}")

        try:
            import asyncio

            asyncio.run(
                run_testing_session(
                    symbol=symbol,
                    interval=interval,
                    max_candles=max_candles,
                    player_module=player_module,
                    player_name=player_name,
                )
            )
        except KeyboardInterrupt:
            logger.info("\n⚠️ Sesión testing interrumpida por usuario (Ctrl+C)")
            print("\n⚠️ Sesión testing interrumpida por usuario")
        except Exception as e:
            logger.error(f"❌ Error en sesión testing: {e}", exc_info=True)
            print(f"\n❌ Error en sesión testing: {e}")
            print("Revisa los logs para más detalles")
        return

    # =====================================================
    # 📊 MODO BACKTEST
    # =====================================================

    print("\n🎰 Casino V2 — Backtest Mode\n")

    # Configurar modo backtest
    if mode == "multi_asset_backtest":
        print("🔄 MODO: Multi-Asset Backtest")
        raise NotImplementedError("Multi-asset backtest not yet implemented in v1.7")
    elif mode == "live_ccxt":
        print("🔄 MODO: Live Trading con CCXT Pro")
        dataset_path = "live_ccxt"  # Placeholder
    else:
        print("🔄 MODO: Single-Asset Backtest")
        dataset_path = getattr(config, "DATASET_PATH", "tables/data/raw/BTCUSDT_1m__30d.csv")

    print(f"🎮 Player seleccionado: {player_name.upper()}")
    print(f"📁 Dataset: {dataset_path}")

    # Configuración de sesión con manejo de errores
    try:
        initial_balance = ask_initial_balance()
    except (ValueError, KeyboardInterrupt) as e:
        logger.error(f"❌ Error obteniendo balance inicial: {e}")
        print("\n❌ Operación cancelada")
        return

    # Inicializar Gemini (validador)
    try:
        from gemini.gemini_core import Gemini

        gemini = Gemini()
    except Exception as e:
        logger.error(f"❌ Error inicializando Gemini: {e}", exc_info=True)
        print(f"\n❌ Error inicializando Gemini: {e}")
        return

    print(f"\n🟢 Iniciando sesión: {mode}")

    # Ejecutar sesión con configuración apropiada
    try:
        stats = run_session_with_player(dataset_path, initial_balance, gemini, player_module, player_name, mode=mode)
        print_session_summary(stats)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Sesión interrumpida por usuario (Ctrl+C)")
        print("\n⚠️ Sesión interrumpida por usuario")
    except Exception as e:
        logger.error(f"❌ Error en sesión backtest: {e}", exc_info=True)
        print(f"\n❌ Error en sesión: {e}")
        print("Revisa los logs para más detalles")
    finally:
        # Guardar memoria siempre, incluso si hay error
        try:
            gemini.memory.save()
            print("💾 Memoria de Gemini guardada.")
        except Exception as e:
            logger.error(f"⚠️ Error guardando memoria: {e}")
            print(f"⚠️ No se pudo guardar la memoria: {e}")

    print("✅ Sesión completada.\n")


if __name__ == "__main__":
    main()
