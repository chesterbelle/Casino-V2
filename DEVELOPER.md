# 🚀 Casino V2 - Developer Guide

> **⚠️ OBLIGATORIO: Leer ANTES de cualquier desarrollo o modificación**

## 📋 Checklist Pre-Desarrollo (Completar TODOS)

- [ ] Leer este documento `DEVELOPER.md` completo
- [ ] Leer `docs/workflow.md` (guidelines de desarrollo)
- [ ] Leer `docs/development/PENDIENTES.md` (estado actual y roadmap)
- [ ] Leer `docs/architecture/overview.md` (arquitectura del sistema)
- [ ] Verificar sistema funciona (`python main.py`)
- [ ] Ejecutar tests (`python -m pytest`)

**❌ NO EMPEZAR desarrollo sin completar este checklist**

---

## 🎯 Workflow Rápido

### **4 Pasos para Desarrollar:**

1. **📋 Planificar**
   - Leer PENDIENTES.md → Elegir feature prioritaria
   - Diseñar solución respetando arquitectura existente
   - Estimar tiempo y complejidad

2. **🔄 Desarrollar**
   - Crear rama `feature/nombre-descriptivo`
   - Implementar código siguiendo estándares
   - Tests pasan en cada cambio significativo
   - Commits descriptivos y frecuentes

3. **✅ Validar**
   - Tests exhaustivos (unit + integration)
   - Backtest funciona (no degrada performance)
   - Documentación actualizada
   - Code review checklist completo

4. **🚀 Merge**
   - Pull Request con descripción detallada
   - Aprobación de code review
   - Merge a rama desarrollo
   - Actualizar PENDIENTES.md y CHANGELOG.md

---

## 📚 Documentación Esencial (Orden de Lectura)

### **1. Primero - Entender el Sistema**
| Documento | Propósito | Obligatorio | Tiempo |
|-----------|-----------|-------------|--------|
| `docs/workflow.md` | Guidelines de desarrollo | ✅ SÍ | 15 min |
| `docs/development/PENDIENTES.md` | Estado actual + roadmap | ✅ SÍ | 10 min |
| `docs/architecture/overview.md` | Arquitectura completa | ✅ SÍ | 20 min |
| `README.md` | Overview del proyecto | ✅ SÍ | 5 min |

### **2. Luego - Desarrollo Específico**
| Documento | Cuándo Leer | Tiempo |
|-----------|-------------|--------|
| `docs/guides/installation.md` | Setup desarrollo | 10 min |
| `docs/guides/exchange-setup.md` | Live trading | 15 min |
| `docs/development/troubleshooting.md` | Problemas comunes | Según necesidad |
| `docs/guides/creating-players.md` | Nuevo player | 10 min |

### **3. Arquitectura por Componentes**
| Componente | Documentación | Propósito |
|------------|---------------|-----------|
| **Gemini** | `docs/architecture/gemini-player.md` | Sistema de validación |
| **Players** | `docs/guides/creating-players.md` | Estrategias sizing |
| **Sensors** | `docs/reference/sensors.md` | Indicadores técnicos |
| **Tables** | `docs/architecture/overview.md` | Interfaces exchange |
| **WebSocket** | `docs/architecture/websocket-integration.md` | Datos real-time |

---

## 🏗️ Arquitectura Rápida (Referencia)

### **Separación de Responsabilidades**
```
🎯 Gemini → Valida probabilidades (¿Apostar?)
🎮 Player → Decide tamaño (¿Cuánto apostar?)
👁️ Sensors → Detecta contextos (¿Dónde apostar?)
🪙 Tables → Provee datos (¿Qué datos usar?)
🧤 Croupier → Ejecuta órdenes (¿Cómo ejecutar?)
```

### **Estructura de Carpetas**
```
Casino-V2/
├── main.py                 # 🚀 Entry point unificado
├── config.py              # ⚙️ Configuración global
├── gemini/                # 🎯 Validación probabilística
├── players/               # 🎮 Estrategias de sizing
├── sensors/               # 👁️ Indicadores técnicos
├── tables/                # 🪙 Interfaces de exchange
├── croupier/              # 🧤 Ejecución de órdenes
├── utils/                 # 🛠️ Herramientas CLI
├── docs/                  # 📚 Documentación
└── tests/                 # 🧪 Testing
```

### **Flujo de Datos**
```
Datos → Sensors → Gemini → Players → Croupier → Exchange
                        ↓
                   Memoria (aprendizaje)
```

---

## 🚦 Estados del Proyecto

### **v1.6 - ACTUAL (Completado)**
- ✅ Arquitectura unificada main.py
- ✅ Multi-exchange testnet (Hyperliquid, Binance, Kraken)
- ✅ WebSocket integration completa
- ✅ 17 sensores técnicos activos
- ✅ Sistema de memoria bayesiano
- ✅ Risk management conservador

### **v1.7 - PRÓXIMO (En Desarrollo)**
- 🎯 Multi-asset trading simultáneo
- 📊 Portfolio management unificado
- ⏱️ Multi-timeframe analysis
- 🎯 Risk diversification

**📖 [Roadmap v1.7 Completo →](docs/development/ROADMAP_V1.7.md)**

---

## 🛠️ Comandos Esenciales

### **Verificar Sistema**
```bash
# Estado general
python main.py

# Tests completos
python -m pytest

# Tests específicos
python -m pytest tests/test_gemini.py -v
```

### **Desarrollo**
```bash
# Crear rama feature
git checkout -b feature/mi-feature

# Ver cambios
git status
git diff

# Commit frecuente
git add .
git commit -m "feat: Descripción clara del cambio"
```

### **Testing**
```bash
# Tests unitarios
python -m pytest tests/ -k "test_my_feature"

# Tests con cobertura
python -m pytest --cov=mi_modulo --cov-report=html

# Tests de performance
python -m pytest tests/test_performance.py
```

---

## ⚠️ Reglas Importantes

### **✅ SIEMPRE HACER:**
- Leer documentación antes de modificar código
- Tests pasan antes de cada commit
- Commits descriptivos y pequeños
- Code review para todos los cambios
- Actualizar documentación con cambios

### **❌ NUNCA HACER:**
- Commits directos a rama principal (usar PR)
- Cambios sin tests correspondientes
- Código sin documentación actualizada
- Modificaciones sin entender arquitectura
- Merge sin aprobación de code review

---

## 🆘 Troubleshooting Rápido

### **"No sé por dónde empezar"**
1. Leer PENDIENTES.md → elegir feature prioritaria
2. Ver código similar existente como referencia
3. Empezar con tests (TDD)

### **"Mi código rompe algo"**
1. Ejecutar `python -m pytest` completo
2. Verificar `python main.py` funciona
3. Revisar logs de error detalladamente

### **"No entiendo la arquitectura"**
1. Leer `docs/architecture/overview.md`
2. Ver ejemplos en código existente
3. Preguntar con contexto específico

### **"Problemas con live trading"**
1. Verificar credenciales en `.env`
2. Test con `python main.py` (timeout 30s)
3. Revisar `docs/guides/exchange-setup.md`

---

## 🎯 Próximos Pasos Después de Leer Esto

1. **✅ Completar checklist** arriba
2. **📖 Leer workflow.md** completo
3. **📋 Revisar PENDIENTES.md** para features disponibles
4. **🎯 Elegir tarea** para desarrollar
5. **🌳 Crear rama** `feature/tu-feature`
6. **🚀 Empezar desarrollo**

---

## 📞 Contacto & Recursos

- **🐛 Issues**: Para bugs o problemas técnicos
- **💬 Discussions**: Para preguntas generales
- **📖 Docs**: Toda documentación en `docs/`
- **🧪 Tests**: Como referencia de funcionamiento esperado

---

**🎰 ¡Bienvenido al desarrollo de Casino V2!**

*Recuerda: La documentación es tan importante como el código. Mantengámosla actualizada juntos.* 📚✨

---

**Última actualización: v1.6 - Octubre 2025**