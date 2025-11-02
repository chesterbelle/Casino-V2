# 🚀 Quick Start - Live Trading

**Última actualización:** 2025-11-01
**Versión:** v1.7.1

---

## ⚡ Inicio Rápido

### 1. Configurar Exchange en `core/config.py`

```python
MODE = "live"
EXCHANGE = "KRAKEN_DEMO"  # o BINANCE_FUTURES_TESTNET, HYPERLIQUID
```

### 2. Configurar Credenciales en `.env`

```bash
# Kraken Futures Demo
KRAKEN_FUTURES_API_KEY=tu_api_key_aqui
KRAKEN_FUTURES_API_SECRET=tu_api_secret_aqui
```

### 3. Ejecutar Sistema

```bash
# Sin inputs (recomendado)
python main.py --symbol=LTC --interval=1m --max-candles=100

# Con inputs interactivos
python main.py
```

---

## 🎮 Opciones de Línea de Comandos

### Opciones Generales
```bash
--player=<nombre>    # kelly, fixed, paroli (default: paroli)
--help, -h           # Mostrar ayuda
```

### Opciones Live Trading
```bash
--symbol=<symbol>    # BTC, LTC, ETH, etc. (default: BTC)
--interval=<time>    # 1m, 5m, 15m, 1h (default: 1m)
--max-candles=<n>    # Límite de velas (default: ilimitado)
```

---

## 📝 Ejemplos de Uso

### Trading con LTC, 1 minuto, 100 velas
```bash
python main.py --symbol=LTC --interval=1m --max-candles=100
```

### Trading con BTC, 5 minutos, sin límite
```bash
python main.py --symbol=BTC --interval=5m
```

### Trading con ETH, 15 minutos, Kelly player
```bash
python main.py --symbol=ETH --interval=15m --player=kelly
```

---

## 🏦 Exchanges Soportados

### ✅ Kraken Futures Demo
- **Configuración:** `EXCHANGE = "KRAKEN_DEMO"`
- **Credenciales:** Generar en https://demo-futures.kraken.com/
- **Símbolos:** BTC, ETH, LTC, etc.
- **Estado:** ✅ FUNCIONAL

### 🔄 Binance Futures Testnet
- **Configuración:** `EXCHANGE = "BINANCE_FUTURES_TESTNET"`
- **Credenciales:** Generar en https://testnet.binancefuture.com/
- **Símbolos:** BTCUSDT, ETHUSDT, LTCUSDT, etc.
- **Estado:** 🔄 EN TESTING

### 🔄 Hyperliquid
- **Configuración:** `EXCHANGE = "HYPERLIQUID"`
- **Credenciales:** Wallet privada
- **Símbolos:** BTC, ETH, etc.
- **Estado:** 🔄 EN TESTING

---

## 📊 Qué Esperar

### Inicio del Sistema
```
🎰 Casino V2 — Live Trading (Testnet)

🎮 Player seleccionado: PAROLI
🏦 Exchange: KRAKEN_DEMO
✅ Credenciales de Kraken validadas
✅ Mesa live conectada
✅ Listener task iniciado
```

### Durante Ejecución
```
📊 REST data received for LTC/USD:USD: 1 candles
📊 Vela #1 procesada | timestamp=... | price=97.94
🎯 Señales encontradas: 1
✅ Gemini aprobó trade: SHORT
```

### Al Finalizar
```
============================================================
📊 Resumen sesión Live
------------------------------------------------------------
   Velas procesadas      : 100
   Balance inicial       : 5000.00 USD
   Balance final         : 5125.50 USD
   Trades BET            : 15
   WinRate (BET)         : 60.00%
============================================================
```

---

## ⚠️ Problemas Comunes

### 1. "AuthenticationError"
**Causa:** Credenciales incorrectas o no configuradas
**Solución:** Verificar `.env` y regenerar API keys si necesario

### 2. "Event loop is closed"
**Causa:** Versión antigua del código
**Solución:** Usar versión v1.7.1 o superior (con refactorización async)

### 3. "amount must be greater than minimum"
**Causa:** Player calculando size muy pequeño
**Solución:** Aumentar balance o ajustar configuración del Player

### 4. "Symbol not found"
**Causa:** Símbolo no disponible en el exchange
**Solución:** Verificar símbolos disponibles en el exchange

---

## 🔧 Troubleshooting

### Ver Logs Detallados
Los logs se guardan en `logs/` con nivel configurado en `core/config.py`:

```python
LOG_LEVEL = "INFO"  # DEBUG para más detalle
```

### Verificar Conexión
```bash
# Test rápido de conexión
python test_kraken_symbols.py
```

### Verificar Balance
```bash
# Test de balance
python test_balance_fix.py
```

---

## 📚 Documentación Adicional

- **Configuración Detallada:** `docs/guides/development-setup.md`
- **Crear Players:** `docs/guides/creating-players.md`
- **Setup Hyperliquid:** `docs/guides/hyperliquid_setup.md`
- **Arquitectura:** `docs/architecture/overview.md`
- **Refactorización Async:** `docs/development/ASYNC_REFACTOR_V1.7.1.md`

---

## 🆘 Soporte

Si encuentras problemas:

1. Revisa los logs en `logs/`
2. Verifica credenciales en `.env`
3. Consulta la documentación en `docs/`
4. Revisa issues conocidos en `docs/development/PENDIENTES.md`

---

## ✅ Checklist Pre-Trading

Antes de iniciar live trading, verifica:

- [ ] Credenciales configuradas en `.env`
- [ ] Exchange configurado en `core/config.py`
- [ ] MODE = "live" en `core/config.py`
- [ ] Balance disponible en cuenta demo/testnet
- [ ] Símbolos válidos para el exchange
- [ ] Player configurado correctamente
- [ ] Logs habilitados

---

**¡Listo para tradear! 🚀**
