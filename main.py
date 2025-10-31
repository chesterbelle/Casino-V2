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
from typing import Dict, Optional

# Add current directory to path for config import
sys.path.insert(0, os.getcwd())
from core import (
    ask_initial_balance,
    config,
    print_session_summary,
    run_session_with_player,
)
from players import fixed_player, kelly_player, paroli_player

try:
    from live_session import run_live_session
except ImportError:
    from core.live_session import run_live_session


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
# 🚀 ENTRYPOINT
# ============================================================
def main() -> None:
    """Main unificado: detecta MODE de config y ejecuta live o backtest"""
    mode = getattr(config, "MODE", "backtest").lower()

    player_name = DEFAULT_PLAYER
    multi_asset_config = None

    # Parsear argumentos de línea de comandos
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            arg = arg.lower()
            if arg.startswith("--player="):
                player_name = arg.replace("--player=", "")
            elif arg == "--multi-asset":
                mode = "multi_asset_backtest"
            elif arg == "--ccxt-live":
                mode = "live_ccxt"

    if player_name not in AVAILABLE_PLAYERS:
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
        if exchange == "HYPERLIQUID":
            from utils.hyperliquid_env_loader import (
                load_hyperliquid_config,
                validate_hyperliquid_config,
            )

            if not validate_hyperliquid_config(load_hyperliquid_config()):
                print("❌ Credenciales de Hyperliquid no configuradas.")
                print("Configura HYPERLIQUID_API_KEY y HYPERLIQUID_API_SECRET en tu .env")
                return
        elif exchange == "KRAKEN_DEMO":
            print("🎯 Usando Kraken Futures Demo - no requiere credenciales")
            print("Exchange confiable para testing inicial")
        elif exchange == "KRAKEN_DEMO":
            from utils.kraken_env_loader import (
                load_kraken_config,
                validate_kraken_config,
            )

            if not validate_kraken_config(load_kraken_config()):
                print("❌ Credenciales de Kraken no configuradas.")
                print("Configura KRAKEN_API_KEY y KRAKEN_API_SECRET en tu .env")
                return

        # Ejecutar live session integrada
        run_live_session(symbol=None, interval=None, player_module=player_module, player_name=player_name)
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

    # Configuración de sesión
    initial_balance = ask_initial_balance()

    # Inicializar Gemini (validador)
    from gemini.gemini_core import Gemini

    gemini = Gemini()

    print(f"\n🟢 Iniciando sesión: {mode}")

    # Ejecutar sesión con configuración apropiada
    stats = run_session_with_player(dataset_path, initial_balance, gemini, player_module, player_name, mode=mode)

    print_session_summary(stats)

    # Guardar memoria
    gemini.memory.save()
    print("💾 Memoria de Gemini guardada.")

    print("✅ Sesión completada.\n")


if __name__ == "__main__":
    main()
