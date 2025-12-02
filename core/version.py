"""
====================================================
📌 VERSION - Casino V2
====================================================

Versión única del sistema Casino V2.
Este es la ÚNICA fuente de verdad para la versión del proyecto.

IMPORTANTE: Si cambias la versión aquí, debes actualizar:
1. README.md
2. DEVELOPER.md
3. docs/workflow.md
4. docs/development/PENDIENTES.md
5. docs/CHANGELOG.md

Usa el script scripts/check_docs_sync.py para verificar sincronización.
====================================================
"""

from typing import Dict, Literal

# =====================================================
# 🎯 VERSIÓN ACTUAL
# =====================================================
__version__ = "2.0.0"
__version_name__ = "Native SDK Migration"
__release_date__ = "2025-12-01"
__status__: Literal["stable", "beta", "alpha", "dev"] = "beta"

# =====================================================
# 📝 CHANGELOG RESUMIDO
# =====================================================
CHANGELOG = {
    "1.9.2": {
        "name": "Paroli Progression Fix",
        "date": "2025-11-05",
        "highlights": [
            "Implementada progresión Paroli (1x-4x-8x) en TradingSession",
            "Agregado player_state para tracking de progresión",
            "Implementado _check_and_process_closed_trades() para detectar TP/SL",
            "handle_trade_outcome() se llama cuando posición cierra",
            "Metadata (paroli_state) se pasa a BuildOrderStage",
            "Auditoría exhaustiva de lógica del bot completada",
        ],
    },
    "1.9.1": {
        "name": "Clean Up Logic",
        "date": "2025-11-03",
        "highlights": [
            "Limpieza de código y documentación",
            "Correcciones de linting y formato",
            "Mejoras en estructura del proyecto",
        ],
    },
    "1.9": {
        "name": "Tres Modos + Conectores Híbridos",
        "date": "2025-11-04",
        "highlights": [
            "Config con modos backtest/testing/live",
            "KrakenConnector híbrido (testing/live) con validaciones",
            "Placeholders de Binance/Hyperliquid y sesiones testing/live",
            "BrokerInterface y tests actualizados para nuevos modos",
        ],
    },
    "1.8": {
        "name": "Mesa + Conectores",
        "date": "2025-11-03",
        "highlights": [
            "Arquitectura modular Mesa + Conectores",
            "KrakenConnector implementado",
            "Separación clara de responsabilidades",
            "Código más limpio y mantenible",
            "Inspirado en Hummingbot",
        ],
    },
    "1.7": {
        "name": "Code Cleanup & Organization",
        "date": "2025-10-15",
        "highlights": [
            "Pre-commit hooks configurados",
            "Código limpio y formateado",
            "Errores de linting corregidos",
            "Table multiasset eliminada",
        ],
    },
    "2.0.0": {
        "name": "Native SDK Migration",
        "date": "2025-12-01",
        "highlights": [
            "Migración completa a Native SDKs (Binance Futures, Hyperliquid)",
            "Eliminación de dependencia CCXT",
            "Refactorización de ExchangeAdapter",
            "Soporte para Agent Wallet en Hyperliquid",
            "Mejoras en sincronización de tiempo y WebSockets",
        ],
    },
    "1.9.3": {
        "name": "Testing & Validation",
        "date": "2025-11-05",
        "highlights": ["Testing & Validation phase"],
    },
}

# =====================================================
# 🎯 PRÓXIMA VERSIÓN
# =====================================================
NEXT_VERSION = "2.0"
NEXT_VERSION_NAME = "Multi-Asset Expansion"
NEXT_VERSION_ETA = "2026-01-31"

# =====================================================
# 🔥 BLOQUEANTES ACTUALES
# =====================================================
BLOCKERS = [
    "Expandir cobertura de tests para Native SDKs",
]


# =====================================================
# 📊 FUNCIONES DE UTILIDAD
# =====================================================
def get_version() -> str:
    """Retorna la versión actual del sistema."""
    return __version__


def get_version_info() -> Dict[str, str]:
    """Retorna información completa de la versión actual."""
    return {
        "version": __version__,
        "name": __version_name__,
        "date": __release_date__,
        "status": __status__,
    }


def get_full_version_string() -> str:
    """Retorna string completo de versión para logs."""
    return f"Casino V2 v{__version__} ({__version_name__}) - {__status__}"


def get_changelog(version: str = None) -> Dict:
    """
    Retorna el changelog de una versión específica o todas.

    Args:
        version: Versión específica (ej: "1.7.1") o None para todas

    Returns:
        Dict con información del changelog
    """
    if version:
        return CHANGELOG.get(version, {})
    return CHANGELOG


def get_next_version_info() -> Dict[str, str]:
    """Retorna información de la próxima versión planeada."""
    return {
        "version": NEXT_VERSION,
        "name": NEXT_VERSION_NAME,
        "eta": NEXT_VERSION_ETA,
        "blockers": BLOCKERS,
    }


def print_version_banner():
    """Imprime banner con información de versión."""
    print("=" * 60)
    print(f"🎰 CASINO V2 - v{__version__}")
    print(f"📌 {__version_name__}")
    print(f"📅 Released: {__release_date__}")
    print(f"🔖 Status: {__status__.upper()}")
    print("=" * 60)


# =====================================================
# 🧪 TESTING
# =====================================================
if __name__ == "__main__":
    print_version_banner()
    print("\n📊 Version Info:")
    info = get_version_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\n🔜 Next Version:")
    next_info = get_next_version_info()
    for key, value in next_info.items():
        if key == "blockers":
            print(f"  {key}:")
            for blocker in value:
                print(f"    - {blocker}")
        else:
            print(f"  {key}: {value}")
