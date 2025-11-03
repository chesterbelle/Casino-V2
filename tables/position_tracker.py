"""
Position Tracker for Casino V2 - Gestión de Posiciones Abiertas
===============================================================

Este módulo implementa el tracking de posiciones abiertas para simular
correctamente el comportamiento de live trading en backtests.

Problema que resuelve:
----------------------
- Backtest actual permite múltiples posiciones simultáneas sin límite
- No bloquea capital durante la duración del trade
- Simula cierres inmediatos en lugar de esperar TP/SL naturales

Solución:
---------
- Track de posiciones abiertas con TP/SL pendientes
- Bloqueo de capital proporcional al margen usado
- Validación de capital disponible antes de abrir posiciones
- Monitoreo vela-por-vela de TP/SL hits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PositionTracker")


@dataclass
class OpenPosition:
    """Representa una posición abierta con TP/SL pendientes."""

    trade_id: str
    symbol: str
    side: str
    entry_price: float
    entry_timestamp: str
    margin_used: float
    notional: float
    leverage: float
    tp_level: float
    sl_level: float
    liquidation_level: Optional[float]
    order: Dict[str, Any]
    bars_held: int = 0
    funding_accrued: float = 0.0


class PositionTracker:
    """
    Gestiona posiciones abiertas y capital bloqueado para simulación realista.
    """

    def __init__(self, max_concurrent_positions: int = 1):
        """
        Args:
            max_concurrent_positions: Máximo número de posiciones simultáneas permitidas
        """
        self.open_positions: List[OpenPosition] = []
        self.blocked_capital: float = 0.0
        self.max_concurrent_positions = max_concurrent_positions
        self.total_trades_opened = 0
        self.total_trades_closed = 0

    def get_available_equity(self, total_equity: float) -> float:
        """Calcula capital disponible (total - bloqueado)."""
        return max(0.0, total_equity - self.blocked_capital)

    def can_open_position(self, required_margin: float, available_equity: float) -> bool:
        """
        Verifica si se puede abrir una nueva posición.

        Args:
            required_margin: Margen requerido para la nueva posición
            available_equity: Capital disponible actualmente

        Returns:
            True si se puede abrir la posición
        """
        # Verificar límite de posiciones concurrentes
        if len(self.open_positions) >= self.max_concurrent_positions:
            return False

        # Verificar capital disponible
        return available_equity >= required_margin

    @staticmethod
    def _normalize_side(side: str) -> Optional[str]:
        """Normaliza side a LONG/SHORT respetando entradas buy/sell."""

        if not side:
            return None

        side_upper = side.upper()

        if side_upper in {"LONG", "BUY"}:
            return "LONG"
        if side_upper in {"SHORT", "SELL"}:
            return "SHORT"

        return None

    def open_position(
        self, order: Dict[str, Any], entry_price: float, entry_timestamp: str, available_equity: float
    ) -> Optional[OpenPosition]:
        """
        Abre una nueva posición y la registra.

        Args:
            order: Orden con detalles de TP/SL
            entry_price: Precio de entrada
            entry_timestamp: Timestamp de entrada
            available_equity: Capital disponible para calcular notional

        Returns:
            OpenPosition creada o None si falla
        """
        try:
            side_raw = order.get("side", "")
            side = self._normalize_side(side_raw)
            symbol = order.get("symbol", "")
            size_fraction = order.get("size", 0.0)
            leverage = order.get("leverage", 1.0)
            trade_id = order.get("trade_id", f"pos_{self.total_trades_opened}")

            if not side:
                logger.error(f"Side inválido para abrir posición: {side_raw}")
                return None

            if size_fraction is None or size_fraction <= 0:
                logger.debug(
                    "Ignorando open_position: size_fraction inválido (trade_id=%s, size=%s)",
                    trade_id,
                    size_fraction,
                )
                return None

            # Calcular notional y margen
            notional = available_equity * size_fraction * leverage
            margin_used = notional / leverage if leverage > 0 else notional

            # Calcular niveles de TP/SL
            tp_factor = order.get("take_profit", 1.01)  # 1% default
            sl_factor = order.get("stop_loss", 0.99)  # -1% default

            if side == "LONG":
                tp_level = entry_price * tp_factor
                sl_level = entry_price * sl_factor
                liquidation_level = entry_price * (1.0 - (1.0 / leverage) + 0.005)  # Aprox liquidation
            elif side == "SHORT":
                tp_level = entry_price * (2.0 - tp_factor)
                sl_level = entry_price * (2.0 - sl_factor)
                liquidation_level = entry_price * (1.0 + (1.0 / leverage) - 0.005)
            else:
                return None

            # Crear posición
            position = OpenPosition(
                trade_id=trade_id,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                entry_timestamp=entry_timestamp,
                margin_used=margin_used,
                notional=notional,
                leverage=leverage,
                tp_level=tp_level,
                sl_level=sl_level,
                liquidation_level=liquidation_level,
                order=order.copy(),
            )

            # Registrar posición
            self.open_positions.append(position)
            self.blocked_capital += margin_used
            self.total_trades_opened += 1

            logger.info(
                f"📈 OPEN | {symbol} {side} | Entry: {entry_price:.2f} | "
                f"TP: {tp_level:.2f} | SL: {sl_level:.2f} | Notional: {notional:.2f} | Margin: {margin_used:.2f}"
            )

            return position

        except Exception as e:
            logger.error(f"Error abriendo posición: {e}")
            return None

    def check_and_close_positions(self, current_candle: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Revisa todas las posiciones abiertas y cierra las que tocaron TP/SL.

        Args:
            current_candle: Vela actual con OHLC

        Returns:
            Lista de resultados de posiciones cerradas
        """
        closed_results = []
        positions_to_remove = []

        high = float(current_candle.get("high", 0))
        low = float(current_candle.get("low", 0))
        timestamp = current_candle.get("timestamp", "")

        for position in self.open_positions:
            position.bars_held += 1

            # Verificar si tocó TP/SL en esta vela
            exit_reason = None
            exit_price = None

            if position.side == "LONG":
                # Liquidation check
                if position.liquidation_level and low <= position.liquidation_level:
                    exit_reason = "LIQUIDATION"
                    exit_price = position.liquidation_level
                # SL check (prioridad sobre TP)
                elif low <= position.sl_level:
                    exit_reason = "SL"
                    exit_price = position.sl_level
                # TP check
                elif high >= position.tp_level:
                    exit_reason = "TP"
                    exit_price = position.tp_level

            elif position.side == "SHORT":
                # Liquidation check
                if position.liquidation_level and high >= position.liquidation_level:
                    exit_reason = "LIQUIDATION"
                    exit_price = position.liquidation_level
                # SL check
                elif high >= position.sl_level:
                    exit_reason = "SL"
                    exit_price = position.sl_level
                # TP check
                elif low <= position.tp_level:
                    exit_reason = "TP"
                    exit_price = position.tp_level

            # Si se cerró la posición
            if exit_reason:
                # Calcular P&L
                if position.side == "LONG":
                    pnl_pct = (exit_price - position.entry_price) / position.entry_price
                else:
                    pnl_pct = (position.entry_price - exit_price) / position.entry_price

                pnl_value = position.notional * pnl_pct

                # Crear resultado estandarizado
                result = {
                    "trade_id": position.trade_id,
                    "result": "WIN" if pnl_value > 0 else "LOSS",
                    "pnl": pnl_value,
                    "pnl_pct": pnl_pct,
                    "fee": 0.0,  # Fees ya calculados en apertura
                    "funding": position.funding_accrued,
                    "liquidated": exit_reason == "LIQUIDATION",
                    "margin_used": position.margin_used,
                    "notional": position.notional,
                    "leverage": position.leverage,
                    "symbol": position.symbol,
                    "entry_price": position.entry_price,
                    "trigger_price": exit_price,
                    "bars_held": position.bars_held,
                    "exit_reason": exit_reason,
                    "exit_timestamp": timestamp,
                    "market": current_candle.get("market", ""),
                    "timeframe": current_candle.get("timeframe", ""),
                    "timestamp": timestamp,
                    "side": position.side,
                    "action": "CLOSE",
                    "ghost": False,
                }

                # 🔴 DEBUG: Log detallado del cálculo de P&L
                logger.debug(
                    f"🔍 P&L Calc | {position.symbol} {position.side} | "
                    f"Entry: {position.entry_price:.2f} | Exit: {exit_price:.2f} | "
                    f"P&L: {pnl_value:+.2f} ({pnl_pct:.4%}) | "
                    f"Notional: {position.notional:.2f} | Side: {position.side}"
                )

                closed_results.append(result)
                positions_to_remove.append(position)

                # Liberar capital bloqueado
                self.blocked_capital -= position.margin_used
                self.total_trades_closed += 1

                logger.info(
                    f"🔒 CLOSE | {position.symbol} {position.side} | "
                    f"Exit: {exit_price:.2f} ({exit_reason}) | "
                    f"P&L: {pnl_value:+.2f} ({pnl_pct:.2%}) | Bars: {position.bars_held}"
                )

        # Remover posiciones cerradas
        for pos in positions_to_remove:
            self.open_positions.remove(pos)

        return closed_results

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del tracker."""
        return {
            "open_positions": len(self.open_positions),
            "blocked_capital": self.blocked_capital,
            "total_opened": self.total_trades_opened,
            "total_closed": self.total_trades_closed,
            "max_concurrent": self.max_concurrent_positions,
        }

    def force_close_all_positions(self, current_candle: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fuerza cierre de todas las posiciones abiertas (ej. fin del backtest).
        Usa precio de cierre actual.
        """
        closed_results = []

        close_price = float(current_candle.get("close", 0))
        timestamp = current_candle.get("timestamp", "")

        for position in self.open_positions[:]:  # Copia para modificar
            # Calcular P&L con precio de cierre
            if position.side == "LONG":
                pnl_pct = (close_price - position.entry_price) / position.entry_price
            else:
                pnl_pct = (position.entry_price - close_price) / position.entry_price

            pnl_value = position.notional * pnl_pct

            result = {
                "trade_id": position.trade_id,
                "result": "WIN" if pnl_value > 0 else "LOSS",
                "pnl": pnl_value,
                "pnl_pct": pnl_pct,
                "fee": 0.0,
                "funding": position.funding_accrued,
                "liquidated": False,
                "margin_used": position.margin_used,
                "notional": position.notional,
                "leverage": position.leverage,
                "symbol": position.symbol,
                "entry_price": position.entry_price,
                "trigger_price": close_price,
                "bars_held": position.bars_held,
                "exit_reason": "FORCED_CLOSE",
                "exit_timestamp": timestamp,
                "market": current_candle.get("market", ""),
                "timeframe": current_candle.get("timeframe", ""),
                "timestamp": timestamp,
                "side": position.side,
                "action": "CLOSE",
                "ghost": False,
            }

            closed_results.append(result)
            self.blocked_capital -= position.margin_used
            self.total_trades_closed += 1

            logger.info(
                f"🔒 FORCE CLOSE | {position.symbol} {position.side} | "
                f"Exit: {close_price:.2f} (FORCED) | "
                f"P&L: {pnl_value:+.2f} ({pnl_pct:.2%}) | Bars: {position.bars_held}"
            )

        self.open_positions.clear()
        return closed_results
