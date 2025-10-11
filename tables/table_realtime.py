"""
====================================================
⚡ TableRealtime — Mesa en vivo del Casino V2 (Binance Ready)
====================================================

Rol:
----
• Gestiona el flujo de datos reales (vía API) o placeholder.
• Permite ejecutar operaciones reales o simuladas.
• Mantiene la misma interfaz que TableBacktest:
  - next_candle()
  - execute_order(order)
  - balance_manager.get_state()

====================================================
🚀 Modos:
---------
1. **Simulado (sin API):**
   - Genera velas aleatorias para pruebas rápidas.
2. **Conectado (Binance Futures Testnet):**
   - Usa las claves API en tu `.env` o en config.py.
   - Requiere instalar python-binance:
       pip install python-binance

====================================================
🔧 Configuración esperada:
--------------------------
• API_KEY, API_SECRET en tu .env o config.py
• SYMBOL_DEFAULT = "BTCUSDT"
• COMMISSION_RATE, TAKE_PROFIT, STOP_LOSS

====================================================
💡 Ejemplo en config.py:
-------------------------
MODE = "live"
API_KEY = "tu_api_key_testnet"
API_SECRET = "tu_api_secret_testnet"
REALTIME_INTERVAL = "15m"
EXCHANGE = "BINANCE_FUTURES_TESTNET"
"""

import os
import time
import logging
import random
from typing import Dict, Optional

import config
from .balance_manager import BalanceManager

# Intentar importar la API de Binance si está disponible
try:
    from binance.client import Client
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False


class TableRealtime:
    """Mesa en vivo compatible con Binance Futures Testnet o modo simulado."""

    def __init__(self, symbol: str = None):
        self.logger = logging.getLogger("TableRealtime")

        # =============================
        # Configuración general
        # =============================
        self.symbol = symbol or getattr(config, "SYMBOL_DEFAULT", "BTCUSDT")
        self.interval = getattr(config, "REALTIME_INTERVAL", "15m")
        self.balance_manager = BalanceManager(starting_balance=getattr(config, "STARTING_BALANCE", 10_000.0))
        self.exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()

        # =============================
        # Intentar conexión con Binance
        # =============================
        self.api_connected = False
        self.client = None
        if BINANCE_AVAILABLE and "BINANCE" in self.exchange:
            api_key = getattr(config, "API_KEY", os.getenv("API_KEY"))
            api_secret = getattr(config, "API_SECRET", os.getenv("API_SECRET"))
            if api_key and api_secret:
                self.client = Client(api_key, api_secret, testnet="TESTNET" in self.exchange)
                self.api_connected = True
                self.logger.info(f"🔌 Conectado a {self.exchange} para {self.symbol}")
            else:
                self.logger.warning("⚠️ Claves API no configuradas. Usando modo simulado.")
        else:
            self.logger.info("🧪 Binance API no disponible. Usando modo simulado.")

    # ==========================================================
    # ⏱️ Feed de velas
    # ==========================================================
    def next_candle(self) -> Optional[Dict]:
        """Obtiene la próxima vela (real o simulada)."""
        time.sleep(1)

        if self.api_connected:
            candle = self._fetch_binance_candle()
        else:
            candle = self._fake_candle()

        if candle is None:
            return None

        state = self.get_state()
        candle.update({
            "symbol": self.symbol,
            "equity": state.get("equity"),
            "balance": state.get("balance"),
        })
        return candle

    def _fetch_binance_candle(self) -> Optional[Dict]:
        """Obtiene la vela más reciente desde Binance Futures Testnet."""
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval=self.interval, limit=1)
            if not klines:
                return None
            k = klines[0]
            return {
                "timestamp": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo vela: {e}")
            return None

    def _fake_candle(self) -> Dict:
        """Genera velas simuladas aleatorias (modo sin conexión)."""
        base = random.uniform(100, 120)
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": base - random.uniform(0, 0.3),
            "high": base + random.uniform(0, 0.5),
            "low": base - random.uniform(0, 0.5),
            "close": base + random.uniform(-0.2, 0.2),
            "volume": random.uniform(1, 20),
        }

    # ==========================================================
    # 💸 Ejecución de órdenes
    # ==========================================================
    def execute_order(self, order: Dict) -> Dict:
        """Ejecuta orden real o simulada y devuelve resultado normalizado."""
        side = order.get("side", "").upper()
        size = float(order.get("size", 0.0))
        ghost = bool(order.get("ghost", False))
        trade_id = order.get("trade_id")

        # Si es ghost, no ejecutamos nada real
        if ghost:
            return {
                "trade_id": trade_id,
                "result": "GHOST",
                "pnl": 0.0,
                "fee": 0.0,
                "symbol": self.symbol,
                "balance": self.balance_manager.get_state().get("balance"),
            }

        if self.api_connected:
            result = self._execute_binance_order(order)
        else:
            result = self._execute_fake_order(order)

        return result

    def _execute_binance_order(self, order: Dict) -> Dict:
        """Ejecuta una orden real en Binance Futures Testnet."""
        try:
            side = "BUY" if order["side"].upper() == "LONG" else "SELL"
            qty = max(order.get("size", 0.001), 0.001)
            response = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty,
            )
            self.logger.info(f"✅ Orden enviada a Binance: {response.get('orderId')}")
            # Placeholder simplificado — podrías mejorar para leer el resultado real.
            return {
                "trade_id": order.get("trade_id"),
                "result": "EXECUTED",
                "pnl": 0.0,
                "fee": 0.0,
                "symbol": self.symbol,
                "balance": self.balance_manager.get_state().get("balance"),
            }
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando orden real: {e}")
            return {"trade_id": order.get("trade_id"), "result": "ERROR", "pnl": 0.0, "fee": 0.0, "symbol": self.symbol}

    def _execute_fake_order(self, order: Dict) -> Dict:
        """Simula ejecución inmediata con resultado aleatorio."""
        side = order.get("side", "").upper()
        size = float(order.get("size", 0.0))
        win = random.random() > 0.5
        pnl_pct = getattr(config, "TAKE_PROFIT", 0.01) if win else -getattr(config, "STOP_LOSS", 0.01)
        fee = size * getattr(config, "COMMISSION_RATE", 0.0004)
        pnl = size * pnl_pct - fee
        try:
            self.balance_manager.balance += pnl
        except Exception:
            pass
        result = "WIN" if win else "LOSS"
        return {
            "trade_id": order.get("trade_id"),
            "result": result,
            "pnl": pnl,
            "fee": fee,
            "symbol": self.symbol,
            "balance": self.balance_manager.get_state().get("balance"),
        }

    # ==========================================================
    # 📊 Estado
    # ==========================================================
    def get_state(self) -> Dict:
        """Devuelve balance/equity actuales."""
        s = self.balance_manager.get_state()
        return {
            "balance": float(s.get("balance", 0.0)),
            "equity": float(s.get("equity", s.get("balance", 0.0))),
        }

