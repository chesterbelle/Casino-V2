"""
Debug Kraken with correct URLs according to official documentation
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
logger = logging.getLogger("KrakenCorrectURLDebug")


async def debug_kraken_correct_urls():
    """Debug Kraken with correct URLs from official docs."""
    logger.info("🔍 Debugging Kraken with CORRECT URLs...")
    
    try:
        # Load config from environment
        config = load_kraken_config()
        logger.info(f"📋 Config loaded: {config}")
        
        # Test correct Kraken configurations according to docs
        configs_to_test = [
            {
                "name": "Kraken Futures Demo (CORRECT)",
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
                    "options": {
                        "defaultType": "future"
                    }
                }
            },
            {
                "name": "Kraken Futures Production (CORRECT)",
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
                    "options": {
                        "defaultType": "future"
                    }
                }
            },
            {
                "name": "Kraken Spot API (Default)",
                "config": {
                    "apiKey": config["api_key"],
                    "secret": config["api_secret"],
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "spot"
                    }
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
                logger.info(f"🔧 Default type: {exchange.options.get('defaultType', 'N/A')}")
                
                # Test server time - try different endpoints
                endpoints_to_try = [
                    "/api/v3/time",  # New futures API
                    "/0/public/Time",  # Old spot API
                    "/derivatives/api/v3/time"  # Alternative futures endpoint
                ]
                
                for endpoint in endpoints_to_try:
                    try:
                        url = f"{exchange.urls['api']['public']}{endpoint}"
                        logger.info(f"🔍 Trying endpoint: {url}")
                        
                        # Direct request to test endpoint
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    logger.info(f"✅ Server time from {endpoint}: {data}")
                                    break
                                else:
                                    logger.warning(f"⚠️ {endpoint} returned {response.status}")
                    except Exception as e:
                        logger.debug(f"❌ {endpoint} failed: {e}")
                
                # Test balance (private endpoint)
                try:
                    balance = await exchange.fetch_balance()
                    logger.info(f"✅ Balance fetched successfully")
                    logger.info(f"💰 Balance info: {type(balance)}")
                    
                    # Show some balance info
                    if 'info' in balance:
                        logger.info(f"📊 Info available: {bool(balance['info'])}")
                    if 'total' in balance:
                        logger.info(f"💰 Total currencies: {len(balance['total'])}")
                        
                except Exception as e:
                    logger.error(f"❌ Balance failed: {e}")
                    
                    # Check if it's the specific error we're seeing
                    if "EAPI:Invalid key" in str(e):
                        logger.error(f"🚨 This is the invalid key error!")
                        logger.error(f"🔍 This means keys are valid but for different endpoint")
                        
                await exchange.close()
                
            except Exception as e:
                logger.error(f"❌ {test_config['name']} failed: {e}")
                
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")


if __name__ == "__main__":
    asyncio.run(debug_kraken_correct_urls())
