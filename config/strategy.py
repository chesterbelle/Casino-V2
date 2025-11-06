"""
====================================================
🧠 CONFIGURACIÓN DE ESTRATEGIA — CASINO V2
====================================================

Parámetros de Gemini y estrategias de trading.
"""

# =====================================================
# 🧠 GEMINI — PARÁMETROS DE APRENDIZAJE
# =====================================================

# Ventana de aprendizaje (cuántos resultados recuerda por bucket)
WINDOW_SIZE = 120

# Mínimo de muestras necesarias por bucket para confiar en la estadística
MIN_SUPPORT = 20

# Fracción del criterio de Kelly a aplicar (1 = Kelly completo, 0.5 = medio Kelly)
# Para live trading, usar valores conservadores
KELLY_FRACTION = 0.1  # Más conservador para live trading


# =====================================================
# 📊 PARÁMETROS BAYESIANOS
# =====================================================

# Umbral de credibilidad para considerar una estrategia confiable
BAYES_CREDIBILITY_THRESHOLD = 0.7

# Percentil inferior para cálculo conservador
BAYES_LOWER_PERCENTILE = 0.05

# Priors bayesianos (alpha, beta)
BAYES_ALPHA = 1.0
BAYES_BETA = 1.0

# Umbral mínimo de ventaja estadística
EDGE_THRESHOLD = 0.01  # 1% de ventaja mínima
