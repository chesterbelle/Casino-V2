"""
====================================================
🧤 Croupier — Ejecutor imparcial del Casino V2
====================================================

Rol:
----
• Recibe una orden estandarizada desde Gemini.
• La enruta a la mesa activa (feed) — sin saber si es backtest o live.
• Devuelve un resultado normalizado, incluyendo balance reportado por la mesa.

Contrato mínimo de la mesa (feed):
----------------------------------
self.table debe exponer:
    - execute_order(order: dict) -> dict
      * Debe respetar el flag order["ghost"] para shadow trading.
    - balance_manager.get_state() -> dict  (opcional, para logging)

La orden estandarizada esperada contiene:
-----------------------------------------
{
    "trade_id": str,
    "symbol": str,
    "side": "LONG" | "SHORT",
    "size": float,            # fracción del equity a arriesgar
    "take_profit": float,     # factor multiplicativo (ej. 1.01 => +1%)
    "stop_loss": float,       # factor multiplicativo (ej. 0.992 => -0.8%)
    "timestamp": str | None,
    "ghost": bool             # True = shadow (entrena sin tocar balance)
}
"""

from __future__ import annotations

import logging


class Croupier:
    def __init__(self, table):
        self.logger = logging.getLogger("Croupier")
        self.table = table

    def route_order(self, order: dict) -> dict:
        """
        Enruta la orden a la mesa.
        No valida origen de datos; la mesa decide cómo ejecutar.

        Retorna un dict normalizado, ejemplo:
        {
           "trade_id": "...",
           "result": "WIN" | "LOSS",
           "pnl": float,                 # PnL monetario aplicado (0 si ghost)
           "fee": float,                 # comisiones totales
           "symbol": str,
           "balance": float | None       # balance tras la ejecución (si no ghost)
        }
        """
        if not isinstance(order, dict):
            raise ValueError("Orden inválida: debe ser un dict estándar.")

        # 🔧 PUNTO DE EXTENSIÓN:
        # Si quieres validar más campos de la orden, hazlo aquí
        required = ("symbol", "side", "size", "take_profit", "stop_loss", "ghost")
        for k in required:
            if k not in order:
                raise ValueError(f"Orden incompleta: falta '{k}'")

        # Usar execute_order_sync si existe (para mesas async), sino execute_order
        if hasattr(self.table, "execute_order_sync"):
            result = self.table.execute_order_sync(order)
        else:
            result = self.table.execute_order(order)

        # Log estándar consolidado
        self.logger.debug(
            f"🃏 Exec | {order.get('symbol','?')} {order.get('side','?')} "
            f"| ghost={order.get('ghost', False)} | res={result.get('result','?')} "
            f"| exit={result.get('exit_reason','?')} | bars={result.get('bars_held', 0)} "
            f"| fee={result.get('fee', 0):.6f} | pnl={result.get('pnl', 0):.6f}"
        )
        return result
