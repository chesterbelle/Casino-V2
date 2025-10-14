"""
Controlador de trading para el modo Oscar.

El objetivo es mantener la misma separación de responsabilidades del
casino: este módulo decide cuándo y cuánto apostar usando la lógica
de RangeDetector + OscarGrind, y delega la ejecución real al Croupier
que ya existe en el sistema.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import config
from croupier.croupier import Croupier

from .oscar_grind_machine import OscarGrindStateMachine, SessionStatus
from .range_sensor import RangeSensor

logger = logging.getLogger("OscarTrader")


class OscarTrader:
    """
    Orquestador del modo Oscar:

    - Lee velas y alimenta el RangeSensor para detectar oportunidades.
    - Consulta la state machine OscarGrind para saber si la sesión permite entrar
      y qué tamaño (en unidades) usar.
    - Construye una orden estandarizada y la envía al Croupier.
    - Recibe el resultado, lo convierte a unidades y actualiza la state machine.
    """

    def __init__(
        self,
        croupier: Croupier,
        range_sensor: Optional[RangeSensor] = None,
        state_machine: Optional[OscarGrindStateMachine] = None,
        unit_fraction: Optional[float] = None,
        max_fraction: Optional[float] = None,
    ) -> None:
        self.croupier = croupier
        self.range_sensor = range_sensor or RangeSensor()
        self.state_machine = state_machine or OscarGrindStateMachine(
            {
                "initial_unit_size": getattr(config, "OSCAR_INITIAL_UNIT_SIZE", 0.1),
                "profit_target": getattr(config, "OSCAR_PROFIT_TARGET", 4.0),
                "max_loss": getattr(config, "OSCAR_MAX_LOSS", -8.0),
                "max_position_size": getattr(config, "OSCAR_MAX_POSITION_UNITS", 10.0),
            }
        )
        if self.state_machine.state.status == SessionStatus.INACTIVE:
            self.state_machine.start_new_session()

        default_fraction = getattr(config, "OSCAR_UNIT_FRACTION", 0.1)
        default_max_fraction = getattr(config, "OSCAR_MAX_POSITION_FRACTION", getattr(config, "MAX_POSITION_SIZE", 0.25))

        self.unit_fraction = float(unit_fraction if unit_fraction is not None else default_fraction)
        self.max_fraction = float(max_fraction if max_fraction is not None else default_max_fraction)

    # --------------------------------------------------
    # API principal
    # --------------------------------------------------
    def process_candle(self, candle: Dict[str, Any], table_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Procesa una vela. Si se detecta señal y la sesión lo permite,
        ejecuta el trade y devuelve un resumen del resultado.
        """
        signal = self.range_sensor.process(candle)
        if not signal:
            return None

        if not self.state_machine.should_enter_trade():
            logger.debug("Oscar session inactive, ignorando señal.")
            return {"signal": signal, "executed": False, "reason": "session_inactive"}

        units = self.state_machine.get_next_position_size()
        if units <= 0:
            logger.debug("State machine devolvió size 0, ignorando señal.")
            return {"signal": signal, "executed": False, "reason": "size_zero"}

        equity = float(table_state.get("equity", table_state.get("balance", 0.0)) or 0.0)
        if equity <= 0:
            logger.warning("Equity no disponible o <= 0; no se puede calcular riesgo.")
            return {"signal": signal, "executed": False, "reason": "no_equity"}

        size_fraction = self._compute_size_fraction(units)
        if size_fraction <= 0:
            return {"signal": signal, "executed": False, "reason": "fraction_zero"}

        order = self._build_order(signal, candle, size_fraction)
        result = self.croupier.route_order(order)

        post_state = self.croupier.table.get_state() if hasattr(self.croupier, "table") else {}
        post_equity = float(post_state.get("equity", equity) or equity)
        pnl_currency = float(result.get("pnl_net", result.get("pnl", 0.0)) or (post_equity - equity))

        pnl_units = self._compute_pnl_units(result, equity)
        self.state_machine.record_result(pnl_units)

        summary = {
            "signal": signal,
            "order": order,
            "result": result,
            "pnl_units": pnl_units,
            "pnl_currency": pnl_currency,
            "session": self.state_machine.get_session_summary(),
            "units_used": units,
            "size_fraction": size_fraction,
            "notional": equity * size_fraction,
            "equity_before": equity,
            "executed": True,
        }
        return summary

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _compute_size_fraction(self, units: float) -> float:
        fraction = units * self.unit_fraction
        fraction = min(fraction, self.max_fraction)
        fraction = max(0.0, fraction)
        return fraction

    def _build_order(self, signal: Dict[str, Any], candle: Dict[str, Any], size_fraction: float) -> Dict[str, Any]:
        side = signal["side"]
        price = float(signal["price"])
        support = float(signal.get("support", price))
        resistance = float(signal.get("resistance", price))
        buffer_percent = float(signal.get("buffer_percent", 0.0))

        if side == "LONG":
            tp_price = resistance
            sl_price = support * (1 - buffer_percent)
        else:
            tp_price = support
            sl_price = resistance * (1 + buffer_percent)

        tp_factor = self._price_to_factor(tp_price, price, side, default=1.0 + getattr(config, "TAKE_PROFIT", 0.01))
        sl_factor = self._price_to_factor(sl_price, price, side, default=1.0 - getattr(config, "STOP_LOSS", 0.01), is_stop=True)

        trade_id = self._make_trade_id(signal, side)
        order = {
            "symbol": candle.get("symbol", "UNKNOWN"),
            "timeframe": candle.get("timeframe", "UNKNOWN"),
            "timestamp": candle.get("timestamp"),
            "side": side,
            "size": size_fraction,
            "take_profit": tp_factor,
            "stop_loss": sl_factor,
            "trade_id": trade_id,
            "ghost": False,
        }
        return order

    def _price_to_factor(self, target_price: float, entry_price: float, side: str, default: float, is_stop: bool = False) -> float:
        if entry_price <= 0 or target_price <= 0:
            return default

        if side == "LONG":
            factor = target_price / entry_price
        else:
            # Para cortos: un TP por debajo significa factor < 1; un SL por encima > 1.
            factor = target_price / entry_price

        if is_stop:
            # Evitar stops imposibles
            if side == "LONG" and factor >= 1.0:
                return default
            if side == "SHORT" and factor <= 1.0:
                return default
        else:
            if side == "LONG" and factor <= 1.0:
                return default
            if side == "SHORT" and factor >= 1.0:
                return default

        return max(0.001, factor)

    def _compute_pnl_units(self, result: Dict[str, Any], equity_before: float) -> float:
        pnl = float(result.get("pnl", 0.0) or 0.0)
        fee = float(result.get("fee", 0.0) or 0.0)
        net = pnl - fee

        unit_value = equity_before * self.unit_fraction if self.unit_fraction > 0 else 0.0
        if unit_value <= 0:
            return 0.0

        return net / unit_value

    def _make_trade_id(self, signal: Dict[str, Any], side: str) -> str:
        ts = signal.get("timestamp")
        if not ts:
            ts = datetime.utcnow().isoformat()
        symbol = signal.get("symbol", "UNKNOWN")
        timeframe = signal.get("timeframe", "UNKNOWN")
        return f"Oscar-{symbol}@{timeframe}-{side}-{ts}"
