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

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

if TYPE_CHECKING:
    from exchanges.adapters.ccxt_adapter import CCXTAdapter

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
        mode: Literal["simulation", "confirmed", "hybrid"] = "hybrid",
        adapter: Optional["CCXTAdapter"] = None,
    ):
        """
        Args:
            max_concurrent_positions: Máximo número de posiciones simultáneas permitidas
            mode: Modo de operación:
                - "simulation": Simula cierres con OHLC (backtest)
                - "confirmed": Solo cierra con confirmación del exchange (live)
                - "hybrid": Detecta + espera confirmación (recomendado)
            adapter: CCXTAdapter para OCO manual (agnóstico del conector)
        """
        self.open_positions: List[OpenPosition] = []
        self.blocked_capital: float = 0.0
        self.max_concurrent_positions = max_concurrent_positions
        self.total_trades_opened = 0
        self.total_trades_closed = 0
        self.total_wins = 0  # Track wins
        self.total_losses = 0  # Track losses

        # NUEVO v1.9.1: Modo de operación
        self.mode = mode

        # NUEVO v1.9.1: Tracking de confirmaciones pendientes
        self.pending_confirmations: Dict[str, Dict[str, Any]] = {}

        # NUEVO v2.0: OCO Manual agnóstico
        self.adapter = adapter
        self._active_orders: Dict[str, Dict[str, Any]] = {}  # Track TP/SL orders for OCO
        self._oco_lock = asyncio.Lock()

        logger.info(f"PositionTracker inicializado | Modo: {mode} | Max positions: {max_concurrent_positions}")
        if adapter:
            logger.info("✅ OCO Manual enabled (adapter provided)")

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
                main_order_id=main_order_id,
                tp_order_id=tp_order_id,
                sl_order_id=sl_order_id,
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
        Revisa todas las posiciones abiertas según el modo configurado.

        VERSIÓN v1.9.1: Soporte para 3 modos
        -------------------------------------
        - **simulation**: Cierra inmediatamente si TP/SL tocado
        - **confirmed**: No cierra, solo espera confirmación del exchange
        - **hybrid**: Detecta TP/SL, marca como pending, espera confirmación

        Args:
            current_candle: Vela actual con OHLC

        Returns:
            Lista de resultados de posiciones cerradas (o pending en modo hybrid)
        """
        if self.mode == "simulation":
            return self._simulate_closes(current_candle)
        elif self.mode == "confirmed":
            # Solo actualiza bars_held, no cierra nada
            for position in self.open_positions:
                position.bars_held += 1
            return []
        else:  # hybrid
            return self._hybrid_check(current_candle)

    def _simulate_closes(self, current_candle: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Modo simulation: Cierra inmediatamente si TP/SL tocado (backtest).
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
                    "confirmed": True,  # En simulation, se considera confirmado
                }

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
                    f"🔒 CLOSE (simulation) | {position.symbol} {position.side} | "
                    f"Exit: {exit_price:.2f} ({exit_reason}) | "
                    f"P&L: {pnl_value:+.2f} ({pnl_pct:.2%}) | Bars: {position.bars_held}"
                )

        # Remover posiciones cerradas
        for pos in positions_to_remove:
            self.open_positions.remove(pos)

        return closed_results

    def _hybrid_check(self, current_candle: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Modo hybrid: Detecta TP/SL tocados, marca como pending, espera confirmación.

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
        }

        # Remover de pending si estaba
        if trade_id in self.pending_confirmations:
            del self.pending_confirmations[trade_id]

        # Remover posición
        self.open_positions.remove(position)

        # Liberar capital bloqueado
        self.blocked_capital -= position.margin_used
        self.total_trades_closed += 1

        # Track wins/losses
        if pnl > 0:
            self.total_wins += 1
        else:
            self.total_losses += 1

        logger.info(
            f"✅ CONFIRMED CLOSE | {position.symbol} {position.side} | "
            f"Exit: {exit_price:.2f} ({exit_reason}) | "
            f"PnL REAL: {pnl:+.2f} | Fee: {fee:.2f} | Bars: {position.bars_held}"
        )

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

    # =========================================================
    # 🎯 OCO MANUAL (ONE-CANCELS-THE-OTHER) MANAGEMENT
    # =========================================================
    # Moved from BinanceConnector to PositionTracker (v2.0)
    # Agnóstico del conector - usa solo métodos de CCXTAdapter

    def register_tpsl_pair(self, symbol: str, tp_order_id: str, sl_order_id: str) -> None:
        """Register TP/SL order pair for OCO monitoring."""
        if symbol not in self._active_orders:
            self._active_orders[symbol] = {}

        self._active_orders[symbol][tp_order_id] = {"type": "TP", "opposite": sl_order_id}
        self._active_orders[symbol][sl_order_id] = {"type": "SL", "opposite": tp_order_id}

        logger.info(f"📝 Registered TP/SL pair for {symbol}: TP={tp_order_id}, SL={sl_order_id}")

    async def monitor_oco_execution(self) -> None:
        """
        Monitor active TP/SL orders and execute manual OCO if needed.

        Esta función es responsable de:
        1. Monitorear órdenes TP/SL registradas
        2. Detectar ejecuciones (TP o SL)
        3. Cancelar orden hermana cuando una se ejecuta
        4. Cerrar la posición

        Sigue el principio "Let it Crash":
        - Falla rápido si hay errores
        - Capas superiores (Croupier) manejan recuperación

        Should be called periodically from Croupier or a central clock.
        """
        if not self.adapter or not self._active_orders:
            return

        try:
            await self._check_manual_tpsl_execution()
        except Exception as e:
            logger.error(f"❌ OCO Manual: Error in monitoring: {e}")

    async def _check_manual_tpsl_execution(self) -> None:
        """Check if any TP/SL orders should be executed manually based on current price."""
        if not self._active_orders:
            return

        try:
            symbols_to_cleanup = []

            # Check each symbol's active orders
            for symbol, orders in list(self._active_orders.items()):
                try:
                    # Get current price
                    ticker = await self.adapter.fetch_ticker(symbol)
                    current_price = ticker.get("last", 0)

                    if not current_price:
                        logger.warning(f"⚠️ OCO Manual: No current price for {symbol}")
                        continue

                    logger.debug(f"💰 OCO Manual: Current price for {symbol}: ${current_price:.4f}")

                    # Check each order
                    orders_to_execute = []
                    for order_id, order_info in orders.items():
                        try:
                            # Get order details
                            order = await self.adapter.fetch_order(order_id, symbol)
                            if not order:
                                continue

                            order_status = order.get("status")
                            order_type = order.get("type", "")

                            # Get stopPrice
                            info = order.get("info", {})
                            stop_price = (
                                order.get("stopPrice")
                                or order.get("triggerPrice")
                                or info.get("stopPrice")
                                or info.get("triggerPrice")
                            )

                            if isinstance(stop_price, str):
                                stop_price = float(stop_price)

                            if order_status != "open" or not stop_price:
                                continue

                            # Get position side
                            position_side = await self._get_position_side(symbol)

                            # Check if price should trigger execution
                            should_execute = False
                            is_take_profit = "take_profit" in order_type.lower() or order_info.get("type") == "TP"
                            is_stop_loss = "stop" in order_type.lower() or order_info.get("type") == "SL"

                            if is_take_profit:
                                if position_side == "short" and current_price <= stop_price:
                                    should_execute = True
                                elif position_side == "long" and current_price >= stop_price:
                                    should_execute = True

                            elif is_stop_loss:
                                if position_side == "short" and current_price >= stop_price:
                                    should_execute = True
                                elif position_side == "long" and current_price <= stop_price:
                                    should_execute = True

                            if should_execute:
                                logger.info(f"🚨 OCO Manual: TRIGGER DETECTED for {symbol}")
                                orders_to_execute.append((order_id, order_info, order, stop_price))

                        except Exception as e:
                            logger.debug(f"⚠️ OCO Manual: Error checking order {order_id[:8]}...: {e}")

                    # Execute triggered orders
                    if orders_to_execute:
                        for order_id, order_info, order, stop_price in orders_to_execute:
                            await self._execute_tpsl_manually(
                                symbol, order_id, order_info, order, current_price, stop_price
                            )
                            if symbol not in symbols_to_cleanup:
                                symbols_to_cleanup.append(symbol)

                except Exception as e:
                    logger.error(f"❌ OCO Manual: Error checking symbol {symbol}: {e}")

            # Clean up symbols after iteration
            for symbol in symbols_to_cleanup:
                if symbol in self._active_orders:
                    del self._active_orders[symbol]
                    logger.debug(f"🧹 OCO Manual: Cleaned up tracking for {symbol}")

        except Exception as e:
            logger.error(f"❌ OCO Manual: Error in manual TP/SL check: {e}")

    async def _get_position_side(self, symbol: str) -> str:
        """Get the side of the current position for a symbol."""
        try:
            positions = await self.adapter.fetch_positions([symbol])

            for pos in positions:
                if pos.get("symbol") == symbol and abs(pos.get("contracts", 0)) > 0:
                    return pos.get("side", "unknown").lower()

            return "unknown"
        except Exception as e:
            logger.error(f"❌ OCO Manual: Error getting position side for {symbol}: {e}")
            return "unknown"

    async def _execute_tpsl_manually(
        self, symbol: str, order_id: str, order_info: dict, order: dict, current_price: float, trigger_price: float
    ) -> None:
        """Execute a TP/SL order manually by converting it to a market order."""
        order_type = order_info.get("type", "unknown")
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"🎯 Executing {order_type} manually (attempt {attempt + 1}/{max_retries}): {symbol} @ ${current_price:.2f}"
                )

                # Step 0: Find the open position for this symbol
                open_position = None
                for pos in self.open_positions:
                    if pos.symbol == symbol:
                        open_position = pos
                        break

                if not open_position:
                    logger.error(f"❌ OCO Manual: No open position found for {symbol}")
                    return

                trade_id = open_position.trade_id

                # Step 1: Cancel the original TP/SL order
                try:
                    await self.adapter.cancel_order(order_id, symbol)
                    logger.debug(f"✅ OCO Manual: Cancelled original {order_type} order {order_id[:8]}...")
                except Exception as e:
                    logger.warning(f"⚠️ OCO Manual: Failed to cancel order: {e}")

                # Step 2: Get position side and amount
                position_side = await self._get_position_side(symbol)
                if position_side == "long":
                    close_side = "sell"
                elif position_side == "short":
                    close_side = "buy"
                else:
                    logger.error(f"❌ OCO Manual: Unknown position side: {position_side}")
                    return

                # Get amount from position
                try:
                    positions = await self.adapter.fetch_positions([symbol])
                    amount = 0
                    for pos in positions:
                        if pos.get("symbol") == symbol:
                            amount = abs(pos.get("contracts", 0))
                            break

                    if amount <= 0:
                        logger.error(f"❌ OCO Manual: No position found for {symbol}")
                        return
                except Exception as e:
                    logger.error(f"❌ OCO Manual: Error fetching position: {e}")
                    return

                logger.info(f"🎯 OCO Manual: Closing {position_side} position with {close_side} {amount} contracts")

                # Step 3: Create market order to close position
                market_order = await self.adapter.create_order(
                    symbol,
                    "market",
                    close_side,
                    amount,
                    None,
                    {"reduceOnly": True},
                )

                close_order_id = market_order.get("id")
                logger.info(f"✅ OCO Manual: {order_type} executed manually: {close_order_id}")

                # Step 4: Cancel opposite order (OCO behavior)
                opposite_id = order_info.get("opposite")
                if opposite_id:
                    try:
                        await self.adapter.cancel_order(opposite_id, symbol)
                        logger.info(f"✅ OCO Manual: Cancelled opposite order {opposite_id[:8]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ OCO Manual: Failed to cancel opposite order: {e}")

                # Step 4b: Cancel main order (important for multi-asset trading)
                # The main_order_id is the entry order that opened the position
                # It must be cancelled to fully close the position
                main_order_id = open_position.main_order_id
                if main_order_id and main_order_id != order_id:  # Don't cancel if it's the same as the TP/SL
                    try:
                        await self.adapter.cancel_order(main_order_id, symbol)
                        logger.info(f"✅ OCO Manual: Cancelled main order {main_order_id[:8]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ OCO Manual: Failed to cancel main order: {e}")

                # Step 5: Confirm close in PositionTracker
                # Calculate PnL based on entry and exit price
                if position_side == "long":
                    pnl = (current_price - open_position.entry_price) * amount
                else:  # short
                    pnl = (open_position.entry_price - current_price) * amount

                self.confirm_close(
                    trade_id=trade_id,
                    exit_price=current_price,
                    exit_reason=order_type,  # "TP" or "SL"
                    pnl=pnl,
                    fee=0.0,  # TODO: Get actual fee from market_order
                )

                logger.info(f"✅ OCO Manual: Position {trade_id} closed | PnL: ${pnl:.2f}")

                return

            except Exception as e:
                logger.error(f"❌ OCO Manual: Execution attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5
                    await asyncio.sleep(wait_time)
