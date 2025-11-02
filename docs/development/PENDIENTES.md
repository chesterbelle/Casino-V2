# 📋 PENDIENTES - Casino V2

> **Versión Actual**: v1.7
> **Próxima Versión**: v1.8 - Multi-Asset Expansion

---

## 🔥 v1.7: TAREAS CRÍTICAS PENDIENTES

### **⭐⭐⭐ CRÍTICO - Live Trading Funcional** 🔄 **EN PROGRESO**

#### 🚀 **Modo Live con Exchanges Principales** (Máxima Prioridad)
**Estado**: 🔄 PENDIENTE - BLOQUEANTE PARA v1.8
**Descripción**: Hacer funcionar el modo live con los 3 exchanges principales
**Objetivo**: Sistema de live trading completamente operacional

**Exchanges a validar**:
1. **Kraken Futures Demo**
   - Testnet/Demo environment
   - Credenciales demo funcionales
   - Ejecución de órdenes real en demo

2. **Binance Futures Testnet**
   - Testnet environment
   - Credenciales testnet funcionales
   - Ejecución de órdenes en testnet

3. **Hyperliquid**
   - Testnet/Mainnet según disponibilidad
   - Credenciales funcionales
   - Ejecución de órdenes

**Criterio de Éxito** (Aprobación Manual):
- ✅ Sistema se conecta exitosamente al exchange
- ✅ Recibe datos de mercado en tiempo real (WebSocket o REST)
- ✅ Gemini genera señales correctamente
- ✅ Player calcula size apropiadamente
- ✅ Sistema ejecuta al menos 1 trade real en demo/testnet
- ✅ Trade se registra correctamente en logs
- ✅ Balance se actualiza después del trade
- ✅ Sistema corre estable por al menos 10 velas sin crashes
- ✅ **Revisión manual del desarrollador confirma funcionamiento**

**Complejidad**: Alta
**Tiempo estimado**: 2-3 días por exchange
**Bloqueante**: SÍ - debe completarse antes de v1.8

**Tareas específicas**:
- [ ] Validar credenciales y conexión para cada exchange
- [ ] Verificar formato de símbolos (BTC/USD vs BTCUSDT vs BTC)
- [ ] Probar WebSocket streams en tiempo real
- [ ] Validar ejecución de órdenes market
- [ ] Confirmar actualización de balance post-trade
- [ ] Documentar configuración específica por exchange
- [ ] Crear guía de troubleshooting por exchange

**Archivos involucrados**:
- `tables/table_ccxt_pro.py` - Mesa principal
- `core/config.py` - Configuración de exchanges
- `utils/exchanges/*_env_loader.py` - Carga de credenciales
- `core/live_session.py` - Loop principal de live trading

---

## 🎯 v1.8: MULTI-ASSET EXPANSION

### **⭐⭐⭐ CRÍTICO - Multi-Asset Foundation** ✅ **COMPLETADO**

### **⭐⭐⭐ CORE FEATURES** (v1.8)

#### 🎮 **Adaptive Player** (Alta Prioridad)
**Estado**: 🔄 PENDIENTE
**Descripción**: Player que ajusta Kelly según volatilidad del mercado
**Beneficios**:
- Mejor adaptación a condiciones de mercado
- Gestión de riesgo dinámica
- Performance potencial mejorada
**Complejidad**: Media
**Tiempo estimado**: 1 semana

#### 📊 **Dashboard Web Básico** (Alta Prioridad)
**Estado**: 🔄 PENDIENTE
**Descripción**: Visualización simple de resultados y métricas
**Beneficios**:
- Mejor monitoreo de performance
- Debugging más fácil
- UX mejorada para análisis
**Complejidad**: Media
**Tiempo estimado**: 1-2 semanas

#### 🛡️ **Kill-Switch Robusto** (Media Prioridad)
**Estado**: 🔄 PENDIENTE
**Descripción**: Sistema de protección automática de capital
**Features**:
- Stop loss de sesión
- Drawdown máximo
- Alertas automáticas
- Cierre automático
**Complejidad**: Media-Alta
**Tiempo estimado**: 1 semana

### **⭐⭐ ADVANCED FEATURES** (v1.8)

#### 🎯 **Regime Detection** (Media Prioridad)
**Estado**: 🔄 PENDIENTE
**Descripción**: Detección automática de bull/bear/sideways
**Beneficios**:
- Estrategias adaptativas por régimen
- Mejor timing de entradas
- Reducción de trades en mercados laterales
**Complejidad**: Alta
**Tiempo estimado**: 2 semanas

#### 📈 **Risk Management Avanzado** (Media Prioridad)
**Estado**: 🔄 PENDIENTE
**Descripción**: Límites dinámicos y portfolio heat management
**Features**:
- Límites dinámicos de posición
- Portfolio correlation controls
- Diversificación automática
**Complejidad**: Alta
**Tiempo estimado**: 2 semanas

---

## 🚀 PLAN DE ACCIÓN v1.8

### **Fase 1: Core Features** (3-4 semanas)

#### **1. Adaptive Player** ⭐⭐⭐ (1 semana)
**Objetivo**: Mejor adaptación a mercado
- Ajuste dinámico de Kelly por volatilidad
- Gestión de riesgo adaptativa
- Testing exhaustivo

#### **2. Dashboard Web Básico** ⭐⭐⭐ (1-2 semanas)
**Objetivo**: Mejor UX y debugging
- Visualización HTML de resultados
- Métricas en tiempo real
- Estado de posiciones

#### **3. Kill-Switch Robusto** ⭐⭐ (1 semana)
**Objetivo**: Protección automática de capital
- Stop loss de sesión dinámico
- Alertas configurables
- Cierre automático por drawdown

### **Fase 2: Advanced Features** (4-6 semanas)

#### **4. Regime Detection** ⭐⭐ (2 semanas)
**Objetivo**: Inteligencia de mercado
- Detección bull/bear/sideways
- Estrategias adaptativas por régimen
- Multi-timeframe analysis

#### **5. Risk Management Avanzado** ⭐⭐ (2 semanas)
**Objetivo**: Gestión sofisticada de riesgo
- Límites dinámicos de posición
- Portfolio correlation controls
- Diversificación automática

---

## 🎯 CÓMO EMPEZAR

### **🔥 PRIORIDAD INMEDIATA: Live Trading Funcional (v1.7)**

**ANTES de continuar con v1.8, debemos completar:**

```bash
# 1. Configurar credenciales del exchange en .env
# Ejemplo para Kraken:
KRAKEN_FUTURES_API_KEY=your_demo_key
KRAKEN_FUTURES_API_SECRET=your_demo_secret

# 2. Configurar config.py para el exchange
MODE = "live"
EXCHANGE = "KRAKEN_DEMO"  # o BINANCE_FUTURES_TESTNET o HYPERLIQUID

# 3. Ejecutar sesión live
python main.py

# 4. Validar manualmente:
# - ✅ Conexión exitosa
# - ✅ Datos en tiempo real
# - ✅ Al menos 1 trade ejecutado
# - ✅ Logs correctos
# - ✅ Balance actualizado
# - ✅ Estabilidad por 10+ velas
```

**Checklist de validación por exchange:**
- [x] **Kraken Futures Demo** - ✅ Validado y funcionando
- [ ] **Binance Futures Testnet** - Validado y funcionando
- [x] **Hyperliquid** - ✅ Casi operativo (requiere ajustes menores)

**Recursos para live trading:**
- 📖 `tables/table_ccxt_pro.py` - Mesa principal con WebSocket/REST híbrido
- 📖 `core/live_session.py` - Loop de live trading
- 📖 `utils/exchanges/` - Loaders de credenciales por exchange
- 📖 `docs/guides/hyperliquid_setup.md` - Guía específica de Hyperliquid

---

### **Después de completar v1.7: Adaptive Player (v1.8)**

```bash
# Crear rama para desarrollo
git checkout -b feature/adaptive-player

# Ver recursos disponibles
cat docs/development/PENDIENTES.md

# Implementar y testear
# ... desarrollo ...

# Registrar en COMPLETED_FEATURES.md cuando termine
```

**Recursos disponibles:**
- 📖 `players/kelly_player.py` - Referencia de player existente
- 📖 `players/fixed_player.py` - Otro ejemplo de player
- 📖 `docs/guides/creating-players.md` - Guía para crear players
- 🧪 Tests existentes como guía
- 📚 Documentación completa en `docs/`
