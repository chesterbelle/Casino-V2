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
# Ejemplo: 0.01 = 1% de take profit, 0.008 = 0.8% de stop loss
TAKE_PROFIT = 0.005  # 0.5% - Take profit más ajustado
STOP_LOSS = 0.015  # 1.5% - Stop loss más amplio (ratio 1:3)


# =====================================================
# 🪙 PERFIL DEL CASINO (GENERAL)
# =====================================================

# Configuración básica de trading
MAX_LEVERAGE = 50  # máximo apalancamiento permitido
MAX_POSITION_SIZE = 0.02  # tamaño máximo conservador (2% del equity)
COMMISSION_RATE = 0.0005  # taker fee (0.05%)
SLIPPAGE_DEFAULT = 0.0003  # spread estimado
MAINTENANCE_MARGIN_RATE = 0.003  # margen de mantenimiento (0.3%)
DEFAULT_MARGIN_TYPE = "ISOLATED"  # Opciones: ISOLATED, CROSSED
