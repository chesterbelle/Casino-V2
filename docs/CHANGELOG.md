# Changelog

## [1.7] - 2025-10-15

### Added
- **Arquitectura Core Refactorizada**: Módulos `core/` consolidados
- **Jerarquía Table Unificada**: Todas las Tables heredan de `BaseTable`
- **Type Safety Completo**: Type hints en todos los módulos core
- **Sistema de Logging Centralizado**: `core/logger.py`
- **Multi-Asset Foundation**: `TableBacktestMultiAsset` completado

### Changed
- **main.py**: Reducido de 644 a 180 líneas
- **Organización de Código**: Mejor estructura en `utils/` y `core/`
- **Imports**: Eliminados imports circulares

### Fixed
- **Performance**: Optimizaciones aplicadas, cuellos de botella eliminados
- **Memory**: Mejor uso de recursos

## [0.1.2] - 2025-01-XX

### Added
- **Suite de tests para mejoras**: `test_mejoras_futurechanges.py` valida las 3 mejoras de calidad de código.

### Changed
- **`gemini/memory.py`**: Mejorada sincronización de `_counts` desde CSV. Ahora detecta cuando el CSV tiene más datos que el JSON y actualiza los conteos totales automáticamente.
- **`gemini/gemini_core.py`**: Simplificada lógica de decisión en `evaluate_signals()`. Reducidas ramas if/else para mejor legibilidad y mantenimiento.
- **`tables/table_backtest.py`**: Añadido fallback automático para `trade_id` cuando falta en la orden. Genera ID único: `backtest_{symbol}_{index}`.

### Fixed
- **Memory CSV sync**: Corregido bug donde `_counts` no se sincronizaba al calentar desde CSV, causando inconsistencias.
- **Edge case handling**: Mejora robustez ante órdenes malformadas sin `trade_id`.

## [0.1.1] - 2025-10-14

### Added
- **Gestor de Posiciones (`PositionManager`):** Se introdujo un nuevo módulo (`tables/position_manager.py`) para gestionar de forma explícita el estado de las posiciones abiertas en modo *live*.
- **Cierre de Posiciones en `TableKrakenPaper`:** Se añadió un nuevo método `close_open_position` para manejar el cierre de trades y el cálculo de PnL.
- **Nuevos Scripts Utilitarios:** Se añadieron `fetch_funding_rates.py` y `download_kline_dataset.py` a `utils/`.

### Changed
- **Refactorización del Flujo de Trading en Vivo:** El bucle principal ahora orquesta el ciclo completo de vida de una operación: monitorea posiciones abiertas para su cierre antes de buscar nuevas entradas.
- `table_kraken_paper.py` ahora utiliza el `PositionManager` para registrar las posiciones abiertas a través de `execute_order`.

### Fixed
- **Cierre de Posiciones al Salir:** Se añadió lógica de limpieza a las sesiones en vivo (`live_session.py`) para asegurar que todas las posiciones abiertas se cierren al terminar el script (ej. con Ctrl+C), evitando dejar operaciones huérfanas.
- **Mejoras en `TableBacktest`:** Ahora lee el perfil de exchange para diferenciar fees, aplicar slippage dinámico, cobrar funding y simular liquidaciones. Los reportes ahora desglosan estos costos.
