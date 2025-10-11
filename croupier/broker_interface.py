"""
====================================================
🤝 BrokerInterface — Coordinador entre Croupier y Mesa
====================================================

Rol:
----
Este módulo actúa como el "jefe de piso" del Casino:
su trabajo es entregar al Croupier una mesa (feed)
correctamente configurada, sin importar su origen.

En modo BACKTEST:
    - Crea una TableBacktest leyendo un CSV histórico.

En modo LIVE:
    - (Futuro) Creará una TableRealtime conectada a la API.

Así, el resto del sistema (Gemini, Croupier, Main)
puede operar sin preocuparse del origen de los datos.

====================================================
🔧 Puntos de extensión:
----------------------
• Para integrar otro exchange, crea una nueva mesa en tables/
  (ej. TableBybit, TableBitget) y añade su import aquí.
• Para modo realtime, implementar TableRealtime en tables/.
"""

import logging
import config

# Importaciones condicionales (según modo)
from tables.table_backtest import TableBacktest
# En el futuro: from tables.table_realtime import TableRealtime


class BrokerInterface:
    """
    Crea y administra el acceso a una mesa del Casino.
    Ofrece una interfaz unificada: self.engine.table
    """

    def __init__(self, csv_path: str | None = None, symbol: str | None = None):
        """
        Inicializa el broker. Según el modo de config.py,
        crea la mesa correspondiente.

        Parámetros:
        ------------
        csv_path : str
            Ruta al dataset histórico (modo backtest)
        symbol : str | None
            Nombre opcional del símbolo (BTCUSDT, LTCUSDT, etc.)
        """
        self.logger = logging.getLogger("BrokerInterface")
        self.mode = getattr(config, "MODE", "backtest").lower()

        if self.mode == "backtest":
            if not csv_path:
                raise ValueError("BrokerInterface(backtest) requiere csv_path.")
            self.logger.info(f"🎬 Iniciando mesa BACKTEST con dataset: {csv_path}")
            self.engine = self._create_backtest_engine(csv_path, symbol)

        elif self.mode == "live":
            # Placeholder futuro
            self.logger.info("🚀 Iniciando mesa LIVE (placeholder)")
            self.engine = self._create_live_engine(symbol)

        else:
            raise ValueError(f"Modo desconocido en config.MODE: {self.mode}")

    # ----------------------------------------------------
    # 🪙 Creación de motores (mesas)
    # ----------------------------------------------------
    def _create_backtest_engine(self, csv_path: str, symbol: str | None):
        """
        Crea una instancia del motor de backtest
        y la expone con la estructura esperada.
        """
        class Engine:
            def __init__(self, csv_path, symbol):
                self.table = TableBacktest(csv_path=csv_path, symbol=symbol)

        return Engine(csv_path, symbol)

    def _create_live_engine(self, symbol: str | None):
        """
        Placeholder para modo live — todavía no implementado.
        Mantiene misma estructura (self.table) para compatibilidad.
        """
        class Engine:
            def __init__(self, symbol):
                raise NotImplementedError("Modo LIVE aún no implementado en BrokerInterface.")
        return Engine(symbol)

