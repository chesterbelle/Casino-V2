"""
💰 BalanceManager
-----------------
Administra el capital del jugador. 
Actualiza equity, PnL y mantiene trazabilidad de operaciones.
"""

class BalanceManager:
    def __init__(self, starting_balance: float):
        self.balance = starting_balance
        self.equity = starting_balance
        self.history = []

    def apply_trade_result(self, pnl: float, fee: float):
        """Aplica el resultado de una operación."""
        self.balance += pnl - fee
        self.equity = self.balance
        self.history.append({"pnl": pnl, "fee": fee, "equity": self.equity})

    def can_open_position(self, risk_amount: float) -> bool:
        """Verifica si el jugador puede arriesgar ese monto."""
        return risk_amount <= self.balance

    def get_state(self):
        """Snapshot actual del capital."""
        return {
            "balance": round(self.balance, 4),
            "equity": round(self.equity, 4),
            "trades": len(self.history)
        }

