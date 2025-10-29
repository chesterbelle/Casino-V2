# 🚀 Guía de Configuración: Hyperliquid Live Trading

## 📋 Requisitos Previos

### 1. Cuenta en Hyperliquid
- Regístrate en [Hyperliquid](https://app.hyperliquid.xyz)
- Completa verificación KYC si es requerido
- Deposita fondos para trading

### 2. API Keys
- Ve a Settings → API Keys
- Crea una nueva API Key
- **Importante**: Configura permisos mínimos necesarios:
  - ✅ Read Info
  - ✅ Trade (solo si vas a usar live trading real)

### 3. Variables de Entorno
Configura estas variables en tu `.env` file o environment:

```bash
# API Credentials
HYPERLIQUID_API_KEY=tu_api_key_aqui
HYPERLIQUID_API_SECRET=tu_api_secret_aqui

# Opcional: Para vault trading
HYPERLIQUID_VAULT_ADDRESS=tu_vault_address

# Configuración adicional (opcional)
HYPERLIQUID_BASE_URL=https://api.hyperliquid.xyz
HYPERLIQUID_WS_URL=wss://api.hyperliquid.xyz/ws
HYPERLIQUID_TESTNET=false
```

## ⚙️ Configuración del Sistema

### 1. Archivo `config.py`
El sistema ya está configurado para Hyperliquid. Verifica:

```python
# En config.py
MODE = "live"
EXCHANGE_PROFILE = "hyperliquid"
EXCHANGE = "HYPERLIQUID"

# Sensores activos (todos los 17)
ACTIVE_SENSORS = {
    # ... todos True ...
}

# Configuración conservadora para live trading
KELLY_FRACTION = 0.1
MAX_POSITION_SIZE = 0.02
LIVE_MAX_CANDLES = 100  # Sesiones cortas inicialmente
```

### 2. Perfil de Exchange
Se creó automáticamente `tables/data/exchange_profiles/hyperliquid.json`:

```json
{
  "name": "Hyperliquid",
  "maker_fee": 0.0001,
  "taker_fee": 0.0005,
  "entry_fee_rate": 0.0005,
  "exit_fee_rate": 0.0005,
  "slippage_model": {
    "type": "linear",
    "base_spread": 0.0002,
    "per_size_fraction": 0.001
  },
  "funding_rate_per_hour": 0.00008,
  "leverage_limit": 50
}
```

## 🧪 Testing Inicial

### 1. Verificar Conexión
```bash
# Probar que las credenciales funcionan
python -c "
from utils.hyperliquid_env_loader import load_hyperliquid_config, validate_hyperliquid_config
config = load_hyperliquid_config()
print('Config loaded:', validate_hyperliquid_config(config))
"
```

### 2. Test de WebSocket (sin trading real)
```bash
# Probar conexión WebSocket
python test_websocket_live.py
```

### 3. Backtest Primero
Antes de live trading, ejecuta un backtest con datos similares:

```bash
# Cambiar a modo backtest temporalmente
# En config.py: MODE = "backtest"
# DATASET_PATH = "ruta/a/datos/hyperliquid"

python main.py
```

## 🚀 Iniciar Live Trading

### 1. Configuración Final
```python
# En config.py - Ajustes para live trading
LIVE_MAX_CANDLES = None  # Sin límite de velas
KELLY_FRACTION = 0.1     # Muy conservador inicialmente
MAX_POSITION_SIZE = 0.02 # Máximo 2% del equity por trade
```

### 2. Ejecutar Live Session
```bash
python live_session.py
```

### 3. Monitoreo
- Revisa logs en tiempo real
- Monitorea `gemini/data/gemini_decisions.csv`
- Revisa `gemini/data/gemini_trade_results.csv`
- Observa balance en Hyperliquid dashboard

## ⚠️ Consideraciones de Seguridad

### 1. Risk Management
- **Kelly Fraction**: 0.1 (10% del Kelly óptimo)
- **Max Position Size**: 2% del equity
- **Stop Loss**: 1.5% por trade
- **Max Drawdown**: Monitorea manualmente

### 2. Monitoreo Continuo
- No dejes sesiones unattended inicialmente
- Configura alertas en Hyperliquid
- Revisa logs regularmente
- Ten plan de contingencia para cerrar posiciones

### 3. Scaling Up
- Después de 100+ trades exitosos, considera aumentar Kelly a 0.15
- Incrementa position size gradualmente
- Nunca más de 5% del equity por trade

## 🛑 Emergency Stop

Si algo sale mal:

```bash
# Cerrar todas las posiciones manualmente en Hyperliquid dashboard
# O modificar config para trading inactivo:
KELLY_FRACTION = 0.0  # Desactiva nuevos trades
```

## 📊 Métricas a Monitorear

### Performance
- Win Rate objetivo: > 55%
- Profit Factor: > 1.2
- Max Drawdown: < 10%
- Sharpe Ratio: > 1.5

### Sistema
- Trades por hora: 2-4 inicialmente
- Latencia: < 2 segundos por trade
- Error rate: < 5%

## 🔧 Troubleshooting

### Problema: "API Key invalid"
- Verifica variables de entorno
- Confirma que la API key no expiró
- Revisa permisos de la API key

### Problema: "Insufficient balance"
- Verifica fondos disponibles en Hyperliquid
- Confirma que no hay posiciones abiertas
- Revisa fees y costos

### Problema: "WebSocket connection failed"
- Verifica conectividad a internet
- Confirma URLs de Hyperliquid
- Revisa firewall/antivirus

## 📞 Soporte

- **Hyperliquid Docs**: https://docs.hyperliquid.xyz
- **Casino V2 Logs**: Revisa `logs/` directory
- **Configuración**: Verifica `config.py` y variables de entorno

---

## ✅ Checklist Pre-Live Trading

- [ ] API keys configuradas en variables de entorno
- [ ] `config.py` actualizado para Hyperliquid
- [ ] Backtest exitoso con datos similares
- [ ] Test WebSocket funcionando
- [ ] Credenciales validadas
- [ ] Plan de risk management definido
- [ ] Monitoreo configurado
- [ ] Plan de contingencia preparado

**¡Listo para live trading con Hyperliquid! 🚀**