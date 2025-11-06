"""
🪙 Table Base
-------------
Interfaz abstracta para todas las mesas del casino (feeds de datos).

Define el contrato universal:
- next_candle() → entrega la siguiente vela normalizada.
- execute_order(order) → ejecuta o simula una orden.
"""

import abc
import json
import os
from typing import Dict, Optional


class BaseTable(abc.ABC):
    def __init__(self, exchange_profile="binance"):
        self.profile = self._load_profile(exchange_profile)
        self.balance_manager = None

    # =========================================================
    # 🔧 Configuración del perfil del exchange
    # =========================================================
    def _load_profile(self, name):
        path = f"tables/data/exchange_profiles/{name}.json"
        if not os.path.exists(path):
            raise FileNotFoundError(f"Perfil de exchange no encontrado: {path}")
        with open(path, "r") as f:
            return json.load(f)

    # =========================================================
    # 🔁 Métodos abstractos
    # =========================================================
    @abc.abstractmethod
    def next_candle(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Retorna la próxima vela normalizada para un símbolo específico o el primero por defecto.

        Args:
            symbol: Símbolo específico (opcional, usa primer símbolo si no se especifica)

        Returns:
            Dict con datos de vela o None si no disponible
        """
        pass

    @abc.abstractmethod
    def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta o simula la orden y devuelve el resultado estandarizado.

        Args:
            order: Orden en formato estándar

        Returns:
            Resultado normalizado de la ejecución
        """
        pass
