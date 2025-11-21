"""
Hyperliquid Environment Loader
Loads API credentials and configuration from environment variables for Hyperliquid exchange.
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


def load_hyperliquid_config() -> Dict[str, Any]:
    """
    Load Hyperliquid configuration from environment variables.

    Expected environment variables:
    - HYPERLIQUID_API_KEY: Your Hyperliquid API key
    - HYPERLIQUID_API_SECRET: Your Hyperliquid API secret
    - HYPERLIQUID_VAULT_ADDRESS: (Optional) Vault address for vault trading

    Returns:
        Dict with Hyperliquid configuration
    """
    # Load .env file if available
    if DOTENV_AVAILABLE:
        # Buscar .env en la raíz del proyecto (2 niveles arriba de utils/exchanges/)
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info("Archivo .env encontrado en la raíz del proyecto: %s", env_path)

    config = {}

    # Load API credentials
    api_key = os.getenv("HYPERLIQUID_API_KEY")
    api_secret = os.getenv("HYPERLIQUID_API_SECRET")
    vault_address = os.getenv("HYPERLIQUID_VAULT_ADDRESS")

    if api_key:
        config["api_key"] = api_key
        logger.info("✅ Hyperliquid API key loaded")
    else:
        logger.warning("⚠️ HYPERLIQUID_API_KEY not found in environment variables")

    if api_secret:
        config["api_secret"] = api_secret
        logger.info("✅ Hyperliquid API secret loaded")
    else:
        logger.warning("⚠️ HYPERLIQUID_API_SECRET not found in environment variables")

    if vault_address:
        config["vault_address"] = vault_address
        logger.info("✅ Hyperliquid vault address loaded")
    else:
        logger.info("ℹ️ No vault address configured (using main account)")

    # Determine entorno (mainnet/testnet)
    raw_testnet = os.getenv("HYPERLIQUID_TESTNET")
    testnet_flag = None if raw_testnet is None else raw_testnet.lower() == "true"

    # Defaults dependen del flag (si está definido) o mainnet por defecto
    default_base_url = "https://api.hyperliquid-testnet.xyz" if testnet_flag is True else "https://api.hyperliquid.xyz"
    default_ws_url = "wss://api.hyperliquid-testnet.xyz/ws" if testnet_flag is True else "wss://api.hyperliquid.xyz/ws"

    env_base_url = os.getenv("HYPERLIQUID_BASE_URL")
    env_ws_url = os.getenv("HYPERLIQUID_WS_URL")
    test_base_url = os.getenv("HYPERLIQUID_TEST_BASE_URL", "https://api.hyperliquid-testnet.xyz")
    test_ws_url = os.getenv("HYPERLIQUID_TEST_WS_URL", "wss://api.hyperliquid-testnet.xyz/ws")

    # Load additional configuration
    config.update(
        {
            "base_url": env_base_url or default_base_url,
            "ws_url": env_ws_url or default_ws_url,
            "testnet": testnet_flag,
            "test_base_url": test_base_url,
            "test_ws_url": test_ws_url,
            "timeout": int(os.getenv("HYPERLIQUID_TIMEOUT", "30000")),  # 30 seconds
            "_testnet_overridden": raw_testnet is not None,
            "_base_url_overridden": env_base_url is not None,
            "_ws_url_overridden": env_ws_url is not None,
        }
    )

    return config


def validate_hyperliquid_config(config: Dict[str, Any]) -> bool:
    """
    Validate Hyperliquid configuration.

    Args:
        config: Configuration dictionary

    Returns:
        True if configuration is valid for trading
    """
    required_fields = ["api_key", "api_secret"]

    for field in required_fields:
        if not config.get(field):
            logger.error(f"❌ Missing required Hyperliquid config: {field}")
            return False

    logger.info("✅ Hyperliquid configuration validated")
    return True


def get_hyperliquid_credentials() -> Optional[Dict[str, str]]:
    """
    Get Hyperliquid API credentials in the format expected by CCXT.

    Hyperliquid uses wallet-based authentication:
    - walletAddress: Ethereum wallet address (0x...)
    - privateKey: Private key for signing transactions (0x...)

    Returns:
        Dict with 'walletAddress' and 'privateKey', or None if not configured
    """
    config = load_hyperliquid_config()

    if not validate_hyperliquid_config(config):
        return None

    return {
        "walletAddress": config["api_key"],  # API_KEY es la wallet address
        "privateKey": config["api_secret"],  # API_SECRET es la private key
    }


if __name__ == "__main__":
    # Test the loader
    logger.info("🔍 Testing Hyperliquid environment loader...")

    config = load_hyperliquid_config()
    logger.info(f"Config loaded: {bool(config)}")

    if config:
        logger.info(f"API Key configured: {bool(config.get('api_key'))}")
        logger.info(f"API Secret configured: {bool(config.get('api_secret'))}")
        logger.info(f"Vault configured: {bool(config.get('vault_address'))}")
        logger.info(f"Testnet: {config.get('testnet', False)}")

        is_valid = validate_hyperliquid_config(config)
        logger.info(f"Configuration valid: {is_valid}")

        credentials = get_hyperliquid_credentials()
        if credentials:
            logger.info("✅ Credentials ready for CCXT")
        else:
            logger.error("❌ Credentials not available")
    else:
        logger.error("❌ No configuration found")
