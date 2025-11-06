# 🛠️ Utilidades de Casino V2

Este directorio contiene herramientas y utilidades para desarrollo y debugging.

---

## 🔧 Herramientas de Testing de Conectores

### 🧪 Connector Validator
**Archivo:** `connector_validator.py`

Ejecuta una batería completa de tests automáticos para validar todas las funcionalidades de un conector.

**Uso:**
```bash
# Validar Kraken en testnet
python -m utils.connector_validator --exchange kraken --testnet

# Validar con símbolo específico
python -m utils.connector_validator --exchange kraken --testnet --symbol ETH/USD
```

**Tests incluidos:**
- ✅ Conexión
- ✅ Balance
- ✅ Posiciones
- ✅ Ticker
- ✅ Order Book
- ✅ Trades
- ✅ Órdenes
- ✅ Límites
- ✅ Fees
- ✅ Precisión
- ✅ Y más...

---

### 🎮 Connector Playground
**Archivo:** `connector_playground.py`

Modo interactivo para probar funciones individuales de un conector. Ideal para debugging y exploración.

**Uso:**
```bash
# Iniciar playground
python -m utils.connector_playground --exchange kraken --testnet
```

**Comandos disponibles:**
```
🎮 > help              # Ayuda
🎮 > symbol BTC/USD    # Cambiar símbolo
🎮 > ticker            # Ver ticker
🎮 > orderbook 10      # Ver order book
🎮 > balance           # Ver balance
🎮 > positions         # Ver posiciones
🎮 > trades 20         # Ver trades
🎮 > markets BTC       # Buscar mercados
🎮 > limits            # Ver límites
🎮 > fees              # Ver fees
🎮 > exit              # Salir
```

---

## 📖 Documentación

Ver guía completa en: [`docs/CONNECTOR_TESTING_GUIDE.md`](../docs/CONNECTOR_TESTING_GUIDE.md)

---

## 🎯 Casos de Uso

### 1. Implementando un Nuevo Conector
```bash
# 1. Validar implementación
python -m utils.connector_validator --exchange nuevo --testnet

# 2. Debugging interactivo
python -m utils.connector_playground --exchange nuevo --testnet
```

### 2. Debugging de Problemas
```bash
# Usar playground para probar función específica
python -m utils.connector_playground --exchange kraken --testnet

🎮 > mytrades 50
🎮 > orders
```

### 3. Explorar Exchange
```bash
# Explorar particularidades del exchange
python -m utils.connector_playground --exchange kraken --testnet

🎮 > markets
🎮 > limits
🎮 > fees
🎮 > precision
```

---

## 🚀 Quick Start

```bash
# 1. Validar conector
python -m utils.connector_validator --exchange kraken --testnet

# 2. Si hay errores, usar playground para debugging
python -m utils.connector_playground --exchange kraken --testnet

# 3. Probar función específica en playground
🎮 > ticker
🎮 > balance
🎮 > positions
```

---

## 📝 Notas

- **Testnet primero:** Siempre valida en testnet antes de usar en live
- **Credenciales:** Asegúrate de tener las credenciales en `.env`
- **Rate limiting:** Ten cuidado con los límites de API del exchange
- **Logs:** Puedes redirigir output a archivo para análisis

---

**Ver también:**
- [`docs/CONNECTOR_TESTING_GUIDE.md`](../docs/CONNECTOR_TESTING_GUIDE.md) - Guía completa
- [`exchanges/connectors/`](../exchanges/connectors/) - Conectores disponibles
- [`config/exchange.py`](../config/exchange.py) - Configuración de exchanges
