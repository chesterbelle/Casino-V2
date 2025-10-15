"""
====================================================
🔐 Binance Env Loader — Cargador y Validador de Claves API
====================================================

Rol:
----
• Carga las claves API de Binance desde `.env` o `config.py`.
• Valida la conexión con Binance Futures Testnet (opcional).
• Devuelve un diccionario estándar con las claves y URLs.

====================================================
🔧 Configuración esperada:
--------------------------
Archivo .env (en la raíz del repo):

    BINANCE_API_KEY=tu_api_key_testnet
    BINANCE_API_SECRET=tu_api_secret_testnet

Opcionalmente puedes definir las mismas variables en config.py
"""

import os
import logging
from typing import Dict

from dotenv import load_dotenv

from utils.binance_futures_client import BinanceFuturesClient, BinanceFuturesAPIError
import config

def load_binance_credentials(test_connection: bool = False) -> Dict[str, str]:
    """
    Carga las credenciales de Binance API desde .env o config.py
    y valida la conexión si se solicita.

    Retorna:
    --------
    {
        "api_key": str | None,
        "api_secret": str | None,
        "base_url": str,
        "connected": bool
    }
    """
    logger = logging.getLogger("BinanceEnvLoader")

    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)

    api_key = os.getenv("BINANCE_API_KEY") or getattr(config, "BINANCE_API_KEY", None)
    api_secret = os.getenv("BINANCE_API_SECRET") or getattr(config, "BINANCE_API_SECRET", None)
    base_url = getattr(config, "BINANCE_BASE_URL", "https://testnet.binancefuture.com")

    connected = False
    if not api_key or not api_secret:
        logger.warning("🔑 Claves API de Binance no configuradas. No se puede conectar.")
    elif test_connection:
        try:
            client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret, base_url=base_url)
            client.get_account_balance()
            connected = True
            logger.info("✅ Conexión válida con Binance Futures Testnet API.")
        except BinanceFuturesAPIError as e:
            logger.error(f"❌ Error probando conexión con Binance: {e}")
    else:
        logger.info("🔌 Claves de Binance cargadas (sin test de conexión).")

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": base_url,
        "connected": connected
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    creds = load_binance_credentials(test_connection=True)
    print("\n🔍 Resultado:")
    for k, v in creds.items():
        print(f"  {k}: {v}")