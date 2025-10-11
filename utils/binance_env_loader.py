"""
====================================================
🔐 Binance Env Loader — Cargador y Validador de Claves API
====================================================

Rol:
----
• Carga las claves API desde `.env` o `config.py`.
• Valida la conexión con Binance (opcional).
• Devuelve un diccionario estándar con las claves
  para ser usado por TableRealtime o cualquier módulo.

====================================================
🧱 Ejemplo de uso:
------------------
from utils.binance_env_loader import load_binance_credentials

creds = load_binance_credentials(test_connection=True)
if creds["connected"]:
    print("✅ Conexión válida a Binance Testnet.")
else:
    print("⚠️ Sin conexión. Modo simulado.")

====================================================
🔧 Configuración esperada:
--------------------------
Archivo .env (en la raíz del repo):

    API_KEY=tu_api_key_testnet
    API_SECRET=tu_api_secret_testnet
    EXCHANGE=BINANCE_FUTURES_TESTNET

Opcionalmente puedes definir las mismas variables en config.py
"""

import os
import logging
from typing import Dict

from dotenv import load_dotenv

# Intentar importar la API de Binance si está instalada
try:
    from binance.client import Client
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False


def load_binance_credentials(test_connection: bool = False) -> Dict[str, str]:
    """
    Carga las credenciales API desde .env o config.py
    y valida la conexión si se solicita.

    Retorna:
    --------
    {
        "api_key": str | None,
        "api_secret": str | None,
        "exchange": str,
        "connected": bool
    }
    """
    logger = logging.getLogger("EnvLoader")

    # ============================================================
    # Cargar variables desde .env si existe
    # ============================================================
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"🧭 .env encontrado en: {env_path}")
    else:
        logger.warning("⚠️ No se encontró archivo .env en la raíz del proyecto.")

    # ============================================================
    # Obtener claves desde entorno o config.py
    # ============================================================
    import config  # importa dinámicamente tu config.py
    api_key = os.getenv("API_KEY") or getattr(config, "API_KEY", None)
    api_secret = os.getenv("API_SECRET") or getattr(config, "API_SECRET", None)
    exchange = os.getenv("EXCHANGE") or getattr(config, "EXCHANGE", "SIMULATION")

    connected = False
    if not BINANCE_AVAILABLE:
        logger.warning("🐍 python-binance no instalado. Modo simulado activado.")
    elif not api_key or not api_secret:
        logger.warning("🔑 Claves API no configuradas. Modo simulado activado.")
    elif test_connection:
        # ============================================================
        # Probar conexión con Binance Futures Testnet (opcional)
        # ============================================================
        try:
            client = Client(api_key, api_secret, testnet="TESTNET" in exchange.upper())
            account_info = client.futures_account()
            if "totalWalletBalance" in account_info:
                connected = True
                logger.info("✅ Conexión válida con Binance API.")
            else:
                logger.warning("⚠️ No se obtuvo balance. La conexión puede ser parcial.")
        except Exception as e:
            logger.error(f"❌ Error probando conexión con Binance: {e}")
    else:
        logger.info("🔌 Claves cargadas (sin test de conexión).")

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "exchange": exchange,
        "connected": connected
    }


# ============================================================
# Ejecución directa (para test rápido)
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    creds = load_binance_credentials(test_connection=True)
    print("\n🔍 Resultado:")
    for k, v in creds.items():
        print(f"  {k}: {v}")

