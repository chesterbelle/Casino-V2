"""
Testing Data Source - Casino V2

Provides real-time data from an exchange for demo/live trading.
Delegates all order execution and state management to the Croupier.
"""

import asyncio
import logging
import time
from typing import Dict, Optional

from croupier.croupier import Croupier

from .base import Candle, DataSource


def timeframe_to_seconds(tf: str) -> int:
    """Convierte un timeframe string (e.g., '1m', '5m', '1h') a segundos."""
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 3600
    if tf.endswith("d"):
        return int(tf[:-1]) * 86400
    raise ValueError(f"Timeframe no soportado: {tf}")


logger = logging.getLogger(__name__)


class TestingDataSource(DataSource):
    """
    Data source for demo trading with real market prices.
    This class is a thin wrapper that provides candle data and delegates
    all execution logic to the Croupier.
    """

    def __init__(
        self,
        croupier: Croupier,
        symbol: str,
        timeframe: str,
        poll_interval: float = 5.0,
    ):
        """
        Initializes the TestingDataSource.

        Args:
            croupier: The Croupier instance, which manages state and execution.
            symbol: Trading symbol (e.g., "BTC/USD").
            timeframe: Candle interval (e.g., "5m", "1h").
            poll_interval: Seconds to wait between candle polls.
        """
        self.croupier = croupier
        # The adapter and connector are accessed through the Croupier
        self.adapter = croupier.exchange_adapter
        self.connector = self.adapter.connector

        self.symbol = symbol
        self.timeframe = timeframe
        self.poll_interval = poll_interval

        self._last_candle_timestamp = 0
        # El balance inicial se obtiene directamente del Croupier, que ya está inicializado.
        self.initial_balance = self.croupier.get_balance()

        logger.info(
            f"📊 TestingDataSource initialized | "
            f"Symbol: {symbol} | "
            f"Timeframe: {timeframe} | "
            f"Poll: {poll_interval}s"
        )

    async def connect(self) -> None:
        """Método de conexión requerido por la clase base. No realiza ninguna acción."""
        pass

    async def disconnect(self) -> None:
        """Método de desconexión requerido por la clase base. No realiza ninguna acción."""
        pass

    async def next_candle(self) -> Optional[Candle]:
        """
        Gets the next candle from the exchange and enriches it with portfolio data from the Croupier.
        """
        while True:
            try:
                candle_data = await self.adapter.next_candle()
                logger.debug(
                    "📥 Raw candle received | data=%s",
                    {
                        "timestamp": candle_data.get("timestamp") if isinstance(candle_data, dict) else None,
                        "open": candle_data.get("open") if isinstance(candle_data, dict) else None,
                        "high": candle_data.get("high") if isinstance(candle_data, dict) else None,
                        "low": candle_data.get("low") if isinstance(candle_data, dict) else None,
                        "close": candle_data.get("close") if isinstance(candle_data, dict) else None,
                        "volume": candle_data.get("volume") if isinstance(candle_data, dict) else None,
                        "type": type(candle_data).__name__,
                    },
                )
                if not candle_data:
                    logger.warning("⚠️ No candles received, retrying...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                if not isinstance(candle_data, dict):
                    logger.error(f"❌ Invalid candle payload type: {type(candle_data)} | value={candle_data}")
                    await asyncio.sleep(self.poll_interval)
                    continue

                required_fields = ["timestamp", "open", "high", "low", "close", "volume"]
                missing_fields = [field for field in required_fields if field not in candle_data]
                if missing_fields:
                    logger.error(f"❌ Candle missing fields: {missing_fields} | payload={candle_data}")
                    await asyncio.sleep(self.poll_interval)
                    continue

                timestamp = int(candle_data["timestamp"])
                if timestamp <= self._last_candle_timestamp:
                    logger.debug(f"⏳ Same candle (ts={timestamp}), waiting for new one...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                self._last_candle_timestamp = timestamp
                logger.info(f"✅ New candle received | ts={timestamp}")

                # The Croupier is now responsible for checking for closed positions.
                # We just get the latest state from it.
                balance = self.croupier.get_balance()
                equity = self.croupier.get_equity()

                candle = Candle(
                    timestamp=timestamp,
                    open=float(candle_data["open"]),
                    high=float(candle_data["high"]),
                    low=float(candle_data["low"]),
                    close=float(candle_data["close"]),
                    volume=float(candle_data["volume"]),
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    equity=equity,
                    balance=balance,
                    unrealized_pnl=equity - balance,
                )

                # Esperar hasta la siguiente vela para simular tiempo real
                timeframe_seconds = timeframe_to_seconds(self.timeframe)
                now = time.time()  # Tiempo actual en segundos desde epoch
                next_candle_start = (timestamp / 1000) + timeframe_seconds  # timestamp está en milisegundos
                wait_time = next_candle_start - now

                if wait_time > 0:
                    logger.info(f"⏳ Waiting {wait_time:.1f}s for next candle...")
                    await asyncio.sleep(wait_time)

                return candle

            except Exception as e:
                logger.error(f"❌ Error fetching candle: {e}")
                await asyncio.sleep(self.poll_interval)
                return None

    async def execute_order(self, order: Dict) -> Dict:
        """
        Adjunta el campo candle_close a la orden antes de delegarla al Croupier.
        """
        # Usar el último precio de cierre conocido si no está presente
        if "candle_close" not in order or not order.get("candle_close"):
            # Buscar el último precio de cierre de la vela actual
            # Si hay una vela procesada, usar su close
            if hasattr(self, "_last_candle_timestamp") and self._last_candle_timestamp:
                # Intentar obtener el precio de cierre desde el adapter
                try:
                    candle = await self.adapter.get_candle_by_timestamp(self._last_candle_timestamp)
                    if candle and isinstance(candle, dict) and "close" in candle:
                        order["candle_close"] = float(candle["close"])
                except Exception:
                    pass
        try:
            result = await self.croupier.execute_order(order)
            return result
        except Exception as e:
            logger.error(f"❌ Order execution failed at DataSource level: {e}")
            return {
                "status": "error",
                "reason": str(e),
                "order": order,
            }

    def get_balance(self) -> float:
        """Gets current balance from the Croupier."""
        return self.croupier.get_balance()

    def get_equity(self) -> float:
        """Gets current equity from the Croupier."""
        return self.croupier.get_equity()

    async def get_stats(self) -> dict:
        """
        Gets trading statistics directly from the Croupier.
        """
        try:
            # The Croupier is the single source of truth for portfolio state.
            stats = self.croupier.get_portfolio_state()
            # Normalize keys expected by main.run_demo() printer
            final_balance = float(stats.get("balance", 0.0))
            final_equity = float(stats.get("equity", 0.0))
            open_positions_count = int(stats.get("open_positions_count", 0))
            wins = int(stats.get("wins", 0))
            losses = int(stats.get("losses", 0))

            normalized = {
                "initial_balance": float(self.initial_balance),
                "final_balance": final_balance,
                "final_equity": final_equity,
                "total_pnl": final_balance - float(self.initial_balance),
                "total_trades": stats.get("total_trades", 0),
                "wins": wins,
                "losses": losses,
                "win_rate": wins / (wins + losses) if (wins + losses) > 0 else 0,
                "open_positions": open_positions_count,
            }
            return normalized
        except Exception as e:
            logger.error(f"❌ Error getting stats from Croupier: {e}")
            return {
                "initial_balance": self.initial_balance,
                "final_balance": 0,
                "final_equity": 0,
                "total_pnl": 0,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "open_positions": 0,
            }
