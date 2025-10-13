# 🎰 CASINO BINANCE V2 — *La Era Gemini*

> 🧠 Un laboratorio de *trading probabilístico* inspirado en la dinámica de un **casino sin límite de apuesta**.  
> Cada módulo cumple un rol dentro del ecosistema: analistas, jugadores, mesas y crupieres trabajando juntos para buscar ventaja estadística.

![Banner del proyecto](https://img.shields.io/badge/Estado-En%20Desarrollo-yellow)
![Versión](https://img.shields.io/badge/Versión-0.1.1-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![Licencia](https://img.shields.io/badge/Licencia-MIT-lightgrey)

---

## 🧭 Filosofía del Proyecto

En lugar de intentar **predecir el futuro**, el sistema busca **apostar cuando el Valor Esperado (EV)** es positivo.  
Cada módulo representa un rol dentro del casino:

| Rol | Módulo | Descripción |
|------|---------|-------------|
| 🎩 **Gemini (Jugador racional)** | `gemini/` | Evalúa el mercado, estima probabilidad de éxito (*p̂*), y decide cuándo y cuánto apostar según Kelly. |
| 👁️ **Analistas de mesa (Sensores)** | `sensors/` | Detectan contextos técnicos favorables. |
| 🧤 **Crupier** | `croupier/` | Ejecuta las órdenes sin pensar, en modo real o simulado. |
| 🪙 **Mesas** | `tables/` | Proveen datos históricos o en vivo, aplican fees y actualizan balance. |
| 💰 **Cajero (BalanceManager)** | `tables/balance_manager.py` | Administra capital y registra resultados. |
| 🧾 **Protocolo** | `protocolo.md` | Define reglas de desarrollo, validación y testing. |
| 🧑‍💼 **Gerente de sala** | `main.py` | Orquesta la sesión: prepara la mesa, llama a sensores, Gemini y crupier. |

---

## ⚙️ Arquitectura General

```
Gemini → Croupier → Mesa (Feed) → BalanceManager
             ↑                     ↓
         resultado ←――――――――――――――――――――――――
```

---

## 📂 Estructura del Proyecto

```
Casino-V2/
├── main.py
├── config.py
├── gemini/
├── croupier/
├── sensors/
├── tables/
└── utils/
```

---

## 🎯 Filosofía Técnica

El casino no intenta adivinar el mercado — **espera contextos donde las probabilidades están a su favor.**

> “No se trata de ganar todas las manos, sino de apostar cuando la ventaja está del lado del jugador.”

Basado en la ecuación fundamental:

\[
EV = p̂ × R − (1 − p̂) × L
\]

Si el EV > 0 → Gemini apuesta;  
Si no, espera la siguiente ronda.

Inspirado en **Oscar Grind**, **teoría de utilidad esperada**, y **modelos bayesianos** de probabilidad aplicada al trading.

---

## 🚀 Ejecución Rápida

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar el dataset principal
MODE = "backtest"        # o "realtime" cuando esté disponible
DATASET_PATH = "tables/data/raw/LTCUSDT_15min_bull.csv"  # único dataset usado en la sesión

# 3. (Opcional) Activar modo Oscar Grind
ENABLE_OSCAR_MODE = True

# 4. (Recomendado) Actualizar tasas de funding reales
python3 utils/fetch_funding_rates.py --symbol LTCUSDT

# 5. (Opcional) Descargar dataset adicional (ej. ETHUSDT 15m)
python3 utils/download_kline_dataset.py --symbol ETHUSDT --interval 15m --limit 1000 --tag sample

# 6. Correr el casino
python3 main.py
```

Ejemplo de salida:

```
🎯 Dataset: LTCUSDT_15min_bull.csv
💰 Balance final: 10,542.33 USDT
🏆 Winrate: 57.6%
⚙️ Trades ejecutados: 182
👻 GHOST trades: 27
```

---

## 🧩 Próximos pasos

✅ **v0.1.1:** Primera versión funcional del ecosistema completo  
🔜 **v0.2.0:** Integración del modo LIVE (Binance Futures Testnet)  
🔜 **v0.3.0:** Gemini A/B/C (múltiples jugadores con estrategias distintas)  
🔜 **v0.4.0:** Dashboard de rendimiento y análisis visual  

---

## 🧠 Credo del Proyecto

> “La casa siempre gana… excepto cuando la estadística está de tu lado.” 🎲  
> — *Casino V2: La Era Gemini*
