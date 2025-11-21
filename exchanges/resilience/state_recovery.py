"""
StateRecovery - Recuperación de estado después de crashes/desconexiones.

Este módulo implementa:
- Guardado periódico de estado en disco
- Recuperación de posiciones del exchange
- Sincronización de balance real
- Continuación desde último punto conocido
- Detección de fills perdidos

Author: Casino V2 Team
Version: 2.0.0
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..connectors.connector_base import BaseConnector

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Estado de una sesión de trading."""

    session_id: str
    player_name: str
    symbol: str
    timeframe: str
    start_time: float
    last_update: float
    candles_processed: int
    balance: float
    equity: float
    open_positions: List[Dict[str, Any]]
    closed_trades: List[Dict[str, Any]]
    last_candle_timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        """Crea desde diccionario."""
        return cls(**data)


class StateRecovery:
    """
    Gestiona recuperación de estado después de crashes.

    Features:
    - Guarda estado periódicamente en disco (JSON)
    - Recupera posiciones abiertas del exchange
    - Sincroniza balance real
    - Detecta fills perdidos durante desconexión
    - Continúa sesión desde último punto conocido

    Usage:
        ```python
        recovery = StateRecovery(
            connector=kraken_connector,
            state_dir="./state"
        )

        # Try to recover previous session
        state = await recovery.recover_session("session_123")

        if state:
            logger.info(f"Recuperando sesión con {len(state.open_positions)} posiciones")

        # Save state periodically
        await recovery.save_state(current_state)
        ```
    """

    def __init__(
        self,
        connector: BaseConnector,
        state_dir: str = "./state",
        auto_save_interval: float = 60.0,
    ):
        """
        Initialize StateRecovery.

        Args:
            connector: Exchange connector para sincronizar con exchange
            state_dir: Directorio para guardar estados
            auto_save_interval: Intervalo de auto-guardado (segundos)
        """
        self.logger = logging.getLogger("StateRecovery")
        self.connector = connector
        self.state_dir = Path(state_dir)
        self.auto_save_interval = auto_save_interval

        # Create state directory if it doesn't exist
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"📁 StateRecovery inicializado | dir={self.state_dir}")

    def _get_state_file(self, session_id: str) -> Path:
        """Retorna path del archivo de estado."""
        return self.state_dir / f"{session_id}.json"

    def _get_backup_file(self, session_id: str) -> Path:
        """Retorna path del archivo de backup."""
        return self.state_dir / f"{session_id}.backup.json"

    async def save_state(self, state: SessionState) -> bool:
        """
        Guarda estado en disco.

        Args:
            state: Estado actual de la sesión

        Returns:
            True si se guardó exitosamente
        """
        try:
            state_file = self._get_state_file(state.session_id)
            backup_file = self._get_backup_file(state.session_id)

            # Create backup of previous state
            if state_file.exists():
                try:
                    state_file.rename(backup_file)
                except Exception as e:
                    self.logger.warning(f"⚠️ No se pudo crear backup: {e}")

            # Save new state
            with open(state_file, "w") as f:
                json.dump(state.to_dict(), f, indent=2)

            self.logger.debug(f"💾 Estado guardado | session={state.session_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error guardando estado: {e}")
            return False

    async def load_state(self, session_id: str) -> Optional[SessionState]:
        """
        Carga estado desde disco.

        Args:
            session_id: ID de la sesión

        Returns:
            Estado cargado o None si no existe
        """
        try:
            state_file = self._get_state_file(session_id)

            if not state_file.exists():
                self.logger.info(f"📂 No hay estado guardado para session={session_id}")
                return None

            with open(state_file, "r") as f:
                data = json.load(f)

            state = SessionState.from_dict(data)
            self.logger.info(
                f"📂 Estado cargado | session={session_id} | "
                f"candles={state.candles_processed} | "
                f"positions={len(state.open_positions)}"
            )
            return state

        except Exception as e:
            self.logger.error(f"❌ Error cargando estado: {e}")

            # Try backup
            backup_file = self._get_backup_file(session_id)
            if backup_file.exists():
                try:
                    self.logger.info("🔄 Intentando cargar backup...")
                    with open(backup_file, "r") as f:
                        data = json.load(f)
                    return SessionState.from_dict(data)
                except Exception as e2:
                    self.logger.error(f"❌ Error cargando backup: {e2}")

            return None

    async def recover_session(self, session_id: str) -> Optional[SessionState]:
        """
        Recupera sesión completa sincronizando con exchange.

        Este método:
        1. Carga estado guardado en disco
        2. Sincroniza posiciones con exchange
        3. Sincroniza balance con exchange
        4. Detecta fills perdidos
        5. Retorna estado actualizado

        Args:
            session_id: ID de la sesión a recuperar

        Returns:
            Estado recuperado y sincronizado, o None si no se puede recuperar
        """
        self.logger.info(f"🔄 Recuperando sesión {session_id}...")

        # Load saved state
        saved_state = await self.load_state(session_id)

        if not saved_state:
            self.logger.info("No hay estado guardado para recuperar")
            return None

        # Sync with exchange
        try:
            # 1. Fetch real positions from exchange
            real_positions = await self.connector.fetch_positions()
            self.logger.info(f"📊 Posiciones reales del exchange: {len(real_positions)}")

            # 2. Fetch real balance
            real_balance = await self.connector.fetch_balance()
            real_equity = real_balance.get("total", {}).get("USD", saved_state.equity)
            self.logger.info(f"💰 Balance real: {real_equity:.2f} USD")

            # 3. Detect missing fills (trades that closed while disconnected)
            missing_fills = await self._detect_missing_fills(
                saved_state.open_positions, real_positions, saved_state.symbol
            )

            if missing_fills:
                self.logger.warning(f"⚠️ Detectados {len(missing_fills)} fills perdidos durante desconexión")
                # Add to closed trades
                saved_state.closed_trades.extend(missing_fills)

            # 4. Update state with real data
            saved_state.open_positions = self._normalize_positions(real_positions)
            saved_state.equity = real_equity
            saved_state.balance = real_balance.get("free", {}).get("USD", saved_state.balance)
            saved_state.last_update = datetime.now().timestamp()

            # Save updated state
            await self.save_state(saved_state)

            self.logger.info(
                f"✅ Sesión recuperada | "
                f"posiciones={len(saved_state.open_positions)} | "
                f"equity={saved_state.equity:.2f} USD"
            )

            return saved_state

        except Exception as e:
            self.logger.error(f"❌ Error sincronizando con exchange: {e}")
            # Return saved state even if sync failed
            return saved_state

    async def _detect_missing_fills(
        self, saved_positions: List[Dict[str, Any]], real_positions: List[Dict[str, Any]], symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Detecta fills que ocurrieron durante desconexión.

        Args:
            saved_positions: Posiciones guardadas antes de desconexión
            real_positions: Posiciones reales actuales del exchange
            symbol: Símbolo de trading

        Returns:
            Lista de fills perdidos
        """
        missing_fills = []

        # Create map of real positions by symbol
        real_pos_map = {pos["symbol"]: pos for pos in real_positions}

        # Check each saved position
        for saved_pos in saved_positions:
            pos_symbol = saved_pos.get("symbol")

            # If position is not in real positions, it was closed
            if pos_symbol not in real_pos_map:
                # Try to fetch fills from exchange
                try:
                    fills = await self.connector.fetch_my_trades(
                        symbol=pos_symbol, since=int(saved_pos.get("timestamp", 0))
                    )

                    # Find closing fill
                    for fill in fills:
                        # Check if this fill closed the position
                        if self._is_closing_fill(saved_pos, fill):
                            missing_fills.append(fill)
                            self.logger.info(
                                f"📝 Fill perdido detectado | " f"{pos_symbol} {fill.get('side')} @ {fill.get('price')}"
                            )
                            break

                except Exception as e:
                    self.logger.warning(f"⚠️ No se pudieron obtener fills para {pos_symbol}: {e}")

        return missing_fills

    def _is_closing_fill(self, position: Dict[str, Any], fill: Dict[str, Any]) -> bool:
        """
        Verifica si un fill cerró una posición.

        Args:
            position: Posición guardada
            fill: Fill del exchange

        Returns:
            True si el fill cerró la posición
        """
        # Check if sides are opposite (closing trade)
        pos_side = position.get("side", "").upper()
        fill_side = fill.get("side", "").upper()

        if pos_side == "LONG" and fill_side == "SELL":
            return True
        if pos_side == "SHORT" and fill_side == "BUY":
            return True

        return False

    def _normalize_positions(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normaliza posiciones del exchange a formato interno.

        Args:
            positions: Posiciones del exchange

        Returns:
            Posiciones normalizadas
        """
        normalized = []

        for pos in positions:
            # Skip positions with zero size
            if pos.get("size", 0) == 0:
                continue

            normalized.append(
                {
                    "symbol": pos.get("symbol"),
                    "side": pos.get("side"),
                    "size": pos.get("size"),
                    "entry_price": pos.get("entry_price"),
                    "mark_price": pos.get("mark_price"),
                    "unrealized_pnl": pos.get("unrealized_pnl"),
                    "timestamp": pos.get("timestamp"),
                }
            )

        return normalized

    def list_sessions(self) -> List[str]:
        """
        Lista todas las sesiones guardadas.

        Returns:
            Lista de session IDs
        """
        sessions = []

        for file in self.state_dir.glob("*.json"):
            if not file.name.endswith(".backup.json"):
                session_id = file.stem
                sessions.append(session_id)

        return sorted(sessions)

    def delete_session(self, session_id: str) -> bool:
        """
        Elimina estado guardado de una sesión.

        Args:
            session_id: ID de la sesión

        Returns:
            True si se eliminó exitosamente
        """
        try:
            state_file = self._get_state_file(session_id)
            backup_file = self._get_backup_file(session_id)

            if state_file.exists():
                state_file.unlink()

            if backup_file.exists():
                backup_file.unlink()

            self.logger.info(f"🗑️ Sesión eliminada | session={session_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error eliminando sesión: {e}")
            return False
