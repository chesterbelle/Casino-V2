# 🔧 Guía de Testing de Conectores

Esta guía explica cómo usar las herramientas de testing y debugging de conectores.

---

## 📋 Herramientas Disponibles

### 1. **Connector Validator** - Validación Automática
Ejecuta una batería completa de tests para validar todas las funcionalidades de un conector.

### 2. **Connector Playground** - Modo Interactivo
Permite probar funciones individuales de forma interactiva, ideal para debugging.

---

## 🧪 Connector Validator

### Uso Básico

```bash
# Validar Kraken en testnet
python -m utils.connector_validator --exchange kraken --testnet

# Validar Kraken en live
python -m utils.connector_validator --exchange kraken --live

# Validar con símbolo específico
python -m utils.connector_validator --exchange kraken --testnet --symbol ETH/USD
```

### Tests Ejecutados

El validador ejecuta los siguientes tests automáticamente:

1. ✅ **Conexión** - Verifica que el conector puede conectarse
2. ✅ **Balance** - Obtiene y valida el balance
3. ✅ **Posiciones** - Obtiene posiciones abiertas
4. ✅ **Ticker** - Obtiene ticker del símbolo
5. ✅ **Order Book** - Obtiene libro de órdenes
6. ✅ **Trades Recientes** - Obtiene trades del mercado
7. ✅ **Mis Trades** - Obtiene historial de trades propios
8. ✅ **Órdenes Abiertas** - Lista órdenes abiertas
9. ✅ **Crear Orden** - Test de creación (dry run)
10. ✅ **Cancelar Orden** - Test de cancelación (dry run)
11. ✅ **Límites de Trading** - Valida límites min/max
12. ✅ **Fees** - Verifica fees maker/taker
13. ✅ **Timeframes** - Lista timeframes disponibles
14. ✅ **Precisión** - Valida precisión de precios

### Ejemplo de Salida

```
================================================================================
🔍 VALIDACIÓN DE CONECTOR: KrakenConnector
📊 Símbolo: BTC/USD
================================================================================

────────────────────────────────────────────────────────────────────────────────
🧪 Test: Conexión
────────────────────────────────────────────────────────────────────────────────
✅ Conexión: PASS
  connected: True
  duration: 0.45s

────────────────────────────────────────────────────────────────────────────────
🧪 Test: Balance
────────────────────────────────────────────────────────────────────────────────
✅ Balance: PASS
  total_currencies: 5
  currencies: ['USD', 'BTC', 'ETH', 'USDT', 'EUR']
  sample:
    USD:
      free: 10000.0
      used: 0.0
      total: 10000.0

...

================================================================================
📊 RESUMEN DE VALIDACIÓN
================================================================================

Total tests: 14
✅ Passed: 14
❌ Failed: 0
Success rate: 100.0%

Detalle por test:
  ✅ PASS Conexión (0.45s)
  ✅ PASS Balance (0.32s)
  ✅ PASS Posiciones (0.28s)
  ...
```

---

## 🎮 Connector Playground

### Uso Básico

```bash
# Iniciar playground de Kraken en testnet
python -m utils.connector_playground --exchange kraken --testnet

# Iniciar playground de Kraken en live
python -m utils.connector_playground --exchange kraken --live
```

### Comandos Disponibles

Una vez en el playground, puedes usar estos comandos:

#### Comandos Generales
```
help, h              - Muestra ayuda
symbol <SYMBOL>      - Cambia el símbolo actual
exit, quit           - Sale del playground
```

#### Comandos de Datos de Mercado
```
ticker               - Muestra ticker del símbolo actual
orderbook [limit]    - Muestra order book (default: 10)
trades [limit]       - Muestra trades recientes (default: 10)
markets [search]     - Lista mercados disponibles
```

#### Comandos de Cuenta
```
balance              - Muestra balance
positions            - Muestra posiciones abiertas
mytrades [limit]     - Muestra mis trades (default: 20)
orders               - Muestra órdenes abiertas
```

#### Comandos de Información
```
limits               - Muestra límites de trading
fees                 - Muestra fees maker/taker
precision            - Muestra precisión de precios
timeframes           - Muestra timeframes disponibles
```

### Ejemplo de Sesión

```
================================================================================
🎮 CONNECTOR PLAYGROUND: KrakenConnector
================================================================================
✅ Conectado al exchange

📖 COMANDOS DISPONIBLES:
────────────────────────────────────────────────────────────────────────────────
  help, h              - Muestra esta ayuda
  symbol <SYMBOL>      - Cambia el símbolo actual
  balance              - Muestra balance
  ticker               - Muestra ticker del símbolo actual
  ...
────────────────────────────────────────────────────────────────────────────────
📊 Símbolo actual: BTC/USD

🎮 > ticker
📈 Obteniendo ticker de BTC/USD...

📈 TICKER: BTC/USD
────────────────────────────────────────────────────────────────────────────────
  Last: 43250.5
  Bid: 43248.0
  Ask: 43252.0
  High: 43500.0
  Low: 42800.0
  Volume: 1234.56
  Timestamp: 2025-11-06T23:15:30.000Z

🎮 > symbol ETH/USD
✅ Símbolo cambiado a: ETH/USD

🎮 > orderbook 5
📖 Obteniendo order book de ETH/USD (limit=5)...

📖 ORDER BOOK: ETH/USD
────────────────────────────────────────────────────────────────────────────────

  🟢 BIDS (compra):
      2250.50 |     10.50000000
      2250.00 |     25.30000000
      2249.50 |     15.80000000
      2249.00 |     30.20000000
      2248.50 |     20.10000000

  🔴 ASKS (venta):
      2251.00 |     12.40000000
      2251.50 |     18.60000000
      2252.00 |     22.30000000
      2252.50 |     16.70000000
      2253.00 |     28.90000000

  Spread: 0.50

🎮 > exit
👋 Saliendo...
🔌 Desconectado
```

---

## 🔍 Casos de Uso

### 1. Implementando un Nuevo Conector

Cuando implementas un nuevo conector:

```bash
# 1. Ejecutar validación completa
python -m utils.connector_validator --exchange nuevo_exchange --testnet

# 2. Si hay errores, usar playground para debugging
python -m utils.connector_playground --exchange nuevo_exchange --testnet

# 3. En playground, probar función específica que falla
🎮 > ticker
🎮 > orderbook
🎮 > balance
```

### 2. Debugging de Problemas Específicos

Si tienes un problema con una función específica:

```bash
# Iniciar playground
python -m utils.connector_playground --exchange kraken --testnet

# Probar la función problemática
🎮 > mytrades 50
🎮 > orders
```

### 3. Explorando Particularidades del Exchange

Para entender las particularidades de un exchange:

```bash
# Iniciar playground
python -m utils.connector_playground --exchange kraken --testnet

# Explorar mercados
🎮 > markets BTC
🎮 > symbol BTC/USD
🎮 > limits
🎮 > fees
🎮 > precision
```

### 4. Validación Pre-Producción

Antes de usar un conector en producción:

```bash
# 1. Validar en testnet
python -m utils.connector_validator --exchange kraken --testnet

# 2. Validar en live (con cuidado)
python -m utils.connector_validator --exchange kraken --live

# 3. Verificar todos los tests pasan
# Success rate: 100.0%
```

---

## 🛠️ Extendiendo las Herramientas

### Agregar Soporte para Nuevo Exchange

1. **Actualizar `connector_validator.py`:**

```python
# En la función validate_connector()
if exchange.lower() == "kraken":
    connector = KrakenConnector(testnet=testnet)
elif exchange.lower() == "binance":
    connector = BinanceConnector(testnet=testnet)
elif exchange.lower() == "tu_exchange":
    connector = TuExchangeConnector(testnet=testnet)
```

2. **Actualizar `connector_playground.py`:**

```python
# En la función start_playground()
if exchange.lower() == "kraken":
    connector = KrakenConnector(testnet=testnet)
elif exchange.lower() == "tu_exchange":
    connector = TuExchangeConnector(testnet=testnet)
```

3. **Actualizar choices en argparse:**

```python
parser.add_argument(
    "--exchange",
    type=str,
    required=True,
    choices=["kraken", "binance", "tu_exchange"],
    help="Exchange a validar",
)
```

### Agregar Nuevos Tests

Para agregar un nuevo test al validador:

```python
# En ConnectorValidator class
async def test_nueva_funcionalidad(self) -> Dict:
    """Test de nueva funcionalidad."""
    start = datetime.now()
    try:
        # Tu código de test aquí
        result = await self.connector.nueva_funcion()
        duration = (datetime.now() - start).total_seconds()

        return {
            "success": True,
            "data": {"resultado": result},
            "duration": duration,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# Agregar a la lista de tests en run_all_tests()
tests = [
    # ... tests existentes ...
    ("Nueva Funcionalidad", self.test_nueva_funcionalidad),
]
```

### Agregar Nuevos Comandos al Playground

Para agregar un nuevo comando:

```python
# En ConnectorPlayground class
async def cmd_nuevo_comando(self, args):
    """Comando: nuevo_comando."""
    logger.info("🔧 Ejecutando nuevo comando...")
    # Tu código aquí

# Agregar al diccionario de comandos en execute_command()
commands = {
    # ... comandos existentes ...
    "nuevo": self.cmd_nuevo_comando,
}

# Actualizar help en print_help()
logger.info("  nuevo [args]         - Descripción del comando")
```

---

## 📝 Tips y Mejores Prácticas

### 1. Siempre Validar en Testnet Primero
```bash
# ✅ Correcto
python -m utils.connector_validator --exchange kraken --testnet

# ⚠️ Cuidado
python -m utils.connector_validator --exchange kraken --live
```

### 2. Usar Playground para Debugging Iterativo
- El playground es ideal para probar cambios rápidamente
- No necesitas reiniciar para probar diferentes comandos
- Puedes cambiar símbolos sobre la marcha

### 3. Validar Todos los Símbolos Importantes
```bash
# Validar BTC
python -m utils.connector_validator --exchange kraken --testnet --symbol BTC/USD

# Validar ETH
python -m utils.connector_validator --exchange kraken --testnet --symbol ETH/USD
```

### 4. Guardar Logs para Análisis
```bash
# Redirigir output a archivo
python -m utils.connector_validator --exchange kraken --testnet > validation_log.txt 2>&1
```

### 5. Verificar Particularidades del Exchange
Cada exchange tiene sus particularidades:
- Formato de símbolos (BTC/USD vs BTCUSD)
- Límites de rate limiting
- Precisión de precios
- Fees diferentes por par
- Timeframes disponibles

Usa el playground para explorar estas diferencias.

---

## 🐛 Troubleshooting

### Error: "Exchange no soportado"
```bash
# Solución: Agregar soporte para el exchange
# Ver sección "Extendiendo las Herramientas"
```

### Error: "Symbol not found"
```bash
# Solución: Verificar formato del símbolo
🎮 > markets BTC  # Buscar el formato correcto
🎮 > symbol BTC/USD  # Usar formato correcto
```

### Error de Autenticación
```bash
# Solución: Verificar credenciales en .env
# KRAKEN_API_KEY=...
# KRAKEN_API_SECRET=...
```

### Rate Limiting
```bash
# Solución: Agregar delays entre comandos
# O usar testnet que suele tener límites más relajados
```

---

## 📚 Recursos Adicionales

- **Documentación de Conectores:** `docs/connectors/`
- **Ejemplos de Uso:** `tests/test_connectors.py`
- **Configuración:** `config/exchange.py`

---

**Última actualización:** 2025-11-06
