"""
Hyperliquid Environment Loader
Loads API credentials and configuration from environment variables for Hyperliquid exchange.
"""

import os
import logging
from typing import Optional, Dict, Any

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
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info("Archivo .env encontrado en la raíz del proyecto: %s", env_path)

    config = {}

    # Load API credentials
    api_key = os.getenv('HYPERLIQUID_API_KEY')
    api_secret = os.getenv('HYPERLIQUID_API_SECRET')
    vault_address = os.getenv('HYPERLIQUID_VAULT_ADDRESS')

    if api_key:
        config['api_key'] = api_key
        logger.info("✅ Hyperliquid API key loaded")
    else:
        logger.warning("⚠️ HYPERLIQUID_API_KEY not found in environment variables")

    if api_secret:
        config['api_secret'] = api_secret
        logger.info("✅ Hyperliquid API secret loaded")
    else:
        logger.warning("⚠️ HYPERLIQUID_API_SECRET not found in environment variables")

    if vault_address:
        config['vault_address'] = vault_address
        logger.info("✅ Hyperliquid vault address loaded")
    else:
        logger.info("ℹ️ No vault address configured (using main account)")

    # Load additional configuration
    config.update({
        'base_url': os.getenv('HYPERLIQUID_BASE_URL', 'https://api.hyperliquid.xyz'),
        'ws_url': os.getenv('HYPERLIQUID_WS_URL', 'wss://api.hyperliquid.xyz/ws'),
        'testnet': os.getenv('HYPERLIQUID_TESTNET', 'false').lower() == 'true',
        'timeout': int(os.getenv('HYPERLIQUID_TIMEOUT', '30000')),  # 30 seconds
    })

    return config


def validate_hyperliquid_config(config: Dict[str, Any]) -> bool:
    """
    Validate Hyperliquid configuration.

    Args:
        config: Configuration dictionary

    Returns:
        True if configuration is valid for trading
    """
    required_fields = ['api_key', 'api_secret']

    for field in required_fields:
        if not config.get(field):
            logger.error(f"❌ Missing required Hyperliquid config: {field}")
            return False

    logger.info("✅ Hyperliquid configuration validated")
    return True


def get_hyperliquid_credentials() -> Optional[Dict[str, str]]:
    """
    Get Hyperliquid API credentials in the format expected by CCXT.

    Returns:
        Dict with 'apiKey' and 'secret', or None if not configured
    """
    config = load_hyperliquid_config()

    if not validate_hyperliquid_config(config):
        return None

    return {
        'apiKey': config['api_key'],
        'secret': config['api_secret'],
    }


if __name__ == '__main__':
    # Test the loader
    print("🔍 Testing Hyperliquid environment loader...")

    config = load_hyperliquid_config()
    print(f"Config loaded: {bool(config)}")

    if config:
        print(f"API Key configured: {bool(config.get('api_key'))}")
        print(f"API Secret configured: {bool(config.get('api_secret'))}")
        print(f"Vault configured: {bool(config.get('vault_address'))}")
        print(f"Testnet: {config.get('testnet', False)}")

        is_valid = validate_hyperliquid_config(config)
        print(f"Configuration valid: {is_valid}")

        credentials = get_hyperliquid_credentials()
        if credentials:
            print("✅ Credentials ready for CCXT")
        else:
            print("❌ Credentials not available")
    else:
        print("❌ No configuration found")