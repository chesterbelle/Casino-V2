"""
====================================================
💰 CONFIGURACIÓN DE TRADING — CASINO V2
====================================================

Parámetros financieros y de gestión de riesgo.
"""

# =====================================================
# 💰 CONFIGURACIÓN FINANCIERA
# =====================================================

# Capital inicial con el que empieza el jugador
# En live trading, se sincroniza con el balance real del exchange
STARTING_BALANCE = 10_000.0

# Tamaños relativos de TP y SL (expresados en proporción decimal)
# Proven values from 90-day backtest (50.8% WR, +0.25% PnL)
TAKE_PROFIT = 0.01  # 1.0% target
STOP_LOSS = 0.01  # 1.0% stop

# Time-Based Exit (Optimization Alignment)
MAX_HOLD_BARS = 120  # Close trade after 120 candles (2 hours) if no TP/SL hit


# =====================================================
# 🪙 PERFIL DEL CASINO (GENERAL)
# =====================================================

# Configuración básica de trading
MAX_LEVERAGE = 50  # máximo apalancamiento permitido
MAX_POSITION_SIZE = 0.08  # tamaño máximo conservador (8% del equity)
COMMISSION_RATE = 0.00035  # Hyperliquid taker fee (0.035%)
SLIPPAGE_DEFAULT = 0.0003  # spread estimado
MAINTENANCE_MARGIN_RATE = 0.003  # margen de mantenimiento (0.3%)
DEFAULT_MARGIN_TYPE = "ISOLATED"  # Opciones: ISOLATED, CROSSED


# =====================================================
# 🚪 EXIT STRATEGY (Dynamic Exit Management)
# =====================================================

# --- Trailing Stop ---
# Dynamic SL that follows price when it moves in favor
TRAILING_STOP_ENABLED = True
TRAILING_STOP_ACTIVATION_PCT = 0.005  # Activate after 0.5% profit
TRAILING_STOP_DISTANCE_PCT = 0.003  # Maintain 0.3% distance from peak

# --- Breakeven ---
# Move SL to entry price to secure risk-free trade
BREAKEVEN_ENABLED = True
BREAKEVEN_ACTIVATION_PCT = 0.003  # Move to BE after 0.3% profit

# --- Signal Reversal ---
# Close position if a strong opposite signal is detected
SIGNAL_REVERSAL_ENABLED = True
SIGNAL_REVERSAL_THRESHOLD = 0.8  # Confidence threshold for reversal signal

# --- Time-Based ---
# (Already defined above as MAX_HOLD_BARS)
