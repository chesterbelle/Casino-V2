# Changelog

## [Unreleased] - 2025-10-14

### Added
- **Gestor de Posiciones (`PositionManager`):** Se introdujo un nuevo módulo (`tables/position_manager.py`) para gestionar de forma explícita el estado de las posiciones abiertas en modo *live*.
- **Cierre de Posiciones en `TableKrakenPaper`:** Se añadió un nuevo método `close_open_position` para manejar el cierre de trades y el cálculo de PnL.

### Changed
- **Refactorización del Flujo de Trading en Vivo (Modo Oscar):**
    - El bucle principal en `oscar/session.py` ahora orquesta el ciclo completo de vida de una operación: monitorea posiciones abiertas para su cierre antes de buscar nuevas entradas.
    - `oscar/oscar_trader.py` fue refactorizado para enfocarse únicamente en la **decisión de entrada**, devolviendo una orden en lugar de ejecutarla.
    - `table_kraken_paper.py` ahora utiliza el `PositionManager` para registrar las posiciones abiertas a través de `execute_order`.
- **Precisión en Reporte de PnL:** La máquina de estados de Oscar Grind ahora clasifica explícitamente los empates (`BREAKEVEN`), mejorando la exactitud de las estadísticas de trading.

### Fixed
- **Cierre de Posiciones al Salir:** Se añadió lógica de limpieza a las sesiones en vivo (`live_session.py` y `oscar/session.py`) para asegurar que todas las posiciones abiertas se cierren al terminar el script (ej. con Ctrl+C), evitando dejar operaciones huérfanas.

## 2025-10-12 — Integración modalidad Oscar Grind

- Se añadió un paquete `oscar/` con los componentes exclusivos del modo Oscar:
  - `range_sensor.py`: sensor de rango autónomo reutilizando la lógica del bot Range Grinder.
  - `oscar_grind_machine.py`: state machine del método Oscar Grind para gestionar sesiones y sizing.
  - `oscar_trader.py`: orquestador que combina sensor + state machine y delega órdenes al croupier.
  - `session.py`: loop de backtest que reproduce el flujo del casino usando Oscar en lugar de Gemini.
- Se amplió `main.py` para habilitar el modo Oscar cuando `ENABLE_OSCAR_MODE=True`, manteniendo el flujo Gemini original como opción por defecto.
- `config.py` incorporó la bandera `ENABLE_OSCAR_MODE` y parámetros `OSCAR_*` para ajustar unidades y límites del método.
- Documentación interna actualizada explicando cómo activar el modo Oscar y mantener la modularidad con el pipeline existente.
- TableBacktest ahora lee el perfil de exchange para diferenciar fees de entrada/salida, aplicar slippage dinámico según tamaño y volatilidad, cobrar funding proporcional al tiempo en posición y simular liquidaciones por margen; los reportes muestran comisiones, funding y liquidaciones acumuladas.
- Nuevos scripts utilitarios en `utils/`:
  - `fetch_funding_rates.py` descarga tasas de funding históricas y las guarda en `tables/data/funding_rates/`.
  - `download_kline_dataset.py` permite obtener datasets adicionales de Binance Futures (pide símbolo base y días a descargar) guardándolos en `tables/data/raw/` sin pasar por `main.py`.