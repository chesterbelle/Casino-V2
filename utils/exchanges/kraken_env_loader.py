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


def load_kraken_config() -> Dict[str, str]:
    """
    Load Kraken configuration from environment variables.

    Expected environment variables:
    - KRAKEN_FUTURES_API_KEY: Your Kraken API key
    - KRAKEN_FUTURES_API_SECRET: Your Kraken API secret

    Returns:
        Dict with Kraken configuration
    """
    logger = logging.getLogger("KrakenEnvLoader")

    # Load .env file if available
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info("Archivo .env encontrado en la raíz del proyecto: %s", env_path)
    else:
        logger.warning("Archivo .env NO encontrado en: %s", env_path)

    # Load API credentials
    api_key = os.getenv("KRAKEN_FUTURES_API_KEY")
    api_secret = os.getenv("KRAKEN_FUTURES_API_SECRET")

    if api_key:
        logger.info("✅ Kraken API key loaded")
    else:
        logger.warning("⚠️ KRAKEN_FUTURES_API_KEY not found in environment variables")

    if api_secret:
        logger.info("✅ Kraken API secret loaded")
    else:
        logger.warning("⚠️ KRAKEN_FUTURES_API_SECRET not found in environment variables")

    # Load additional configuration
    config = {
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": os.getenv("KRAKEN_FUTURES_BASE_URL", DEFAULT_BASE_URL),
        "charts_url": os.getenv("KRAKEN_FUTURES_CHARTS_URL", DEFAULT_CHARTS_URL),
        "testnet": True,  # Always demo for safety
    }

    return config


def validate_kraken_config(config: Dict[str, str]) -> bool:
    """
    Validate Kraken configuration.

    Args:
        config: Configuration dictionary

    Returns:
        True if configuration is valid for trading
    """
    logger = logging.getLogger("KrakenEnvLoader")

    required_fields = ["api_key", "api_secret"]

    for field in required_fields:
        if not config.get(field):
            logger.error(f"❌ Missing required Kraken config: {field}")
            return False

    logger.info("✅ Kraken configuration validated")
    return True


def get_kraken_credentials() -> Dict[str, str] | None:
    """
    Get Kraken API credentials in the format expected by CCXT.

    Returns:
        Dict with 'apiKey' and 'secret', or None if not configured
    """
    config = load_kraken_config()

    if not validate_kraken_config(config):
        return None

    return {
        "apiKey": config["api_key"],
        "secret": config["api_secret"],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    creds = load_kraken_config()
    logger = logging.getLogger("KrakenEnvLoader")
    logger.info("\nResultado Kraken Futures:")
    for key, value in creds.items():
        logger.info(f"  {key}: {value}")
