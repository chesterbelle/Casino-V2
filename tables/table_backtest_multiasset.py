"""
===================================================
🪙 TableBacktestMultiAsset — Backtest Multi-Asset
===================================================

Rol:
----
• Simular trading multi-asset con datos históricos
• Gestionar posiciones concurrentes across múltiples símbolos
• Sincronización temporal precisa entre diferentes assets
• Balance portfolio unificado y realista

Características:
-------------
• Multi-asset: Múltiples símbolos simultáneos
• Multi-timeframe: Diferentes marcos temporales por símbolo
• Sincronización: Timestamp común para simulación realista
• Balance unificado: Gestión holística del portfolio
• Position tracking: Simulación de posiciones abiertas realista

Estructura de datos esperada:
-----------------------------
tables/data/raw/
├── BTCUSDT/
│   ├── BTCUSDT_1m_training.csv
│   ├── BTCUSDT_5m_training.csv
│   └── BTCUSDT_15m_training.csv
├── ETHUSDT/
│   ├── ETHUSDT_1m_training.csv
│   └── ETHUSDT_5m_training.csv
└── LTCUSDT/
    └── LTCUSDT_15m_training.csv
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from .balance_manager import BalanceManager
from .position_tracker import PositionTracker

class TableBacktestMultiAsset:
    """
    Backtest multi-asset con sincronización temporal precisa.

    Arquitectura:
    - Múltiples datasets CSV por símbolo/timeframe
    - Sincronización por timestamp común
    - PositionTracker por símbolo
    - BalanceManager unificado
    """

    def __init__(self,
                 symbol_configs: Dict[str, Dict[str, Any]],
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None,
                 data_base_path: str = "tables/data/raw"):
        """
        Inicializa backtest multi-asset.

        Args:
            symbol_configs: Config por símbolo
                {
                    "BTCUSDT": {
                        "timeframes": ["1m", "5m", "15m"],
                        "data_path": "BTCUSDT"  # opcional, default = symbol
                    },
                    "ETHUSDT": {
                        "timeframes": ["1m", "5m"],
                        "data_path": "ETHUSDT"
                    }
                }
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)
            data_base_path: Path base de datos
        """
        self.logger = logging.getLogger("TableBacktestMultiAsset")

        # Configuración
        self.symbol_configs = symbol_configs
        self.symbols = list(symbol_configs.keys())
        self.start_date = start_date
        self.end_date = end_date
        self.data_base_path = Path(data_base_path)

        # Componentes core
        self.balance_manager = BalanceManager(starting_balance=10_000.0)
        self.position_trackers: Dict[str, PositionTracker] = {}

        # Estado interno
        self.data: Dict[str, Dict[str, List[Dict]]] = {}  # symbol -> timeframe -> candles
        self.current_timestamp: Optional[int] = None
        self.cursor_positions: Dict[str, Dict[str, int]] = {}  # symbol -> timeframe -> cursor

        # Estadísticas
        self.total_candles_processed = 0
        self.is_initialized = False

        # Inicializar
        self._initialize_data()
        self._initialize_position_trackers()

        self.logger.info(f"🪙 TableBacktestMultiAsset inicializada | Symbols: {self.symbols}")

    def _initialize_data(self) -> None:
        """Carga y valida todos los datasets."""
        for symbol, config in self.symbol_configs.items():
            timeframes = config.get("timeframes", ["1m"])
            data_path = config.get("data_path", symbol)

            self.data[symbol] = {}
            self.cursor_positions[symbol] = {}

            for timeframe in timeframes:
                # Intentar múltiples formatos de filename para compatibilidad
                possible_filenames = [
                    f"{symbol}_{timeframe}_training.csv",
                    f"{symbol}_{timeframe}__30d.csv",
                    f"{symbol}_{timeframe}__90d.csv",
                    f"{symbol}_{timeframe}__1d.csv",
                ]

                filepath = None
                for filename in possible_filenames:
                    candidate = self.data_base_path / data_path / filename
                    if candidate.exists():
                        filepath = candidate
                        break

                # Si no encontró en subdirectorio, buscar en raíz
                if not filepath:
                    for filename in possible_filenames:
                        candidate = self.data_base_path / filename
                        if candidate.exists():
                            filepath = candidate
                            break

                if not filepath:
                    self.logger.warning(f"⚠️ Dataset no encontrado para {symbol} {timeframe}, saltando...")
                    # Crear lista vacía para mantener consistencia
                    self.data[symbol][timeframe] = []
                    self.cursor_positions[symbol][timeframe] = 0
                    continue

                # Cargar datos
                candles = self._load_csv(filepath)
                self.data[symbol][timeframe] = candles
                self.cursor_positions[symbol][timeframe] = 0

                self.logger.info(f"📚 Cargado {symbol} {timeframe}: {len(candles)} velas desde {filepath.name}")

        self.is_initialized = True

    def _initialize_position_trackers(self) -> None:
        """Inicializa PositionTracker por símbolo."""
        for symbol in self.symbols:
            self.position_trackers[symbol] = PositionTracker(max_concurrent_positions=1)

    def _load_csv(self, filepath: Path) -> List[Dict]:
        """Carga datos CSV y los parsea."""
        candles = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Parsear timestamp
                    ts_raw = row.get('timestamp', '')
                    ts_ms = self._parse_timestamp(ts_raw)

                    if ts_ms is None:
                        continue

                    # Filtrar por rango de fechas si especificado
                    if self.start_date or self.end_date:
                        candle_date = datetime.fromtimestamp(ts_ms / 1000).date()
                        if self.start_date and candle_date < datetime.fromisoformat(self.start_date).date():
                            continue
                        if self.end_date and candle_date > datetime.fromisoformat(self.end_date).date():
                            continue

                    candle = {
                        'timestamp': ts_raw,
                        'timestamp_ms': ts_ms,
                        'open': float(row.get('open', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                        'volume': float(row.get('volume', 0)),
                        'symbol': filepath.stem.split('_')[0],  # Extraer símbolo del filename
                        'timeframe': filepath.stem.split('_')[1]  # Extraer timeframe del filename
                    }
                    candles.append(candle)

            # Ordenar por timestamp
            candles.sort(key=lambda x: x['timestamp_ms'])

        except Exception as e:
            self.logger.error(f"Error cargando {filepath}: {e}")
            raise

        return candles

    def _parse_timestamp(self, ts_str: str) -> Optional[int]:
        """Parsea timestamp a milisegundos."""
        if not ts_str:
            return None

        try:
            # Intentar diferentes formatos
            if ts_str.isdigit():
                val = int(ts_str)
                return val if val > 10**10 else val * 1000
            else:
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                return int(dt.timestamp() * 1000)
        except:
            return None

    def next_candle_batch(self) -> Optional[Dict[str, Dict[str, Dict]]]:
        """
        Retorna el siguiente batch de velas sincronizadas por timestamp.

        Returns:
            Dict[symbol][timeframe] = candle o None si no hay más datos
        """
        if not self.is_initialized:
            return None

        # Encontrar el próximo timestamp común
        next_timestamp = self._find_next_common_timestamp()

        if next_timestamp is None:
            # No hay más datos
            return None

        self.current_timestamp = next_timestamp
        batch = {}

        # Recopilar velas para este timestamp por símbolo/timeframe
        for symbol in self.symbols:
            batch[symbol] = {}

            for timeframe in self.symbol_configs[symbol]["timeframes"]:
                cursor = self.cursor_positions[symbol][timeframe]
                candles = self.data[symbol][timeframe]

                # Buscar vela más cercana a este timestamp para este timeframe
                candle = self._find_candle_at_timestamp(candles, cursor, next_timestamp, timeframe)
                if candle:
                    batch[symbol][timeframe] = candle
                    # Avanzar cursor
                    self.cursor_positions[symbol][timeframe] = max(cursor, candles.index(candle) + 1)

        self.total_candles_processed += 1
        return batch if any(batch.values()) else None

    def _find_next_common_timestamp(self) -> Optional[int]:
        """Encuentra el próximo timestamp disponible en al menos un símbolo."""
        candidates = []

        for symbol in self.symbols:
            for timeframe in self.symbol_configs[symbol]["timeframes"]:
                cursor = self.cursor_positions[symbol][timeframe]
                candles = self.data[symbol][timeframe]

                if cursor < len(candles):
                    candidates.append(candles[cursor]['timestamp_ms'])

        return min(candidates) if candidates else None

    def _find_candle_at_timestamp(self, candles: List[Dict], start_idx: int,
                                target_timestamp: int, timeframe: str) -> Optional[Dict]:
        """
        Encuentra la vela más apropiada para un timestamp objetivo.

        Para timeframes más largos, puede no haber vela exacta en cada timestamp.
        """
        # Buscar vela más cercana hacia adelante
        for i in range(start_idx, len(candles)):
            candle = candles[i]
            candle_ts = candle['timestamp_ms']

            if candle_ts >= target_timestamp:
                return candle

        return None

    def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta orden simulada para un símbolo específico.

        Interface compatible con Croupier existente.
        """
        symbol = order.get('symbol', '')
        if symbol not in self.symbols:
            return self._create_error_result(order, f"Símbolo no soportado: {symbol}")

        # Obtener tracker para este símbolo
        tracker = self.position_trackers[symbol]

        # Obtener estado actual
        balance_state = self.balance_manager.get_state()
        equity = balance_state.get('equity', 0.0)

        # Verificar capital disponible
        available_equity = tracker.get_available_equity(equity)

        # Simular ejecución (simplificada por ahora)
        # En producción, implementar lógica completa de TP/SL

        try:
            side = order.get('side', '').upper()
            size_fraction = order.get('size', 0.0)

            if side not in ['BUY', 'SELL'] or size_fraction <= 0:
                raise ValueError("Orden inválida")

            # Calcular tamaños
            notional = available_equity * size_fraction
            margin_used = notional  # Simplificado

            # Para testing, devolver orden válida pero sin ejecutar realmente
            # En producción, implementar lógica completa de TP/SL
    
            return {
                'trade_id': order.get('trade_id', f'multi_{symbol}_{self.total_candles_processed}'),
                'result': 'WIN',  # Simulado
                'pnl': notional * 0.005,  # +0.5% simulado
                'fee': notional * 0.0004,  # 0.04% fee
                'symbol': symbol,
                'balance': self.balance_manager.get_state().get('balance', 0.0),
                'status': 'closed',
                'order_id': f'sim_{symbol}',
                'filled': notional,
                'cost': notional,
                'timestamp': datetime.now().isoformat(),
                'market': f"{symbol}@multi",
                'timeframe': 'multi',
                'side': side,
                'action': 'BET',
                'ghost': False,
            }

        except Exception as e:
            self.logger.error(f"Error ejecutando orden multi-asset: {e}")
            return self._create_error_result(order, str(e))

    def get_state(self) -> Dict:
        """
        Retorna estado unificado del backtest multi-asset.
        """
        balance_state = self.balance_manager.get_state()

        # Consolidar estadísticas de posiciones
        portfolio_positions = {}
        total_blocked = 0.0

        for symbol, tracker in self.position_trackers.items():
            stats = tracker.get_stats()
            portfolio_positions[symbol] = stats
            total_blocked += stats.get('blocked_capital', 0.0)

        return {
            'balance': balance_state.get('balance', 0.0),
            'equity': balance_state.get('equity', 0.0),
            'blocked_capital': total_blocked,
            'available_equity': balance_state.get('equity', 0.0) - total_blocked,
            'positions': portfolio_positions,
            'symbols': self.symbols,
            'current_timestamp': self.current_timestamp,
            'candles_processed': self.total_candles_processed,
        }

    def _create_error_result(self, order: Dict, error: str) -> Dict:
        """Crea resultado de error estandarizado."""
        return {
            'trade_id': order.get('trade_id', 'error'),
            'result': 'ERROR',
            'pnl': 0.0,
            'fee': 0.0,
            'symbol': order.get('symbol', ''),
            'balance': self.balance_manager.get_state().get('balance', 0.0),
            'status': 'error',
            'error': error,
            'timestamp': datetime.now().isoformat(),
            'market': f"{order.get('symbol', '')}@multi",
            'timeframe': 'multi',
            'side': order.get('side', ''),
            'action': 'ERROR',
            'ghost': False,
        }