"""
State machine del método Oscar Grind adaptada para Casino V2.

La responsabilidad de esta clase es exclusivamente gestionar la
progresión de unidades (stake sizing) de acuerdo al criterio de
Oscar Grind: aumentar tras ganancias hasta completar +1 unidad,
reiniciar tras pérdidas y detener la sesión al alcanzar los
umbrales de profit o max loss definidos en la configuración.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger("OscarGrind")


class TradeResult(Enum):
    WIN = "win"
    LOSS = "loss"
    PENDING = "pending"


class SessionStatus(Enum):
    ACTIVE = "active"
    TARGET_HIT = "target_hit"
    MAX_LOSS = "max_loss"
    INACTIVE = "inactive"


@dataclass
class SessionState:
    status: SessionStatus
    current_position_size: float
    session_pnl: float
    consecutive_wins: int
    last_trade_result: TradeResult
    trades_count: int
    sequence_progress: float


class OscarGrindStateMachine:
    """
    Implementación pura del método Oscar Grind.

    No ejecuta operaciones ni calcula PnL monetario; únicamente
    recibe resultados expresados en “unidades” y determina el tamaño
    de la siguiente apuesta junto con el estado global de la sesión.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = dict(config)
        self.initial_unit_size = float(self.config.get("initial_unit_size", 1.0))
        self.profit_target = float(self.config.get("profit_target", 4.0))
        self.max_loss = float(self.config.get("max_loss", -8.0))
        self.max_position_size = float(self.config.get("max_position_size", 10.0))

        self.state = SessionState(
            status=SessionStatus.INACTIVE,
            current_position_size=self.initial_unit_size,
            session_pnl=0.0,
            consecutive_wins=0,
            last_trade_result=TradeResult.PENDING,
            trades_count=0,
            sequence_progress=0.0,
        )

        logger.info(
            "Oscar Grind inicializado. Target=%.2f unidades | MaxLoss=%.2f unidades",
            self.profit_target,
            self.max_loss,
        )

    # --------------------------------------------------
    # Control de sesión
    # --------------------------------------------------
    def start_new_session(self) -> None:
        self.state = SessionState(
            status=SessionStatus.ACTIVE,
            current_position_size=self.initial_unit_size,
            session_pnl=0.0,
            consecutive_wins=0,
            last_trade_result=TradeResult.PENDING,
            trades_count=0,
            sequence_progress=0.0,
        )
        logger.info("Nueva sesión Oscar Grind iniciada.")

    def _check_session_limits(self) -> None:
        if self.state.session_pnl >= self.profit_target:
            self.state.status = SessionStatus.TARGET_HIT
            logger.info("Sesión completada: profit target alcanzado (%.2f unidades).", self.state.session_pnl)
        elif self.state.session_pnl <= self.max_loss:
            self.state.status = SessionStatus.MAX_LOSS
            logger.info("Sesión detenida: max loss alcanzado (%.2f unidades).", self.state.session_pnl)

    # --------------------------------------------------
    # API de interacción
    # --------------------------------------------------
    def should_enter_trade(self) -> bool:
        return self.state.status == SessionStatus.ACTIVE

    def get_next_position_size(self) -> float:
        if self.state.status != SessionStatus.ACTIVE:
            return 0.0
        return min(self.state.current_position_size, self.max_position_size)

    def record_result(self, pnl_units: float) -> None:
        """
        Actualiza la sesión con el resultado de la última operación,
        expresado en unidades Oscar (positivo = win, negativo = loss).
        """
        if self.state.status != SessionStatus.ACTIVE:
            logger.warning("Intento de registrar resultado con la sesión inactiva.")
            return

        pnl_units = float(pnl_units)
        self.state.session_pnl += pnl_units
        self.state.trades_count += 1

        if pnl_units > 0:
            result = TradeResult.WIN
            self.state.consecutive_wins += 1
        else:
            result = TradeResult.LOSS
            self.state.consecutive_wins = 0
            self.state.sequence_progress = 0.0

        self.state.last_trade_result = result

        if result == TradeResult.WIN:
            profit_fraction = pnl_units / self.initial_unit_size if self.initial_unit_size > 0 else 0.0
            self.state.sequence_progress += profit_fraction

            if self.state.sequence_progress >= 1.0:
                self.state.current_position_size = self.initial_unit_size
                self.state.sequence_progress %= 1.0
            else:
                self.state.current_position_size += profit_fraction
        else:
            self.state.current_position_size = self.initial_unit_size

        self.state.current_position_size = max(self.initial_unit_size, min(self.state.current_position_size, self.max_position_size))

        logger.debug(
            "OscarGrind -> Resultado registrado %.4f unidades | próximo size %.4f | pnl acumulado %.4f",
            pnl_units,
            self.state.current_position_size,
            self.state.session_pnl,
        )

        self._check_session_limits()

    def get_session_summary(self) -> Dict[str, Any]:
        progress_pct = (self.state.session_pnl / self.profit_target * 100.0) if self.profit_target else 0.0
        return {
            "status": self.state.status.value,
            "current_position_size": self.state.current_position_size,
            "session_pnl": self.state.session_pnl,
            "consecutive_wins": self.state.consecutive_wins,
            "last_trade_result": self.state.last_trade_result.value,
            "trades_count": self.state.trades_count,
            "sequence_progress": self.state.sequence_progress,
            "progress_to_target_pct": progress_pct,
        }

