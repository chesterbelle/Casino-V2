# 🎰 CASINO BINANCE V2 — *La Era Gemini*

> Un laboratorio de trading probabilístico inspirado en la dinámica de un casino sin límite de apuesta.  
> Cada módulo cumple un rol dentro del ecosistema: analistas, jugadores, mesas y crupieres trabajando juntos.

---

## 🧠 Filosofía del Proyecto

En lugar de intentar predecir el futuro, el sistema busca explotar contextos estadísticamente favorables,  
jugando únicamente cuando el Valor Esperado (EV) es positivo.

El objetivo es construir un entorno modular, donde cada componente represente un rol dentro del casino:

Rol | Módulo | Descripción  
----|---------|-------------  
🎩 **Gemini (Jugador racional)** | `gemini/` | Evalúa el mercado y decide cuándo y cuánto apostar en función de la probabilidad estimada de éxito (p̂).  
👁️ **Analistas de mesa (Sensores)** | `sensors/` | Observan el mercado y detectan contextos técnicos favorables.  
🧤 **Crupier** | `croupier/` | Ejecuta las órdenes sin pensar, ya sea en modo simulado o real.  
🪙 **Mesas** | `tables/` | Controlan los datos (reales o históricos), aplican fees, slippage y mantienen el balance.  
💰 **Cajero (BalanceManager)** | `tables/balance_manager.py` | Administra el capital del jugador y reporta resultados.  
🧾 **Protocolo** | `protocolo.md` | Define las reglas de desarrollo, validación y testing.  

---

## ⚙️ Arquitectura General

Gemini → Croupier → Mesa (Feed) → BalanceManager  
             ↑                     ↓  
         resultado ←――――――――――――――――  

---

## 📂 Estructura del Proyecto

Casino-V2/
│
├── main.py                        # Orquestador maestro del casino
├── config.py                      # Configuración global
├── protocolo.md                   # Reglas de desarrollo y testing
│
├── gemini/
│   ├── gemini_core.py             # Núcleo lógico del jugador racional
│   ├── bucket_manager.py          # Clasificación de contextos
│   ├── memory.py                  # Historial adaptativo de resultados
│   └── __init__.py
│
├── sensors/
│   ├── sensor_manager.py          # Orquestador de sensores
│   ├── rsi_reversion.py           # Detector RSI (reversión)
│   ├── bollinger_touch.py         # Detector Bollinger (extremos)
│   ├── keltner_reversion.py       # Detector Keltner (reversión)
│   └── __init__.py
│
├── croupier/
│   ├── croupier.py                # Croupier universal
│   ├── broker_interface.py        # Controla el modo backtest/live
│   ├── order_simulator.py         # Ejecutor simulado
│   ├── order_realtime.py          # Ejecutor en vivo (placeholder)
│   └── __init__.py
│
└── tables/
    ├── table_base.py              # Clase base para las mesas
    ├── table_backtest.py          # Mesa de simulación
    ├── balance_manager.py         # Control de capital
    ├── data/
    │   ├── raw/                   # Datasets históricos (.csv)
    │   └── exchange_profiles/     # Perfiles por exchange
    └── __init__.py

---

## 🧾 Descripción de Componentes

🎩 Gemini — El jugador racional  
- Evalúa cada señal recibida por los sensores.  
- Calcula la probabilidad estimada de éxito (p̂).  
- Compara con el umbral crítico (p* = L / (L + R)).  
- Si p̂ > p*, ejecuta una apuesta con fracción de Kelly ajustada al riesgo.  
- Aprende de los resultados y ajusta su comportamiento.  

👁️ Sensores — Los analistas técnicos  
- Usan indicadores simples: RSI, Bollinger Bands y Keltner Channels.  
- Cada sensor produce señales independientes (LONG, SHORT o NONE).  
- El `SensorManager` las unifica antes de entregarlas a Gemini.  

🧤 Crupier — El ejecutor imparcial  
- Recibe órdenes ya decididas por Gemini.  
- Las pasa a la mesa activa (feed), que puede ser:  
  - `TableBacktest` (simulada)  
  - `TableRealtime` (futura implementación)  
- No evalúa condiciones de mercado ni riesgos.  

🪙 Mesas — Las fuentes de verdad  
- Administran los datos de precios (históricos o reales).  
- Aplican comisiones, slippage, funding y latencia.  
- Mantienen y actualizan el balance del jugador.  
- Devuelven resultados normalizados (WIN, LOSS, pnl, fee, etc).  

---

## ⚙️ Configuración (config.py)

El archivo `config.py` centraliza todos los parámetros del casino:

MODE = "backtest"  
DATASET_PATH = "tables/data/raw/LTCUSDT_15min_bull.csv"  
STARTING_BALANCE = 10_000.0  
TAKE_PROFIT = 0.010  
STOP_LOSS = 0.008  
KELLY_FRACTION = 1.0  
WINDOW_SIZE = 120  
MIN_SUPPORT = 20  
LOG_LEVEL = "INFO"  

---

## 🚀 Ejecución

1. Asegúrate de tener los datasets en:  
   - tables/data/raw/LTCUSDT_15min_bull.csv  
   - tables/data/raw/LTCUSDT_15min_bear.csv  

2. Configura config.py:  
   MODE = "backtest"  
   DATASET_PATH = "tables/data/raw/LTCUSDT_15min_bull.csv"  

3. Ejecuta:  
   python3 main.py  

4. Verás un flujo como:  
   🎰 Bienvenido al Casino Binance V2  
   2025-10-10 08:44:15 | Gemini | INFO | 🎯 Mesa caliente | p̂=0.57 > p*=0.44 | Apuesta: 5.23% del equity  
   2025-10-10 08:44:16 | Croupier | INFO | ✅ Resultado: WIN | PnL: +1.23%  
   📊 WinRate: 58.00% | Balance: 10,456.73 | Trades: 23  

---

## 📚 Filosofía Técnica

El casino no busca predecir sino apostar con ventaja estadística.  
Cada decisión está basada en:

EV = p̂ × R − (1 − p̂) × L  

Si EV > 0, Gemini apuesta; de lo contrario, pasa la ronda.  

Inspirado en el sistema Oscar Grind y la teoría de utilidad esperada,  
adaptado al contexto de trading probabilístico.  

---

## 🧪 Protocolo de Validación

1. Cada cambio de módulo debe pasar pruebas en datasets bull y bear.  
2. Commit unitario por feature (feat:, fix:, test:, refactor:).  
3. WinRate esperado > 52% con fees simulados.  
4. Los resultados se almacenan en casino_results.csv.  

---

## 🛠️ Requisitos

- Python 3.10 o superior  
- Librerías recomendadas:  
  pip install pandas numpy matplotlib  
- (Opcional) pytest para pruebas unitarias  

---

## 🧩 Próximos pasos

- [ ] Implementar TableRealtime con API REST/WebSocket.  
- [ ] Agregar ExchangeProfile dinámico (Binance, OKX, Bybit).  
- [ ] Incorporar StrategyDashboard para visualización del rendimiento.  
- [ ] Conectar múltiples jugadores (Gemini A, B, C).  

---

## 📜 Licencia

Proyecto de investigación y experimentación personal.  
Uso libre con atribución al autor original.  

“La casa siempre gana… excepto cuando la estadística está de tu lado.” 🎲  
