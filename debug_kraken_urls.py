"""
Debug Kraken URLs and configuration
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt.async_support as ccxt_async
from utils.exchanges.kraken_env_loader import load_kraken_config

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("KrakenURLDebug")


async def debug_kraken_urls():
    """Debug Kraken URLs and authentication."""
    logger.info("🔍 Debugging Kraken URLs and configuration...")
    
    try:
        # Load config from environment
        config = load_kraken_config()
        logger.info(f"📋 Config loaded: {config}")
        
        # Test different Kraken configurations
        configs_to_test = [
            {
                "name": "Kraken (Default)",
                "config": {
                    "apiKey": config["api_key"],
                    "secret": config["api_secret"],
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"}
                }
            },
            {
                "name": "Kraken (Demo URLs)",
                "config": {
                    "apiKey": config["api_key"],
                    "secret": config["api_secret"],
                    "enableRateLimit": True,
                    "urls": {
                        "api": {
                            "public": "https://demo-futures.kraken.com/derivatives/api/v3/",
                            "private": "https://demo-futures.kraken.com/derivatives/api/v3/"
                        }
                    },
                    "options": {"defaultType": "future"}
                }
            },
            {
                "name": "Kraken (Production URLs)",
                "config": {
                    "apiKey": config["api_key"],
                    "secret": config["api_secret"],
                    "enableRateLimit": True,
                    "urls": {
                        "api": {
                            "public": "https://futures.kraken.com/derivatives/api/v3/",
                            "private": "https://futures.kraken.com/derivatives/api/v3/"
                        }
                    },
                    "options": {"defaultType": "future"}
                }
            }
        ]
        
        for test_config in configs_to_test:
            logger.info(f"\n🧪 Testing: {test_config['name']}")
            
            try:
                # Create exchange instance
                exchange = ccxt_async.kraken(test_config["config"])
                
                # Show URLs being used
                logger.info(f"📡 Public URL: {exchange.urls.get('api', {}).get('public', 'N/A')}")
                logger.info(f"🔒 Private URL: {exchange.urls.get('api', {}).get('private', 'N/A')}")
                
                # Test server time (public endpoint)
                try:
                    server_time = await exchange.fetch_time()
                    logger.info(f"✅ Server time: {server_time}")
                except Exception as e:
                    logger.error(f"❌ Server time failed: {e}")
                    continue
                
                # Test balance (private endpoint)
                try:
                    balance = await exchange.fetch_balance()
                    logger.info(f"✅ Balance fetched successfully")
                    logger.info(f"💰 Balance keys: {list(balance.keys())}")
                except Exception as e:
                    logger.error(f"❌ Balance failed: {e}")
                    
                    # Check if it's the specific error we're seeing
                    if "EAPI:Invalid key" in str(e):
                        logger.error(f"🚨 This is the invalid key error!")
                        
                await exchange.close()
                
            except Exception as e:
                logger.error(f"❌ {test_config['name']} failed: {e}")
                
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")


if __name__ == "__main__":
    asyncio.run(debug_kraken_urls())
