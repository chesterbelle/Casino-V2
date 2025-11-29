"""
Position Tracker for Casino V2 - Gestión de Posiciones Abiertas
===============================================================

Este módulo implementa el tracking de posiciones abiertas con soporte para
confirmación de cierres con datos reales del exchange.

VERSIÓN v1.9.1: Modo Híbrido
-----------------------------
- **simulation**: Simula cierres con OHLC (para backtest)
- **confirmed**: Solo cierra con confirmación del exchange (para live)
- **hybrid**: Detecta TP/SL + espera confirmación (mejor de ambos mundos)

Problema que resuelve:
----------------------
- Backtest actual permite múltiples posiciones simultáneas sin límite
- No bloquea capital durante la duración del trade
- Simula cierres inmediatos en lugar de esperar TP/SL naturales
- NO confirma cierres con datos reales del exchange (v1.9)

Solución v1.9.1:
----------------
- Track de posiciones abiertas con TP/SL pendientes
- Bloqueo de capital proporcional al margen usado
- Validación de capital disponible antes de abrir posiciones
- Monitoreo vela-por-vela de TP/SL hits
- **NUEVO**: Confirmación de cierres con datos reales del exchange
- **NUEVO**: Modo híbrido (detecta + confirma)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from exchanges.adapters.ccxt_adapter import CCXTAdapter

import config.trading

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
    main_order_id: Optional[str] = None  # ID de la orden principal (MARKET/LIMIT)
    tp_order_id: Optional[str] = None  # ID de la orden TP (TAKE_PROFIT_MARKET)
    sl_order_id: Optional[str] = None  # ID de la orden SL (STOP_MARKET)
    bars_held: int = 0
    funding_accrued: float = 0.0
    contributors: List[str] = None  # Sensores que contribuyeron a la señal


class PositionTracker:
    """
    Gestiona posiciones abiertas y capital bloqueado con soporte para confirmación.

    VERSIÓN v1.9.1: Modo Híbrido
    -----------------------------
    - **simulation**: Simula cierres con OHLC (para backtest)
    - **confirmed**: Solo cierra con confirmación del exchange (para live)
    - **hybrid**: Detecta TP/SL + espera confirmación (recomendado)

    Ejemplo:
        # Modo simulation (backtest)
        tracker = PositionTracker(mode="simulation")

        # Modo hybrid (testing/live)
        tracker = PositionTracker(mode="hybrid")

        # Detectar cierres
        closes = tracker.check_and_close_positions(candle)

        # Confirmar cierre con datos reales
        result = tracker.confirm_close(
            trade_id="trade_123",
            exit_price=50000.0,  # Precio REAL del fill
            exit_reason="TP",
            pnl=150.0,  # PnL REAL
            fee=2.5
        )
    """

    def __init__(
        self,
        max_concurrent_positions: int = 1,
        adapter: Optional["CCXTAdapter"] = None,
        on_close_callback: Optional[callable] = None,
    ):
        """
        Args:
            max_concurrent_positions: Máximo número de posiciones simultáneas permitidas
            adapter: CCXTAdapter para OCO manual (agnóstico del conector)
        """
        self.open_positions: List[OpenPosition] = []
        self.blocked_capital: float = 0.0
        self.max_concurrent_positions = max_concurrent_positions
        self.on_close_callback = on_close_callback
        self.total_trades_opened = 0
        self.total_trades_closed = 0
        self.total_wins = 0  # Track wins
        self.total_losses = 0  # Track losses

        # Tracking de confirmaciones pendientes
        self.pending_confirmations: Dict[str, Dict[str, Any]] = {}

        logger.info(f"PositionTracker inicializado | Max positions: {max_concurrent_positions}")

    def get_available_equity(self, total_equity: float) -> float:
        """Calcula capital disponible (total - bloqueado)."""
        return max(0.0, total_equity - self.blocked_capital)

    def get_position(self, trade_id: str) -> Optional["OpenPosition"]:
        """Busca una posición por trade_id."""
        for position in self.open_positions:
            if position.trade_id == trade_id:
                return position
        return None

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
        self,
        order: Dict[str, Any],
        entry_price: float,
        entry_timestamp: str,
        available_equity: float,
        main_order_id: Optional[str] = None,
        tp_order_id: Optional[str] = None,
        sl_order_id: Optional[str] = None,
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
            tp_factor = order.get("take_profit", 1.0 + config.trading.TAKE_PROFIT)
            sl_factor = order.get("stop_loss", 1.0 - config.trading.STOP_LOSS)

            if side == "LONG":
                tp_level = entry_price * tp_factor
                sl_level = entry_price * sl_factor
                liquidation_level = entry_price * (1.0 - (1.0 / leverage) + 0.005)  # Aprox liquidation
            elif side == "SHORT":
                # TP Logic: Support both implicit (1.01) and explicit (0.99) multipliers
                # If tp_factor > 1.0 (e.g., 1.01), it's "LONG-centric" so invert it (2.0 - 1.01 = 0.99)
                # If tp_factor < 1.0 (e.g., 0.99), it's already correct for SHORT, use directly
                if tp_factor > 1.0:
                    tp_level = entry_price * (2.0 - tp_factor)
                else:
                    tp_level = entry_price * tp_factor

                # SL Logic: Support both implicit (0.99) and explicit (1.015) multipliers
                # If sl_factor < 1.0 (e.g., 0.99), it's "LONG-centric" loss so invert it (2.0 - 0.99 = 1.01)
                # If sl_factor > 1.0 (e.g., 1.015), it's already correct for SHORT, use directly
                if sl_factor < 1.0:
                    sl_level = entry_price * (2.0 - sl_factor)
                else:
                    sl_level = entry_price * sl_factor

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
                main_order_id=main_order_id,
                tp_order_id=tp_order_id,
                sl_order_id=sl_order_id,
                contributors=order.get("contributors", []),
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
        Verifica si alguna posición debe cerrarse según la vela actual.
        Detecta TP/SL tocados y marca como pending para verificación con exchange.

        Args:
            current_candle: Vela actual con keys: timestamp, open, high, low, close

        Returns:
            Lista de resultados de cierre (o eventos pending)
        """
        return self._check_potential_exits(current_candle)

    def _check_potential_exits(self, current_candle: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detecta TP/SL tocados, marca como pending, espera confirmación.
        NO cierra la posición ni cuenta como WIN/LOSS hasta que exchange confirme.
        """
        potential_closes = []
        high = float(current_candle.get("high", 0))
        low = float(current_candle.get("low", 0))
        timestamp = current_candle.get("timestamp", "")

        for position in self.open_positions:
            position.bars_held += 1

            # Skip si ya está pending
            if position.trade_id in self.pending_confirmations:
                continue

            # Detectar si TP/SL fue tocado
            exit_reason = None
            exit_price = None

            if position.side == "LONG":
                if position.liquidation_level and low <= position.liquidation_level:
                    exit_reason = "LIQUIDATION"
                    exit_price = position.liquidation_level
                elif low <= position.sl_level:
                    exit_reason = "SL"
                    exit_price = position.sl_level
                elif high >= position.tp_level:
                    exit_reason = "TP"
                    exit_price = position.tp_level

            elif position.side == "SHORT":
                if position.liquidation_level and high >= position.liquidation_level:
                    exit_reason = "LIQUIDATION"
                    exit_price = position.liquidation_level
                elif high >= position.sl_level:
                    exit_reason = "SL"
                    exit_price = position.sl_level
                elif low <= position.tp_level:
                    exit_reason = "TP"
                    exit_price = position.tp_level

            # Time-Based Exit Check (Optimization Alignment)
            # If no TP/SL hit and max bars exceeded, close at market (current close)
            if not exit_reason and position.bars_held >= config.trading.MAX_HOLD_BARS:
                exit_reason = "TIME_EXIT"
                exit_price = float(current_candle.get("close", 0))
                logger.info(
                    f"⏳ Time Limit Reached for {position.trade_id} ({position.bars_held} bars). Closing at {exit_price}"
                )

            if exit_reason:
                # Calcular PnL teórico (para referencia)
                if position.side == "LONG":
                    pnl_pct = (exit_price - position.entry_price) / position.entry_price
                else:
                    pnl_pct = (position.entry_price - exit_price) / position.entry_price

                pnl_value = position.notional * pnl_pct

                # Marcar como pending (NO confirmar aún)
                pending_result = {
                    "trade_id": position.trade_id,
                    "symbol": position.symbol,
                    "side": position.side,
                    "entry_price": position.entry_price,
                    "exit_price_detected": exit_price,  # Teórico
                    "exit_reason_detected": exit_reason,
                    "pnl_estimated": pnl_value,  # Estimado
                    "bars_held": position.bars_held,
                    "timestamp": timestamp,
                    "confirmed": False,  # ← FLAG CRÍTICO
                    "pending_confirmation": True,
                    "status": "PENDING_CONFIRMATION",
                }

                # Guardar en pending
                self.pending_confirmations[position.trade_id] = pending_result

                logger.info(
                    f"⏳ PENDING | {position.symbol} {position.side} | "
                    f"Detected: {exit_reason} @ {exit_price:.2f} | "
                    f"PnL estimado: {pnl_value:+.2f} | "
                    f"Esperando confirmación del exchange..."
                )

                potential_closes.append(pending_result)

        return potential_closes

    def confirm_close(
        self, trade_id: str, exit_price: float, exit_reason: str, pnl: float, fee: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        NUEVO v1.9.1: Confirma cierre con datos REALES del exchange.

        Este método debe ser llamado cuando se recibe un fill confirmado del exchange
        que cierra una posición.

        Args:
            trade_id: ID del trade
            exit_price: Precio de salida REAL (del fill)
            exit_reason: Razón CONFIRMADA ("TP" | "SL" | "MANUAL" | "LIQUIDATION")
            pnl: PnL REAL (incluye fees, slippage)
            fee: Fee REAL

        Returns:
            Resultado confirmado o None si no existe la posición

        Ejemplo:
            # Cuando llega fill del exchange
            result = tracker.confirm_close(
                trade_id="trade_123",
                exit_price=50150.0,  # Precio REAL del fill
                exit_reason="TP",
                pnl=150.0,  # PnL REAL
                fee=2.5
            )

            if result:
                print(f"Cierre confirmado: {result['result']}")
                gemini.on_trade_result(trade_id, result)
        """
        # Buscar posición
        position = None
        for pos in self.open_positions:
            if pos.trade_id == trade_id:
                position = pos
                break

        if not position:
            logger.warning(f"⚠️ No se encontró posición para confirmar: {trade_id}")
            return None

        # Crear resultado CONFIRMADO con datos REALES
        result = {
            "trade_id": trade_id,
            "result": "WIN" if pnl > 0 else "LOSS",
            "pnl": pnl,  # ← PNL REAL
            "pnl_pct": pnl / position.notional if position.notional > 0 else 0.0,
            "fee": fee,  # ← FEE REAL
            "funding": position.funding_accrued,
            "liquidated": exit_reason == "LIQUIDATION",
            "margin_used": position.margin_used,
            "notional": position.notional,
            "leverage": position.leverage,
            "symbol": position.symbol,
            "entry_price": position.entry_price,
            "exit_price": exit_price,  # ← PRECIO REAL
            "trigger_price": exit_price,
            "bars_held": position.bars_held,
            "exit_reason": exit_reason,  # ← CONFIRMADO
            "side": position.side,
            "action": "CLOSE",
            "ghost": False,
            "confirmed": True,  # ← FLAG CRÍTICO
            "state_source": "exchange_confirmed",
            "contributors": position.contributors,
        }

        # Remover de pending si estaba
        if trade_id in self.pending_confirmations:
            del self.pending_confirmations[trade_id]

        # Remover posición
        self.open_positions.remove(position)

        # Liberar capital bloqueado
        self.blocked_capital -= position.margin_used
        self.total_trades_closed += 1

        # Track wins/losses based on exit reason (TP = win, SL = loss)
        # This measures if the prediction was correct, not if we made money
        if exit_reason == "TP":
            self.total_wins += 1
        elif exit_reason in ["SL", "FORCE_CLOSE", "END_SESSION", "MANUAL_SYNC", "MANUAL", "TIME_EXIT"]:
            self.total_losses += 1
        # Other reasons (IMMEDIATE_CLOSE) don't count as wins/losses

        logger.info(
            f"✅ CONFIRMED CLOSE | {position.symbol} {position.side} | "
            f"Exit: {exit_price:.2f} ({exit_reason}) | "
            f"PnL REAL: {pnl:+.2f} | Fee: {fee:.2f} | Bars: {position.bars_held}"
        )

        # Notificar a Gemini (o cualquier otro listener) sobre el resultado
        if self.on_close_callback:
            try:
                self.on_close_callback(trade_id, result)
            except Exception as e:
                logger.error(f"Error en callback on_close_callback: {e}")

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del tracker."""
        return {
            "open_positions": len(self.open_positions),
            "blocked_capital": self.blocked_capital,
            "total_opened": self.total_trades_opened,
            "total_closed": self.total_trades_closed,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
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
                "result": "LOSS",  # Force close is always considered a LOSS
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
