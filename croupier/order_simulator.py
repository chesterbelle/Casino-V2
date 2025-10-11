"""
🧮 OrderSimulator
-----------------
Usado en modo backtest. 
Recibe órdenes del Croupier y las ejecuta usando el TableBacktest.
"""

from tables.table_backtest import TableBacktest

class OrderSimulator:
    def __init__(self, csv_path, exchange_profile="binance"):
        self.table = TableBacktest(csv_path, exchange_profile)

    def execute(self, order: dict) -> dict:
        """Ejecuta una orden simulada en la mesa de backtest."""
        return self.table.execute_order(order)

