# 🎯 ROADMAP v1.9.4 - REFACTORIZACIÓN DE MODULARIDAD

**Fecha Inicio:** 2025-11-06
**Duración Estimada:** 7 semanas
**Objetivo:** Maximizar modularidad, mantenibilidad y testabilidad

---

## 📊 RESUMEN EJECUTIVO

### Puntuación Actual: 6.5/10
### Puntuación Objetivo: 9.0/10

### Problemas Críticos Identificados

1. **Configuración Global** (Impacto: ALTO) - Todos los módulos dependen de `config.py`
2. **Falta DI** (Impacto: ALTO) - Instanciación directa, imposible testear
3. **Session Runner Legacy** (Impacto: ALTO) - 381 líneas duplicadas
4. **Gemini Monolítico** (Impacto: MEDIO) - 968 líneas, múltiples responsabilidades
5. **SensorManager Monolítico** (Impacto: MEDIO) - Demasiadas responsabilidades
6. **Sin BasePlayer** (Impacto: MEDIO) - Sin interfaz común

---

## 📁 DOCUMENTACIÓN

- **Análisis Completo:** `docs/ANALISIS_MODULARIDAD_v1.9.4.md`
- **Propuesta Detallada:** `docs/REFACTORIZACION_PROPUESTA_v1.9.4.md`

---

## 🗓️ PLAN DE IMPLEMENTACIÓN

### FASE 1: Fundamentos (2 semanas)

#### Sprint 1 (Semana 1)
**Objetivo:** Sistema de Configuración

- [ ] Crear `config/schema.py` con Pydantic
- [ ] Crear `config/manager.py` con ConfigManager
- [ ] Tests unitarios (>80% cobertura)
- [ ] Migrar `main.py` a usar ConfigManager

**Entregables:**
- ConfigManager funcional
- Validación automática de config
- Tests pasando

---

#### Sprint 2 (Semana 2)
**Objetivo:** Dependency Injection

- [ ] Crear `core/container.py` con ServiceContainer
- [ ] Crear factories para componentes
- [ ] Migrar `main.py` a usar container
- [ ] Tests de integración

**Entregables:**
- ServiceContainer funcional
- Componentes inyectables
- Tests de integración pasando

---

### FASE 2: Interfaces (1 semana)

#### Sprint 3 (Semana 3)
**Objetivo:** BasePlayer Interface

- [ ] Crear `core/interfaces/player.py`
- [ ] Refactorizar `players/paroli.py`
- [ ] Refactorizar `players/kelly.py`
- [ ] Tests unitarios por player

**Entregables:**
- BasePlayer abstracto
- Paroli y Kelly refactorizados
- Tests unitarios pasando

---

### FASE 3: Refactorización Core (3 semanas)

#### Sprint 4-5 (Semanas 4-5)
**Objetivo:** Dividir Gemini

- [ ] Crear `gemini/evaluator.py` (200 líneas)
- [ ] Crear `gemini/kelly.py` (150 líneas)
- [ ] Crear `gemini/bayesian.py` (200 líneas)
- [ ] Crear `gemini/verdict.py` (100 líneas)
- [ ] Crear `gemini/memory_interface.py` (100 líneas)
- [ ] Migrar a usar ConfigManager
- [ ] Tests unitarios por módulo

**Entregables:**
- Gemini modularizado
- Tests unitarios pasando
- Mismos resultados que antes

---

#### Sprint 6 (Semana 6)
**Objetivo:** Dividir SensorManager

- [ ] Crear `sensors/manager.py` (80 líneas)
- [ ] Crear `sensors/registry.py` (50 líneas)
- [ ] Crear `sensors/executor.py` (60 líneas)
- [ ] Crear `sensors/consolidator.py` (100 líneas)
- [ ] Crear `sensors/cooldown.py` (40 líneas)
- [ ] Tests unitarios por módulo

**Entregables:**
- SensorManager modularizado
- Tests unitarios pasando
- Performance mantenido

---

### FASE 4: Limpieza (1 semana)

#### Sprint 7 (Semana 7)
**Objetivo:** Eliminar Legacy y Documentar

- [ ] Eliminar `core/session_runner.py`
- [ ] Migrar funcionalidad a TradingSession
- [ ] Simplificar `BuildOrderStage`
- [ ] Crear `utils/symbol_normalizer.py`
- [ ] Actualizar toda la documentación
- [ ] Tests end-to-end

**Entregables:**
- Código legacy eliminado
- Documentación actualizada
- Sistema completamente refactorizado

---

## 📈 MÉTRICAS DE ÉXITO

### Antes → Después

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Acoplamiento | 8/10 | 2/10 | -75% |
| Cohesión | 5/10 | 9/10 | +80% |
| Testabilidad | 3/10 | 9/10 | +200% |
| Mantenibilidad | 5/10 | 9/10 | +80% |
| Cobertura Tests | 30% | 80% | +167% |
| Tiempo agregar Player | 2 días | 2 horas | -87.5% |
| Tiempo agregar Sensor | 1 día | 1 hora | -87.5% |
| Líneas duplicadas | 500 | 50 | -90% |

---

## 🎯 CRITERIOS DE ACEPTACIÓN

### Por Sprint

Cada sprint debe cumplir:
- [ ] Tests unitarios >80% cobertura
- [ ] Tests de integración pasando
- [ ] Backtest produce mismos resultados
- [ ] Performance no degradado (±5%)
- [ ] Documentación actualizada
- [ ] Code review aprobado

### Global

Al finalizar v1.9.4:
- [ ] Todos los módulos usan DI
- [ ] Configuración centralizada y validada
- [ ] Código legacy eliminado
- [ ] Cobertura de tests >80%
- [ ] Documentación completa
- [ ] Performance igual o mejor

---

## 🚀 PRÓXIMOS PASOS

1. **Revisar documentación** completa:
   - `docs/ANALISIS_MODULARIDAD_v1.9.4.md`
   - `docs/REFACTORIZACION_PROPUESTA_v1.9.4.md`

2. **Crear branch** de trabajo:
   ```bash
   git checkout -b refactor/v1.9.4-modularidad
   ```

3. **Comenzar Sprint 1** (Sistema de Configuración)

4. **Daily standups** para tracking de progreso

5. **Code reviews** al finalizar cada sprint

---

## 📝 NOTAS IMPORTANTES

### Principios de Refactorización

1. **Incremental:** Cambios pequeños y testeables
2. **Tests primero:** Asegurar que todo funciona antes de cambiar
3. **Backward compatible:** Mantener API pública estable
4. **Documentar:** Cada cambio debe estar documentado

### Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Romper funcionalidad existente | Media | Alto | Tests exhaustivos antes/después |
| Performance degradado | Baja | Medio | Benchmarks en cada sprint |
| Scope creep | Alta | Medio | Stick to roadmap, no features nuevas |
| Tiempo excedido | Media | Medio | Buffer de 1 semana al final |

---

## ✅ CHECKLIST DE INICIO

Antes de comenzar:
- [ ] Leer análisis completo
- [ ] Leer propuesta detallada
- [ ] Entender arquitectura objetivo
- [ ] Configurar entorno de desarrollo
- [ ] Crear branch de trabajo
- [ ] Configurar CI/CD para tests
- [ ] Notificar al equipo

---

**Estado:** PROPUESTA
**Aprobación requerida:** SÍ
**Próxima revisión:** Tras lectura de documentación

---

**Autor:** Cascade AI
**Fecha:** 2025-11-06
**Versión:** 1.0
