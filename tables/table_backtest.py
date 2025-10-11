"""
====================================================
🪙 TableBacktest — Mesa sobre CSV para Casino V2
====================================================

Rol:
----
• Proveer velas históricas desde un CSV (backtest “rápido”).
• Ejecutar órdenes del Croupier con lógica de TP/SL sobre velas futuras.
• Aplicar fees y (opcionalmente) slippage al PnL monetario.
• Mantener y reportar el balance a través de BalanceManager.

Importante:
-----------
• El Croupier SIEMPRE opera; el “modo simulado” existe solo aquí (feed),
  a través del flag `order["ghost"]`.
• Si ghost=True: se determina WIN/LOSS, pero NO se altera el balance.
• Si ghost=False: se aplica PnL + fees y se actualiza el balance.

CSV esperado (cabecera):
------------------------
timestamp,open,high,low,close,volume

Configuración leída desde config.py:
------------------------------------
• TAKE_PROFIT (R)         • STOP_LOSS (L)
• COMMISSION_RATE         • SLIPPAGE_DEFAULT (opcional)
"""

from __future__ import annotations

import csv
import math
import logging
import os
import re
from typing import List, Dict, Optional, Tuple

import config
from .balance_manager import BalanceManager

class TableBacktest:
    """
    Backtest secuencial vela-por-vela.
    next_candle() avanza un índice interno.
    execute_order() simula TP/SL a partir de la vela actual hacia adelante.
    """

    def __init__(self, csv_path: str, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        self.logger = logging.getLogger("TableBacktest")
        self.csv_path = csv_path
        inferred_symbol, inferred_timeframe = self._infer_market_from_path(csv_path)
        self.symbol = symbol or inferred_symbol
        self.timeframe = timeframe or inferred_timeframe
        self.market_id = f"{self.symbol}@{self.timeframe}" if self.timeframe != "UNKNOWN" else self.symbol
        self.data: List[Dict] = self._load_csv(csv_path)
        self.n = len(self.data)
        self._cursor = 0           # índice de la PROXIMA vela a entregar
        self._last_index = -1      # última vela entregada (para saber desde dónde simular)
        self.balance_manager = BalanceManager(starting_balance=getattr(config, "STARTING_BALANCE", 10_000.0))

        # Parámetros de costos
        self.fee_rate = getattr(config, "COMMISSION_RATE", 0.0004)     # por lado; total ~ 2*fee_rate
        self.slippage = getattr(config, "SLIPPAGE_DEFAULT", 0.0)

        # RR por defecto (si la orden no define sus factores)
        self.R = getattr(config, "TAKE_PROFIT", 0.01)
        self.L = getattr(config, "STOP_LOSS", 0.01)

        if self.n == 0:
            raise ValueError(f"Dataset vacío: {csv_path}")

        self.logger.info(
            f"📚 CSV cargado: {csv_path} | velas: {self.n} | símbolo: {self.symbol} | timeframe: {self.timeframe}"
        )

    # ----------------------------------------------------
    # API de consumo de velas
    # ----------------------------------------------------
    def next_candle(self) -> Optional[Dict]:
        """Devuelve la siguiente vela y avanza el cursor."""
        if self._cursor >= self.n:
            return None
        row = self.data[self._cursor]
        self._last_index = self._cursor
        self._cursor += 1

        # Reportar junto con balance actual (estandarizado)
        state = self.get_state()
        return {
            "timestamp": row["timestamp"],
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "market": self.market_id,
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "equity": state.get("equity"),
            "balance": state.get("balance"),
        }

    # ----------------------------------------------------
    # API de ejecución para el Croupier
    # ----------------------------------------------------
    def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta TP/SL a partir de la vela actual hacia adelante.
        • La entrada se asume al PRECIO DE CIERRE de la última vela entregada,
          con un ajuste simple por slippage (si se desea).
        • Se evalúa la secuencia de velas futuras hasta que toque TP o SL.
        • Se aplican fees (entrada + salida) sobre el notional de la posición.
        • Si 'ghost'==True → no modifica el balance (entrena sin riesgo).

        Retorna resultado normalizado:
        {
          "trade_id": str,
          "result": "WIN"|"LOSS",
          "pnl": float,            # monetario aplicado (0 si ghost)
          "fee": float,
          "symbol": str,
          "balance": float | None  # balance nuevo si no es ghost
        }
        """
        # Validación mínima
        side = order.get("side", "").upper()
        size_fraction = float(order.get("size", 0.0))
        ghost = bool(order.get("ghost", False))
        trade_id = order.get("trade_id")
        symbol = order.get("symbol", self.symbol)

        if self._last_index < 0:
            raise RuntimeError("No hay vela de referencia para ejecutar (llama a next_candle() primero).")

        # Precio de entrada (close de la última vela entregada), con slippage simple
        entry_candle = self.data[self._last_index]
        entry_price = float(entry_candle["close"])
        if self.slippage > 0:
            # 🔧 PUNTO DE EXTENSIÓN: refina la modelación de slippage
            entry_price *= (1 + self.slippage) if side == "LONG" else (1 - self.slippage)

        # Factores de TP/SL (si no vienen en la orden, usar config)
        tp_factor = float(order.get("take_profit", 1.0 + self.R))
        sl_factor = float(order.get("stop_loss", 1.0 - self.L))

        # Niveles objetivo
        if side == "LONG":
            tp_level = entry_price * tp_factor
            sl_level = entry_price * sl_factor
        elif side == "SHORT":
            # Para corto: TP por debajo, SL por encima
            # tp_factor ~ (1 - R), sl_factor ~ (1 + L)
            tp_level = entry_price * (2 - tp_factor) if tp_factor > 1 else entry_price * tp_factor
            sl_level = entry_price * (2 - sl_factor) if sl_factor < 1 else entry_price * sl_factor
        else:
            raise ValueError(f"Side inválido: {side}")

        # Buscar el primer toque: conservador => SL tiene prioridad si se cruzan en la misma vela
        outcome = self._walk_to_outcome(side, start_index=self._last_index + 1,
                                        tp_level=tp_level, sl_level=sl_level)

        # Cálculo monetario (solo si no es ghost)
        fee_total = 0.0
        pnl_value = 0.0
        balance_after = None

        if not ghost:
            state = self.balance_manager.get_state()
            equity = float(state.get("equity", state.get("balance", 0.0)))
            notional = max(0.0, equity * size_fraction)

            # Fees: entrada + salida (taker)
            fee_total = notional * (2 * self.fee_rate)

            # PnL bruto por R/L (usamos R y L de config para cuantificar el resultado)
            # Nota: determinamos WIN/LOSS por niveles, pero cuantificamos % por R o L simétrico.
            if outcome == "WIN":
                pnl_pct = self.R
            else:
                pnl_pct = -self.L

            pnl_value = notional * pnl_pct
            pnl_net = pnl_value - fee_total

            # Actualizar balance
            try:
                # 🔧 PUNTO DE EXTENSIÓN: si tu BalanceManager expone otro método, ajústalo aquí
                self.balance_manager.balance += pnl_net
            except Exception:
                # fallback si la propiedad no es accesible
                s = self.balance_manager.get_state()
                base = float(s.get("balance", 0.0)) + pnl_net
                if hasattr(self.balance_manager, "set_balance"):
                    self.balance_manager.set_balance(base)

            balance_after = float(self.balance_manager.get_state().get("balance", 0.0))

        # Resultado normalizado
        return {
            "trade_id": trade_id,
            "result": outcome,
            "pnl": float(pnl_value if not ghost else 0.0),
            "fee": float(fee_total if not ghost else 0.0),
            "symbol": symbol,
            "balance": balance_after
        }

    # ----------------------------------------------------
    # Estado
    # ----------------------------------------------------
    def get_state(self) -> Dict:
        """
        Devuelve estado estándar para el main/croupier/sensores.
        """
        s = self.balance_manager.get_state()
        # Asegurar claves
        return {
            "balance": float(s.get("balance", 0.0)),
            "equity": float(s.get("equity", s.get("balance", 0.0)))
        }

    # ----------------------------------------------------
    # Internos
    # ----------------------------------------------------
    def _walk_to_outcome(self, side: str, start_index: int, tp_level: float, sl_level: float) -> str:
        """
        Recorre velas futuras hasta que toque TP o SL. Política conservadora:
        • LONG : si en una vela se tocan ambos, se asume SL primero.
        • SHORT: idem (SL tiene prioridad).
        """
        # Seguridad: no salirnos del dataset
        for i in range(start_index, self.n):
            c = self.data[i]
            high = float(c["high"])
            low = float(c["low"])

            if side == "LONG":
                # Priorizamos SL si low cruza primero
                if low <= sl_level:
                    return "LOSS"
                if high >= tp_level:
                    return "WIN"
            else:  # SHORT
                if high >= sl_level:
                    return "LOSS"
                if low <= tp_level:
                    return "WIN"

        # Si nunca tocó (fin del dataset): cerramos por último precio (conservador = LOSS)
        return "LOSS"

    def _load_csv(self, path: str) -> List[Dict]:
        out: List[Dict] = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    out.append({
                        "timestamp": row.get("timestamp") or row.get("date") or row.get("time") or "",
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row.get("volume", 0.0)),
                    })
                except Exception:
                    # Saltar filas corruptas
                    continue
        return out

    def _infer_market_from_path(self, path: str) -> Tuple[str, str]:
        """
        Intenta inferir símbolo y timeframe desde el nombre del archivo.
        Ejemplo: 'LTCUSDT_15min_bull.csv' → ('LTCUSDT', '15min')
        """
        fname = os.path.basename(path)
        base = fname.split(".")[0]
        parts = base.split("_") if base else []

        symbol = parts[0] if parts else "UNKNOWN"
        timeframe = "UNKNOWN"

        timeframe_pattern = re.compile(r"^\d+(min|m|h|d|wk|mo)$", re.IGNORECASE)
        for part in parts[1:]:
            token = part.lower()
            if timeframe_pattern.match(token):
                timeframe = part
                break

        return symbol or "UNKNOWN", timeframe
