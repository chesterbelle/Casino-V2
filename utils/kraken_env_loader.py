"""
Environment loader for Kraken Futures (demo or production).
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://demo-futures.kraken.com/derivatives/api/"
DEFAULT_CHARTS_URL = "https://demo-futures.kraken.com/api/charts/v1/"


def load_kraken_credentials(test_connection: bool = False) -> Dict[str, str]:
    """
    Carga credenciales y URLs para Kraken Futures desde `.env` o `config.py`.
    """
    logger = logging.getLogger("KrakenEnvLoader")

    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info("Archivo .env encontrado en la raíz del proyecto: %s", env_path)
    else:
        logger.warning("No se encontró archivo .env en la raíz del proyecto.")

    import config  # noqa: WPS433  # deferred import to honour runtime config

    api_key = os.getenv("KRAKEN_FUTURES_API_KEY") or getattr(config, "KRAKEN_FUTURES_API_KEY", None)
    api_secret = os.getenv("KRAKEN_FUTURES_API_SECRET") or getattr(config, "KRAKEN_FUTURES_API_SECRET", None)
    base_url = (os.getenv("KRAKEN_FUTURES_BASE_URL") or getattr(config, "KRAKEN_FUTURES_BASE_URL", DEFAULT_BASE_URL)).rstrip("/") + "/"
    charts_url = (os.getenv("KRAKEN_FUTURES_CHARTS_URL") or getattr(config, "KRAKEN_FUTURES_CHARTS_URL", DEFAULT_CHARTS_URL)).rstrip("/") + "/"

    if not api_key or not api_secret:
        logger.warning("Claves de Kraken Futures incompletas; se deshabilitan llamadas privadas.")

    connected = False
    if test_connection and api_key and api_secret:
        from utils.kraken_futures_client import KrakenFuturesClient  # local import to avoid circulars

        try:
            client = KrakenFuturesClient(
                api_key=api_key,
                api_secret=api_secret,
                base_url=base_url,
                charts_url=charts_url,
            )
            client.get_accounts()
            connected = True
            logger.info("Kraken Futures API responde correctamente (accounts).")
        except Exception as exc:
            logger.error("Error validando credenciales de Kraken Futures: %s", exc)

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": base_url,
        "charts_url": charts_url,
        "connected": connected,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    creds = load_kraken_credentials(test_connection=True)
    print("\nResultado Kraken Futures:")
    for key, value in creds.items():
        print(f"  {key}: {value}")
