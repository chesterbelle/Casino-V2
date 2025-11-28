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
# Asymmetric ratio based on MFE/MAE: TP=0.3% (71% of avg MFE=0.42%), SL=0.6% (2.1x avg MAE=0.28%)
# Gives signals room to breathe while capturing realistic profit targets
TAKE_PROFIT = 0.003  # 0.3% target (conservative, captures 71% of typical favorable move)
STOP_LOSS = 0.006  # 0.6% stop (generous, allows 2x typical adverse move)


# =====================================================
# 🪙 PERFIL DEL CASINO (GENERAL)
# =====================================================

# Configuración básica de trading
MAX_LEVERAGE = 50  # máximo apalancamiento permitido
MAX_POSITION_SIZE = 0.08  # tamaño máximo conservador (8% del equity)
COMMISSION_RATE = 0.0005  # taker fee (0.05%)
SLIPPAGE_DEFAULT = 0.0003  # spread estimado
MAINTENANCE_MARGIN_RATE = 0.003  # margen de mantenimiento (0.3%)
DEFAULT_MARGIN_TYPE = "ISOLATED"  # Opciones: ISOLATED, CROSSED
