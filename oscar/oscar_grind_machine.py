"""
State machine del método Oscar Grind adaptada para Casino V2.

La responsabilidad de esta clase es exclusivamente gestionar la
progresión de unidades (stake sizing) de acuerdo al criterio de
Oscar Grind: aumentar tras ganancias hasta completar +1 unidad,
reiniciar tras pérdidas y detener la sesión al alcanzar los
umbrales de profit o max loss definidos en la configuración.
"""

# --------------------------------------------------
# Explicación Coloquial del Rol de esta Clase (El Estratega)
# --------------------------------------------------
# Esta clase actúa como un "contador de fichas" de casino. Su única
# responsabilidad es decidir CUÁNTAS fichas apostar en la siguiente
# ronda, sin saber cuánto dinero vale cada ficha.
#
# - Lógica Principal:
#   - Si se gana una operación, la siguiente apuesta aumenta en 1 ficha.
#   - Si se pierde, la apuesta se mantiene con la misma cantidad de fichas.
#   - Si la ganancia neta de la sesión alcanza +1 unidad (o más), la
#     secuencia se reinicia, volviendo a apostar 1 ficha.
#
# Este módulo está aislado del dinero. Solo maneja unidades simbólicas
# (1.0, 2.0, 3.0...), permitiendo que el "Banquero" (OscarTrader) decida
# el valor monetario de cada "ficha".
# --------------------------------------------------

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
    BREAKEVEN = "breakeven"


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
    wins_count: int
    losses_count: int
    draws_count: int


class OscarGrindStateMachine:
    """
    Implementación pura del método Oscar Grind.

    No ejecuta operaciones ni calcula PnL monetario; únicamente
    recibe resultados expresados en “unidades” y determina el tamaño
    de la siguiente apuesta junto con el estado global de la sesión.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = dict(config)
        self.base_unit = 1.0
        self.profit_target = float(self.config.get("profit_target", 4.0))
        self.max_loss = float(self.config.get("max_loss", -8.0))
        self.max_position_size = float(self.config.get("max_position_size", 10.0))

        self.state = SessionState(
            status=SessionStatus.INACTIVE,
            current_position_size=self.base_unit,
            session_pnl=0.0,
            consecutive_wins=0,
            last_trade_result=TradeResult.PENDING,
            trades_count=0,
            wins_count=0,
            losses_count=0,
            draws_count=0,
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
            current_position_size=self.base_unit,
            session_pnl=0.0,
            consecutive_wins=0,
            last_trade_result=TradeResult.PENDING,
            trades_count=0,
            wins_count=0,
            losses_count=0,
            draws_count=0,
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
        epsilon = 1e-9
        self.state.session_pnl += pnl_units
        self.state.trades_count += 1

        if pnl_units > epsilon:
            result = TradeResult.WIN
            self.state.consecutive_wins += 1
            self.state.wins_count += 1
        elif pnl_units < -epsilon:
            result = TradeResult.LOSS
            self.state.consecutive_wins = 0
            self.state.losses_count += 1
        else:
            result = TradeResult.BREAKEVEN
            self.state.draws_count += 1

        self.state.last_trade_result = result

        if result == TradeResult.WIN:
            # Tras una ganancia, la apuesta aumenta en 1 unidad base.
            self.state.current_position_size += self.base_unit
        elif result == TradeResult.LOSS:
            # Tras una pérdida, la apuesta se mantiene igual.
            pass

        # Si la sesión alcanza un PnL de +1 o más, se reinicia la secuencia.
        if self.state.session_pnl >= 1.0:
            self.state.current_position_size = self.base_unit

        self.state.current_position_size = max(self.base_unit, min(self.state.current_position_size, self.max_position_size))

        logger.debug(
            "OscarGrind -> Resultado registrado %.4f unidades | próximo size %.4f | pnl acumulado %.4f",
            pnl_units,
            self.state.current_position_size,
            self.state.session_pnl,
        )

        self._check_session_limits()

    def get_session_summary(self) -> Dict[str, Any]:
        progress_pct = (self.state.session_pnl / self.profit_target * 100.0) if self.profit_target else 0.0
        wins = self.state.wins_count
        losses = self.state.losses_count
        draws = self.state.draws_count
        decided = wins + losses
        winrate_pct = (wins / decided * 100.0) if decided > 0 else 0.0
        return {
            "status": self.state.status.value,
            "current_position_size": self.state.current_position_size,
            "session_pnl": self.state.session_pnl,
            "consecutive_wins": self.state.consecutive_wins,
            "last_trade_result": self.state.last_trade_result.value,
            "trades_count": self.state.trades_count,
            "progress_to_target_pct": progress_pct,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "winrate_pct": winrate_pct,
        }
