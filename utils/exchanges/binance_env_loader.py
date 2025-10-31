"""
Binance Environment Loader
Loads API credentials and configuration from environment variables for Binance exchange.
"""

import logging
import os
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

logger = logging.getLogger(__name__)


def load_binance_config() -> Dict[str, Any]:
    """
    Load Binance configuration from environment variables.

    Expected environment variables:
    - BINANCE_API_KEY: Your Binance API key
    - BINANCE_API_SECRET: Your Binance API secret

    Returns:
        Dict with Binance configuration
    """
    # Load .env file if available
    if DOTENV_AVAILABLE:
        # Try multiple possible .env locations
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),  # Project root
            os.path.join(os.getcwd(), ".env"),  # Current working directory
            ".env",  # Relative to current script
        ]

        env_loaded = False
        for env_path in possible_paths:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                logger.info("✅ Archivo .env cargado desde: %s", env_path)
                env_loaded = True
                break

        if not env_loaded:
            logger.warning("⚠️ Archivo .env no encontrado en ninguna ubicación buscada")

    config = {}

    # Load API credentials
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if api_key:
        config["api_key"] = api_key
        logger.info("✅ Binance API key loaded")
    else:
        logger.warning("⚠️ BINANCE_API_KEY not found in environment variables")

    if api_secret:
        config["api_secret"] = api_secret
        logger.info("✅ Binance API secret loaded")
    else:
        logger.warning("⚠️ BINANCE_API_SECRET not found in environment variables")

    # Load additional configuration
    config.update(
        {
            "base_url": os.getenv("BINANCE_BASE_URL", "https://testnet.binancefuture.com"),
            "timeout": int(os.getenv("BINANCE_TIMEOUT", "30000")),  # 30 seconds
            "testnet": True,  # Always testnet for safety
        }
    )

    return config


def validate_binance_config(config: Dict[str, Any]) -> bool:
    """
    Validate Binance configuration.

    Args:
        config: Configuration dictionary

    Returns:
        True if configuration is valid for trading
    """
    required_fields = ["api_key", "api_secret"]

    for field in required_fields:
        if not config.get(field):
            logger.error(f"❌ Missing required Binance config: {field}")
            return False

    logger.info("✅ Binance configuration validated")
    return True


def get_binance_credentials() -> Optional[Dict[str, str]]:
    """
    Get Binance API credentials in the format expected by CCXT.

    Returns:
        Dict with 'apiKey' and 'secret', or None if not configured
    """
    config = load_binance_config()

    if not validate_binance_config(config):
        return None

    return {
        "apiKey": config["api_key"],
        "secret": config["api_secret"],
    }


if __name__ == "__main__":
    # Test the loader
    print("🔍 Testing Binance environment loader...")

    config = load_binance_config()
    print(f"Config loaded: {bool(config)}")

    if config:
        print(f"API Key configured: {bool(config.get('api_key'))}")
        print(f"API Secret configured: {bool(config.get('api_secret'))}")
        print(f"Testnet: {config.get('testnet', False)}")

        is_valid = validate_binance_config(config)
        print(f"Configuration valid: {is_valid}")

        credentials = get_binance_credentials()
        if credentials:
            print("✅ Credentials ready for CCXT")
        else:
            print("❌ Credentials not available")
    else:
        print("❌ No configuration found")
