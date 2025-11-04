"""
Backtest Data Source - Casino V2

Provides historical data for backtesting strategies.
Simulates order execution with realistic slippage and fees.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from .base import Candle, DataSource

logger = logging.getLogger(__name__)


class BacktestDataSource(DataSource):
    """
    Data source for backtesting with historical data.

    Features:
    - Load from CSV, Parquet, or DataFrame
    - Simulate slippage and fees
    - Simulate TP/SL using high/low prices
    - Track balance and positions
    - Instant execution (no delays)

    Example:
        >>> source = BacktestDataSource.from_csv("BTC_1h.csv")
        >>> await source.connect()
        >>> candle = await source.next_candle()
        >>> result = await source.execute_order(order)
        >>> await source.disconnect()
    """

    def __init__(
        self,
        data: pd.DataFrame,
        initial_balance: float = 10000.0,
        fee_rate: float = 0.0006,  # 0.06% (Kraken taker)
        slippage_rate: float = 0.0001,  # 0.01%
    ):
        """
        Initialize backtest data source.

        Args:
            data: DataFrame with columns [timestamp, open, high, low, close, volume]
            initial_balance: Starting balance for simulation
            fee_rate: Trading fee rate (0.0006 = 0.06%)
            slippage_rate: Simulated slippage (0.0001 = 0.01%)
        """
        self.data = data.reset_index(drop=True)
        self.index = 0
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

        # Position tracking
        self.open_positions: List[Dict] = []
        self.closed_trades: List[Dict] = []

        # Metadata
        self.symbol = data.get("symbol", pd.Series(["BTC/USD"]))[0] if "symbol" in data.columns else "BTC/USD"
        self.timeframe = data.get("timeframe", pd.Series(["1h"]))[0] if "timeframe" in data.columns else "1h"

        self._connected = False

        logger.info(
            f"📊 BacktestDataSource initialized | "
            f"Symbol: {self.symbol} | "
            f"Timeframe: {self.timeframe} | "
            f"Candles: {len(self.data)} | "
            f"Balance: {initial_balance:.2f}"
        )

    @classmethod
    def from_csv(
        cls,
        filepath: str,
        initial_balance: float = 10000.0,
        normalize_symbol: bool = True,
        force_timeframe: str = None,
        **kwargs,
    ) -> "BacktestDataSource":
        """
        Load data from CSV file.

        CSV must have columns: timestamp, open, high, low, close, volume

        Args:
            filepath: Path to CSV file
            initial_balance: Starting balance
            normalize_symbol: If True, normalize stablecoins to USD for Gemini
                            memory compatibility (BTC/USDT → BTC/USD)
            force_timeframe: Override detected timeframe (e.g., "1m" for memory
                           compatibility even if file is 5m data)
            **kwargs: Additional arguments for BacktestDataSource

        Returns:
            BacktestDataSource instance

        Example:
            >>> # Auto-detect and normalize
            >>> source = BacktestDataSource.from_csv("data/BTCUSDT_5m.csv")
            >>> # Force timeframe for memory compatibility
            >>> source = BacktestDataSource.from_csv(
            ...     "data/BTCUSDT_5m.csv",
            ...     force_timeframe="1m"  # Pretend it's 1m for Gemini memory
            ... )

        Note:
            Symbol normalization helps match Gemini's memory which may have been
            trained on different stablecoin pairs. All USDT/USDC/BUSD pairs are
            normalized to USD (e.g., BTC/USDT → BTC/USD).

            Timeframe forcing is useful when you want to use 5m data but have
            Gemini memory trained on 1m data. The backtest will work but be aware
            that the actual timeframe differs from what Gemini "thinks" it is.
        """
        df = pd.read_csv(filepath)

        # Convert timestamp to int if it's a string (ISO format)
        if df["timestamp"].dtype == "object":
            df["timestamp"] = pd.to_datetime(df["timestamp"]).astype(int) // 10**6

        # Try to infer symbol and timeframe from filename
        # e.g., "BTCUSDT_5m__30d.csv" -> symbol="BTC/USDT", timeframe="5m"
        import re
        from pathlib import Path

        filename = Path(filepath).stem  # Get filename without extension

        # Try to extract timeframe from filename (e.g., "5m", "1h", "15m")
        detected_timeframe = None
        timeframe_match = re.search(r"_(\d+[mhd])", filename)
        if timeframe_match:
            detected_timeframe = timeframe_match.group(1)

        # Apply timeframe: force_timeframe > detected > column > default
        if "timeframe" not in df.columns:
            if force_timeframe:
                df["timeframe"] = force_timeframe
                if detected_timeframe and detected_timeframe != force_timeframe:
                    logger.warning(
                        f"⚠️ Timeframe forced: {detected_timeframe} → {force_timeframe} "
                        f"(for Gemini memory compatibility). "
                        f"Note: Actual data is {detected_timeframe} but Gemini will see {force_timeframe}"
                    )
            elif detected_timeframe:
                df["timeframe"] = detected_timeframe

        # Try to extract symbol from filename (e.g., "BTCUSDT" -> "BTC/USD")
        if "symbol" not in df.columns:
            symbol_match = re.match(r"([A-Z]+)(USDT|USDC|BUSD|USD)", filename)
            if symbol_match:
                base = symbol_match.group(1)
                quote = symbol_match.group(2)

                if normalize_symbol and quote in ["USDT", "USDC", "BUSD"]:
                    # IMPORTANT: Normalize stablecoins to match Gemini memory format
                    # Gemini memory uses Kraken format: BTC/USDC:USDC (with settle currency)
                    # This allows backtest data with USDT/USDC/BUSD to match Gemini's memory
                    # which may have been trained on Kraken futures data.
                    # Example: BTC/USDT → BTC/USDC:USDC (Kraken format)
                    normalized_quote = "USDC"  # Kraken uses USDC
                    df["symbol"] = f"{base}/{normalized_quote}:{normalized_quote}"
                    logger.info(
                        f"📝 Symbol normalized: {base}/{quote} → {base}/{normalized_quote}:{normalized_quote} "
                        f"(Kraken format for Gemini memory compatibility)"
                    )
                else:
                    df["symbol"] = f"{base}/{quote}"

        return cls(df, initial_balance, **kwargs)

    @classmethod
    def from_parquet(
        cls,
        filepath: str,
        initial_balance: float = 10000.0,
        **kwargs,
    ) -> "BacktestDataSource":
        """
        Load data from Parquet file (faster for large datasets).

        Args:
            filepath: Path to Parquet file
            initial_balance: Starting balance
            **kwargs: Additional arguments for BacktestDataSource

        Returns:
            BacktestDataSource instance

        Example:
            >>> source = BacktestDataSource.from_parquet("data/BTC_1h.parquet")
        """
        df = pd.read_parquet(filepath)
        return cls(df, initial_balance, **kwargs)

    async def connect(self) -> None:
        """Initialize backtest (validate data is loaded)."""
        if len(self.data) == 0:
            raise ValueError("No data loaded for backtest")

        self._connected = True
        logger.info("✅ Backtest data source connected")

    async def disconnect(self) -> None:
        """Close backtest and force-close any open positions."""
        # Force close all open positions at current market price
        if self.open_positions:
            logger.info(f"🔄 Force-closing {len(self.open_positions)} open position(s) at session end...")

            for position in self.open_positions[:]:  # Copy list to avoid modification during iteration
                # Close at current price (last candle close)
                current_price = self.data.iloc[self.index - 1]["close"] if self.index > 0 else position["entry_price"]

                # Calculate PnL
                if position["side"] == "buy":
                    pnl = (current_price - position["entry_price"]) * position["amount"]
                else:  # sell
                    pnl = (position["entry_price"] - current_price) * position["amount"]

                # Subtract fees
                exit_fee = position["amount"] * current_price * self.fee_rate
                net_pnl = pnl - exit_fee

                # Return margin (notional)
                self.balance += position["notional"]

                # Apply PnL
                self.balance += net_pnl

                # Record trade
                total_fee = position["fee"] + exit_fee
                self.closed_trades.append(
                    {
                        "entry_price": position["entry_price"],
                        "exit_price": current_price,
                        "side": position["side"],
                        "amount": position["amount"],
                        "pnl": net_pnl,
                        "total_fee": total_fee,
                        "result": "WIN" if net_pnl > 0 else "LOSS",
                        "exit_reason": "FORCE_CLOSE_END_SESSION",
                    }
                )

                logger.info(
                    f"{'🟢' if net_pnl > 0 else '🔴'} Position force-closed | "
                    f"END_SESSION @ {current_price:.2f} | "
                    f"PnL: {net_pnl:+.2f} | Balance: {self.balance:.2f}"
                )

                # Remove from open positions
                self.open_positions.remove(position)

        self._connected = False
        logger.info("🔌 Backtest data source disconnected")

    async def next_candle(self) -> Optional[Candle]:
        """
        Get next historical candle.

        Returns:
            Candle object or None if no more data

        Note:
            Also checks TP/SL of open positions using this candle's high/low
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        if self.index >= len(self.data):
            return None

        row = self.data.iloc[self.index]
        self.index += 1

        # Check TP/SL of open positions with this candle
        self._check_positions_tpsl(row)

        # Calculate equity (balance + unrealized PnL)
        unrealized_pnl = self._calculate_unrealized_pnl(row["close"])
        equity = self.balance + unrealized_pnl

        return Candle(
            timestamp=int(row["timestamp"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            symbol=self.symbol,
            timeframe=self.timeframe,
            equity=equity,
            balance=self.balance,
            unrealized_pnl=unrealized_pnl,
        )

    async def execute_order(self, order: Dict) -> Dict:
        """
        Simulate order execution.

        Simulates:
        - Slippage (slightly worse entry price)
        - Fees (taker commission)
        - TP/SL (checked in next_candle)

        Args:
            order: Order dict with keys: symbol, side, amount, type, price

        Returns:
            Result dict with status, trade_id, entry_price, fee, balance
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Check if there's already an open position
        if self.open_positions:
            logger.warning(
                f"❌ Order rejected | " f"Already have {len(self.open_positions)} open position(s) | " f"Max allowed: 1"
            )
            return {
                "status": "rejected",
                "reason": "max_positions_reached",
                "open_positions": len(self.open_positions),
                "balance": self.balance,
            }

        side = order["side"].lower()  # "buy" or "sell"
        amount = float(order["amount"])

        # Use current close price if no price specified
        if self.index > 0:
            price = float(order.get("price", self.data.iloc[self.index - 1]["close"]))
        else:
            price = float(order.get("price", self.data.iloc[0]["close"]))

        # Simulate slippage (worse price)
        if side == "buy":
            entry_price = price * (1 + self.slippage_rate)
        else:
            entry_price = price * (1 - self.slippage_rate)

        # Calculate cost/proceeds
        notional = amount * entry_price
        fee = notional * self.fee_rate

        # Check sufficient balance (for buy orders)
        if side == "buy" and (notional + fee) > self.balance:
            logger.warning(
                f"❌ Insufficient balance | " f"Required: {notional + fee:.2f} | " f"Available: {self.balance:.2f}"
            )
            return {
                "status": "rejected",
                "reason": "insufficient_balance",
                "balance": self.balance,
                "required": notional + fee,
            }

        # Open position
        position = {
            "trade_id": order.get("trade_id", f"backtest_{len(self.closed_trades)}"),
            "symbol": order["symbol"],
            "side": side,
            "amount": amount,
            "entry_price": entry_price,
            "notional": notional,
            "fee": fee,
            "take_profit": order.get("take_profit"),  # Multiplier (e.g., 1.01)
            "stop_loss": order.get("stop_loss"),  # Multiplier (e.g., 0.99)
            "timestamp": self.data.iloc[self.index - 1]["timestamp"] if self.index > 0 else 0,
        }

        self.open_positions.append(position)

        # Update balance: deduct fee + reserve capital for position
        # IMPORTANT: In futures/margin trading, we reserve the notional as margin
        # This ensures balance tracking is realistic and prevents over-leveraging
        # When position closes, we'll return the margin + PnL
        self.balance -= fee
        self.balance -= notional  # Reserve capital (margin)

        logger.info(
            f"📈 Order opened | "
            f"{side.upper()} {amount:.4f} @ {entry_price:.2f} | "
            f"Fee: {fee:.4f} | "
            f"Margin reserved: {notional:.2f} | "
            f"Balance: {self.balance:.2f}"
        )

        return {
            "status": "opened",
            "result": "OPENED",
            "trade_id": position["trade_id"],
            "symbol": position["symbol"],
            "side": side,
            "amount": amount,
            "entry_price": entry_price,
            "notional": notional,
            "fee": fee,
            "balance": self.balance,
        }

    def _check_positions_tpsl(self, candle_row) -> None:
        """
        Check if open positions hit TP or SL in this candle.

        Uses high/low of candle to simulate intra-candle execution.
        """
        high = float(candle_row["high"])
        low = float(candle_row["low"])
        timestamp = int(candle_row["timestamp"])

        positions_to_close = []

        for pos in self.open_positions:
            entry = pos["entry_price"]
            side = pos["side"]
            tp_mult = pos.get("take_profit")
            sl_mult = pos.get("stop_loss")

            if side == "buy":
                # Long: TP above, SL below
                tp_price = entry * tp_mult if tp_mult else None
                sl_price = entry * sl_mult if sl_mult else None

                # Check SL first (priority)
                if sl_price and low <= sl_price:
                    # IMPORTANT: Result (WIN/LOSS) will be determined by actual PnL
                    # not by exit reason. A SL can still be profitable in some cases.
                    positions_to_close.append((pos, sl_price, None, "stop_loss"))
                # Check TP
                elif tp_price and high >= tp_price:
                    positions_to_close.append((pos, tp_price, None, "take_profit"))

            else:  # sell (short)
                # Short: TP below, SL above
                tp_price = entry * tp_mult if tp_mult else None
                sl_price = entry * sl_mult if sl_mult else None

                # Check SL first (priority)
                if sl_price and high >= sl_price:
                    # IMPORTANT: Result (WIN/LOSS) will be determined by actual PnL
                    # not by exit reason. A SL can still be profitable in some cases.
                    positions_to_close.append((pos, sl_price, None, "stop_loss"))
                # Check TP
                elif tp_price and low <= tp_price:
                    positions_to_close.append((pos, tp_price, None, "take_profit"))

        # Close positions
        for pos, exit_price, result, exit_reason in positions_to_close:
            self._close_position(pos, exit_price, result, exit_reason, timestamp)

    def _close_position(
        self,
        position: Dict,
        exit_price: float,
        result: str,
        exit_reason: str,
        timestamp: int,
    ) -> None:
        """
        Close position and update balance.

        IMPORTANT:
        1. Balance update includes: return margin + PnL - exit fee
        2. Result (WIN/LOSS) is determined by actual PnL, not exit reason
           - A stop_loss can still be a WIN if PnL > 0 (e.g., trailing stop)
           - A take_profit can still be a LOSS if fees exceed profit

        This ensures balance is persistent across the session and reflects
        the actual capital available for new trades.
        """
        side = position["side"]
        amount = position["amount"]
        entry_price = position["entry_price"]
        entry_notional = position["notional"]  # Original margin reserved

        # Calculate PnL
        if side == "buy":
            pnl = (exit_price - entry_price) * amount
        else:  # sell (short)
            pnl = (entry_price - exit_price) * amount

        # Exit fee
        exit_notional = amount * exit_price
        exit_fee = exit_notional * self.fee_rate

        # Net PnL (after fees)
        net_pnl = pnl - exit_fee

        # Determine result based on actual PnL (not exit reason)
        # IMPORTANT: This is the correct way to classify trades
        # A SL can be profitable, a TP can be unprofitable (due to fees)
        if result is None:
            result = "WIN" if net_pnl > 0 else "LOSS"

        # Update balance: return margin + add PnL
        # IMPORTANT: We return the original margin (entry_notional) that was reserved
        # Then add the net PnL (which can be positive or negative)
        self.balance += entry_notional  # Return reserved margin
        self.balance += net_pnl  # Add PnL (can be negative)

        # Record closed trade
        closed_trade = {
            **position,
            "exit_price": exit_price,
            "exit_timestamp": timestamp,
            "exit_reason": exit_reason,
            "result": result,
            "pnl": net_pnl,
            "exit_fee": exit_fee,
            "total_fee": position["fee"] + exit_fee,
        }

        self.closed_trades.append(closed_trade)
        self.open_positions.remove(position)

        logger.info(
            f"{'🟢' if result == 'WIN' else '🔴'} Position closed | "
            f"{exit_reason.upper()} @ {exit_price:.2f} | "
            f"PnL: {net_pnl:+.2f} | "
            f"Balance: {self.balance:.2f}"
        )

    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL of open positions."""
        unrealized = 0.0

        for pos in self.open_positions:
            side = pos["side"]
            amount = pos["amount"]
            entry = pos["entry_price"]

            if side == "buy":
                unrealized += (current_price - entry) * amount
            else:  # sell (short)
                unrealized += (entry - current_price) * amount

        return unrealized

    def get_balance(self) -> float:
        """Get current balance (without unrealized PnL)."""
        return self.balance

    def get_equity(self) -> float:
        """Get current equity (balance + unrealized PnL)."""
        if self.index > 0:
            current_price = self.data.iloc[self.index - 1]["close"]
            unrealized = self._calculate_unrealized_pnl(current_price)
            return self.balance + unrealized
        return self.balance

    def get_stats(self) -> Dict:
        """
        Get backtest statistics.

        Returns:
            Dict with:
            - initial_balance, final_balance, final_equity
            - total_pnl, total_fees, net_pnl
            - total_trades, wins, losses, win_rate
            - avg_win, avg_loss
        """
        wins = [t for t in self.closed_trades if t["result"] == "WIN"]
        losses = [t for t in self.closed_trades if t["result"] == "LOSS"]

        total_pnl = sum(t["pnl"] for t in self.closed_trades)
        total_fees = sum(t["total_fee"] for t in self.closed_trades)

        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.balance,
            "final_equity": self.get_equity(),
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "net_pnl": total_pnl,  # Already net after fees
            "total_trades": len(self.closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.closed_trades) if self.closed_trades else 0,
            "avg_win": sum(t["pnl"] for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t["pnl"] for t in losses) / len(losses) if losses else 0,
        }
