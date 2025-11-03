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
__version__ = "1.8"
__version_name__ = "TBD"  # Pending definition
__release_date__ = "2025-11-02"
__status__: Literal["stable", "beta", "alpha", "dev"] = "dev"

# =====================================================
# 📝 CHANGELOG RESUMIDO
# =====================================================
CHANGELOG = {
    "1.8": {
        "name": "TBD",
        "date": "2025-11-02",
        "highlights": [
            "TBD - Pending definition",
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
    "1.6": {
        "name": "WebSocket Integration",
        "date": "2025-09-30",
        "highlights": ["WebSocket para datos en tiempo real", "TableCCXTPro implementado", "Mejoras en live trading"],
    },
}

# =====================================================
# 🎯 PRÓXIMA VERSIÓN
# =====================================================
NEXT_VERSION = "1.8"
NEXT_VERSION_NAME = "Multi-Asset Expansion"
NEXT_VERSION_ETA = "2025-12-31"

# =====================================================
# 🔥 BLOQUEANTES ACTUALES
# =====================================================
BLOCKERS = [
    "Validar Binance Futures Testnet (v1.7 - CRÍTICO)",
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
