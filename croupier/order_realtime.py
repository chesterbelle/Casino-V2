"""
🎲 OrderRealtime
----------------
Usado en modo live trading. 
El Crupier no ejecuta directamente; llama al método de la mesa realtime.
"""

from tables.table_base import BaseTable

class OrderRealtime:
    def __init__(self, realtime_table: BaseTable):
        self.table = realtime_table

    def execute(self, order: dict) -> dict:
        """Ejecuta una orden real mediante el feed activo (API)."""
        return self.table.execute_order(order)

