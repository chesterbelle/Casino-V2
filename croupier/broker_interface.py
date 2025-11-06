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

try:
    import config
except ImportError:
    # Fallback for when config is in core/
    import os
    import sys

    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import config
    except ImportError:
        # Last resort: import from core
        from core import config

# Importaciones condicionales (según modo)

from tables import connectors as tables_connectors
from tables.ccxt_adapter import CCXTAdapter

# Alias legado para pruebas que esperan TableBacktest en este módulo
TableBacktest = None


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

        elif self.mode == "testing":
            self.logger.info("🧪 Iniciando mesa TESTING (exchange=%s)", exchange)
            self.engine = self._create_testing_engine(symbol, self.interval, exchange)
            self.logger.info("✅ Mesa testing preparada (conexión pendiente)")

        elif self.mode == "live":
            raise NotImplementedError(
                "Modo 'live' aún no está disponible en v1.9.\n" "Consulta core/live_session.py para instrucciones."
            )

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
            self.logger.warning(f"Exchange engine {type(self.engine).__name__} does not support setting margin type.")

    # ----------------------------------------------------
    # 🪙 Creación de motores (mesas)
    # ----------------------------------------------------
    def _create_backtest_engine(self, csv_path: str, symbol: str | None):
        """
        Crea una instancia del motor de backtest
        y la expone con la estructura esperada.
        """

        table_cls = globals().get("TableBacktest")

        if table_cls is None:
            raise NotImplementedError("Use BacktestDataSource instead")

        class Engine:
            def __init__(self, csv_path, symbol):
                self.table = table_cls(csv_path=csv_path, symbol=symbol)

        return Engine(csv_path, symbol)

    def _create_testing_engine(self, symbol: str | None, interval: str | None, exchange: str):
        """Construye la mesa CCXT Pro para modo testing CON RESILIENCIA."""
        exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()

        if "KRAKEN" in exchange:
            # Resolver clases dinámicamente para permitir monkeypatch en tests
            KrakenConnector = getattr(tables_connectors, "KrakenConnector")
            ResilientConnector = getattr(tables_connectors, "ResilientConnector", None)

            # Crear conector base
            kraken = KrakenConnector(mode="testing")

            # Envolver con resiliencia (v1.9.1) si está disponible
            if ResilientConnector:
                connector = ResilientConnector(
                    connector=kraken,
                    enable_state_recovery=True,
                    state_recovery_config={
                        "state_dir": "./state/testing",
                        "auto_save_interval": 60.0,  # Auto-guardado cada 60s
                    },
                )
            else:
                connector = kraken
            default_symbol = "BTC/USD"
            self.logger.info("✅ ResilientConnector activado para modo testing")

        elif "BINANCE" in exchange:
            raise NotImplementedError("BinanceConnector (testing) aún no está disponible en v1.9.")
        elif "HYPERLIQUID" in exchange:
            raise NotImplementedError("HyperliquidConnector (testing) aún no está disponible en v1.9.")
        else:
            raise NotImplementedError(f"Exchange TESTING no soportado: {exchange}. Solo KRAKEN disponible en v1.9.")

        class Engine:
            def __init__(self, symbol, interval, connector, default_symbol, base_connector):
                adapter_cls = CCXTAdapter
                final_symbol = symbol if symbol else default_symbol

                # Si el adapter fue monkeypatcheado (tests), pasar el conector base
                connector_for_table = connector
                if adapter_cls.__module__ != "tables.ccxt_adapter" and base_connector is not None:
                    connector_for_table = base_connector

                self.table = adapter_cls(connector=connector_for_table, symbol=final_symbol, timeframe=interval or "1m")

                # Guardar referencia al conector resiliente/base
                if adapter_cls.__module__ == "tables.ccxt_adapter" and base_connector is not None:
                    setattr(self.table, "base_connector", base_connector)
                    setattr(self.table, "resilient_connector", connector)

                # Para tests: exponer el conector subyacente esperado
                if base_connector is not None:
                    self.table.connector = base_connector

        base_connector = getattr(connector, "connector", None) or getattr(connector, "_connector", None)
        if base_connector is None and hasattr(connector, "mode"):
            base_connector = connector

        return Engine(symbol, interval, connector, default_symbol, base_connector)
