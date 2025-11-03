"""
Debug exchange symbols and configurations
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tables.table_ccxt_pro import TableCCXTPro

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("DebugSymbols")


async def debug_kraken():
    """Debug Kraken configuration."""
    logger.info("🔍 Debugging Kraken...")
    
    try:
        # Try without sandbox first
        table = TableCCXTPro(
            exchange_id="kraken",
            symbols=["BTC/USDT"],
            timeframe="1m",
            testnet=False  # Try production first
        )
        
        await table.connect()
        
        # Check markets
        logger.info("📊 Loading markets...")
        markets = await table.exchange.load_markets()
        
        # Find BTC markets
        btc_markets = [symbol for symbol in markets.keys() if 'BTC' in symbol and 'USD' in symbol]
        logger.info(f"💰 BTC/USD markets found: {btc_markets[:10]}")  # Show first 10
        
        # Check if we can get ticker for BTC/USDT
        try:
            ticker = await table.exchange.fetch_ticker('BTC/USDT')
            logger.info(f"✅ BTC/USDT ticker: ${ticker['last']:,.2f}")
        except Exception as e:
            logger.info(f"❌ BTC/USDT not available: {e}")
            
            # Try alternative symbols
            for symbol in ['BTC/USD', 'XBT/USDT', 'XBT/USD']:
                try:
                    ticker = await table.exchange.fetch_ticker(symbol)
                    logger.info(f"✅ {symbol} ticker: ${ticker['last']:,.2f}")
                    break
                except:
                    logger.info(f"❌ {symbol} not available")
        
        await table.close()
        
    except Exception as e:
        logger.error(f"❌ Kraken debug failed: {e}")


async def debug_hyperliquid():
    """Debug Hyperliquid symbols."""
    logger.info("🔍 Debugging Hyperliquid...")
    
    try:
        table = TableCCXTPro(
            exchange_id="hyperliquid",
            symbols=["BTC/USDT"],
            timeframe="1m",
            testnet=True
        )
        
        await table.connect()
        
        # Check markets
        logger.info("📊 Loading markets...")
        markets = await table.exchange.load_markets()
        
        # Find BTC markets
        btc_markets = [symbol for symbol in markets.keys() if 'BTC' in symbol]
        logger.info(f"💰 BTC markets found: {btc_markets[:10]}")  # Show first 10
        
        # Try different BTC symbols
        for symbol in btc_markets[:5]:  # Try first 5 BTC markets
            try:
                ticker = await table.exchange.fetch_ticker(symbol)
                logger.info(f"✅ {symbol} ticker: ${ticker['last']:,.2f}")
            except Exception as e:
                logger.info(f"❌ {symbol} failed: {e}")
        
        await table.close()
        
    except Exception as e:
        logger.error(f"❌ Hyperliquid debug failed: {e}")


async def main():
    """Main debug runner."""
    await debug_kraken()
    await asyncio.sleep(2)
    await debug_hyperliquid()


if __name__ == "__main__":
    logger.info("--- Starting Exchange Symbol Debug ---")
    asyncio.run(main())
    logger.info("--- Debug Complete ---")
