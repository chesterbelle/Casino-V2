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
from tables.table_aster_paper import TableAsterPaper
from tables.table_kraken_paper import TableKrakenPaper
from tables.table_binance_paper import TableBinancePaper


class BrokerInterface:
    """
    Crea y administra el acceso a una mesa del Casino.
    Ofrece una interfaz unificada: self.engine.table
    """

    def __init__(
        self,
        csv_path: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
    ):
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
        exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()
        if interval:
            self.interval = interval
        elif "KRAKEN" in exchange:
            self.interval = getattr(config, "KRAKEN_FUTURES_INTERVAL", "1m")
        elif "BINANCE" in exchange:
            self.interval = getattr(config, "BINANCE_DEFAULT_INTERVAL", "15m")
        else:
            self.interval = getattr(config, "ASTER_DEFAULT_INTERVAL", "1m")

        if self.mode == "backtest":
            if not csv_path:
                raise ValueError("BrokerInterface(backtest) requiere csv_path.")
            self.logger.info(f"🎬 Iniciando mesa BACKTEST con dataset: {csv_path}")
            self.engine = self._create_backtest_engine(csv_path, symbol)

        elif self.mode == "live":
            self.logger.info("🚀 Iniciando mesa LIVE (config.EXCHANGE=%s)", exchange)
            self.engine = self._create_live_engine(symbol, self.interval, exchange)

        else:
            raise ValueError(f"Modo desconocido en config.MODE: {self.mode}")

    def set_margin_type(self, symbol: str, margin_type: str) -> None:
        """Set margin type on the underlying engine if supported."""
        if hasattr(self.engine, "set_margin_type") and callable(getattr(self.engine, "set_margin_type")):
            try:
                # We pass the original, user-provided symbol, not the normalized one from the table
                self.engine.set_margin_type(symbol=symbol, margin_type=margin_type)
                self.logger.info(f"Margin type for {symbol} set to {margin_type}")
            except Exception as e:
                self.logger.error(f"Failed to set margin type for {symbol} to {margin_type}: {e}")
        else:
            self.logger.warning(
                f"Exchange engine {type(self.engine).__name__} does not support setting margin type."
            )

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

    def _create_live_engine(self, symbol: str | None, interval: str | None, exchange: str):
        """
        Construye la mesa realtime según el exchange configurado.
        """
        exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()

        class Engine:
            def __init__(self, symbol, interval):
                if "ASTER" in exchange:
                    self.table = TableAsterPaper(symbol=symbol, interval=interval)
                elif "KRAKEN" in exchange:
                    self.table = TableKrakenPaper(symbol=symbol, interval=interval)
                elif "BINANCE" in exchange:
                    self.table = TableBinancePaper(symbol=symbol, interval=interval)
                else:
                    raise NotImplementedError(f"Exchange LIVE no soportado: {exchange}")

        return Engine(symbol, interval)
