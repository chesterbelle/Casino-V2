# 🧹 Plan de Limpieza de Código Legacy

## Objetivo
Eliminar todo el código legacy que no forma parte de la arquitectura actual (V2).

---

## 📋 Archivos a ELIMINAR

### 1. Directorio `tables/` (Legacy - Ya migrado a `exchanges/` y `core/portfolio/`)
```
❌ tables/__init__.py              → Wrapper de compatibilidad (ya no necesario)
❌ tables/connectors/__init__.py   → Wrapper de compatibilidad (ya no necesario)
✅ tables/data/                    → MANTENER (datasets para backtest)
```

**Razón:** Todo el código de `tables/` fue migrado a:
- `exchanges/connectors/` - Conectores
- `exchanges/adapters/` - Adapters
- `core/portfolio/` - Balance y posiciones

Los wrappers de compatibilidad ya no son necesarios porque el código fue actualizado.

---

### 2. Core Legacy Files
```
❌ core/config_v18_backup.py           → Backup de config antigua
❌ core/live_session_v18_backup.py     → Backup de sesión antigua
❌ core/session_runner.py              → Reemplazado por core/trading/session.py
❌ core/session_helpers.py             → Funciones helper legacy
❌ core/session_summary.py             → Reemplazado por SessionStats
```

**Razón:**
- Los backups ya no son necesarios (v18 → v2)
- `session_runner.py` fue reemplazado por `core/trading/session.py` (TradingSession)
- Los helpers fueron integrados en la nueva arquitectura

---

### 3. Croupier Legacy
```
❌ croupier/croupier_v2.py             → Ya fue migrado a croupier.py
❌ croupier/broker_interface.py        → Legacy, no se usa en V2
```

**Razón:**
- `croupier_v2.py` ya fue copiado a `croupier.py`
- `broker_interface.py` era parte de la arquitectura antigua

---

### 4. Tests Legacy
```
❌ validate_refactoring.py             → Script de validación temporal
❌ test_backtest_croupier_v2.py        → Test temporal (mover a tests/)
```

**Razón:**
- Scripts de validación temporal para la refactorización
- Deben moverse a `tests/` o eliminarse

---

### 5. Documentación Legacy
```
❌ PRUEBAS_VALIDACION_BACKTEST_VS_LIVE.md  → Pruebas antiguas
❌ ROADMAP_v1.9.4_REFACTORIZACION.md       → Roadmap completado
```

**Razón:**
- Documentación de versiones anteriores
- El roadmap v1.9.4 ya fue completado

---

## ✅ Archivos a MANTENER

### Arquitectura Actual (V2)
```
✅ config/                          → Config modular (nuevo)
✅ core/trading/                    → TradingSession + Pipeline (nuevo)
✅ core/data_sources/               → DataSources (nuevo)
✅ core/portfolio/                  → PortfolioManager (nuevo)
✅ exchanges/                       → Connectors + Adapters (migrado)
✅ croupier/croupier.py             → Croupier V2 (refactorizado)
✅ gemini/                          → Gemini (pendiente refactorizar)
✅ sensors/                         → Sensors (activo)
✅ players/                         → Players (activo)
✅ main.py                          → Entry point (actualizado)
```

### Datos y Tests
```
✅ tables/data/                     → Datasets para backtest
✅ tests/                           → Tests de integración
✅ docs/                            → Documentación actual
```

### Configuración
```
✅ .env
✅ .gitignore
✅ pyproject.toml
✅ .pre-commit-config.yaml
```

---

## 🗂️ Estructura DESPUÉS de la Limpieza

```
Casino-V2/
├── config/                    # Config modular ✅
├── core/
│   ├── trading/              # TradingSession + Pipeline ✅
│   ├── data_sources/         # DataSources ✅
│   ├── portfolio/            # PortfolioManager ✅
│   ├── cache.py              # Cache ✅
│   ├── exceptions.py         # Exceptions ✅
│   ├── logger.py             # Logger ✅
│   └── validators.py         # Validators ✅
├── exchanges/
│   ├── connectors/           # Exchange connectors ✅
│   ├── adapters/             # Exchange adapters ✅
│   └── resilience/           # Resilience patterns ✅
├── croupier/
│   └── croupier.py           # Croupier V2 ✅
├── gemini/                   # Gemini (pendiente refactor)
├── sensors/                  # Sensors ✅
├── players/                  # Players ✅
├── tables/
│   └── data/                 # Solo datasets ✅
├── tests/                    # Tests ✅
├── docs/                     # Documentación ✅
├── main.py                   # Entry point ✅
└── pyproject.toml            # Config ✅
```

---

## 📝 Resumen de Cambios

### Eliminar
- 🗑️ **9 archivos** legacy
- 🗑️ **2 directorios** de wrappers de compatibilidad

### Mantener
- ✅ **Arquitectura V2** completa
- ✅ **Datasets** para backtest
- ✅ **Tests** actuales
- ✅ **Documentación** relevante

### Resultado
- 🎯 Código más limpio y mantenible
- 🚀 Sin dependencias legacy
- 📦 Estructura clara y moderna
- ✅ 100% arquitectura V2

---

## ⚠️ Precauciones

1. **Backup antes de eliminar** - Hacer commit de git antes de la limpieza
2. **Verificar imports** - Asegurar que ningún archivo activo importe código legacy
3. **Mantener datos** - No eliminar `tables/data/` (datasets)
4. **Tests** - Ejecutar tests después de la limpieza

---

**Fecha:** 2025-11-06
**Versión:** V2.0.0
