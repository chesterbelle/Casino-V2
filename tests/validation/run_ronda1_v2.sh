#!/bin/bash
# Ronda 1: Validación con 10 velas
# Duración: ~15 minutos
#
# FLUJO CORRECTO:
# 1. Ejecutar demo (10 velas en tiempo real, ~10 min) - Binance Testnet
# 2. Extraer timestamps de las velas REALMENTE procesadas
# 3. Descargar esas velas específicas de Binance
# 4. Ejecutar backtest con esas velas
# 5. Comparar resultados

set -e  # Exit on error

echo "================================================================================"
echo "🎯 RONDA 1: Validación con 10 velas (VERSIÓN CORRECTA)"
echo "================================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# PASO 1: DEMO TRADING (10 velas en tiempo real)
# ============================================================================
echo -e "${YELLOW}📊 PASO 1: Ejecutando demo trading (10 velas, ~10 minutos)...${NC}"
echo -e "${BLUE}⏰ Esto tomará aproximadamente 10 minutos reales${NC}"
echo -e "${BLUE}   Cada vela = 1 minuto de tiempo real${NC}"
echo -e "${BLUE}   Exchange: Binance Testnet${NC}"
echo ""

.venv/bin/python main.py \
    --mode=demo \
    --exchange=binance \
    --player=paroli \
    --symbol=LTC/USD:USD \
    --interval=1m \
    --max-candles=10

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Demo trading falló${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Demo trading completado${NC}"
echo ""

# ============================================================================
# PASO 2: EXTRAER INFORMACIÓN DEL LOG
# ============================================================================
echo -e "${YELLOW}📝 PASO 2: Extrayendo información del demo trading...${NC}"
echo ""

# Get the latest demo log
DEMO_LOG=$(ls -t logs/demo_*.json 2>/dev/null | head -1)

if [ -z "$DEMO_LOG" ]; then
    echo -e "${RED}❌ No se encontró log de demo trading${NC}"
    exit 1
fi

echo "📄 Log de demo: $DEMO_LOG"

# Extract initial balance
INITIAL_BALANCE=$(.venv/bin/python -c "import json; print(json.load(open('$DEMO_LOG'))['initial_balance'])")
echo -e "${GREEN}💰 Balance inicial: \$$INITIAL_BALANCE${NC}"

# Extract timestamp (cuando TERMINÓ el demo)
END_TIMESTAMP=$(.venv/bin/python -c "import json; print(json.load(open('$DEMO_LOG'))['timestamp'])")
echo "📅 Demo trading terminó: $END_TIMESTAMP"

# Calculate start time (10 minutes before end)
# El demo procesó 10 velas de 1 minuto = 10 minutos atrás
START_TIME=$(.venv/bin/python -c "
from datetime import datetime, timedelta
end = datetime.fromisoformat('$END_TIMESTAMP')
start = end - timedelta(minutes=10)
print(start.strftime('%Y-%m-%d %H:%M:%S'))
")

END_TIME=$(.venv/bin/python -c "
from datetime import datetime
end = datetime.fromisoformat('$END_TIMESTAMP')
print(end.strftime('%Y-%m-%d %H:%M:%S'))
")

echo -e "${GREEN}📊 Período de las velas procesadas:${NC}"
echo "   Inicio: $START_TIME"
echo "   Fin:    $END_TIME"
echo ""

# ============================================================================
# PASO 3: DESCARGAR DATOS HISTÓRICOS
# ============================================================================
echo -e "${YELLOW}📥 PASO 3: Descargando datos históricos del período exacto...${NC}"
echo ""

.venv/bin/python tests/validation/download_historical_data.py \
    --start "$START_TIME" \
    --end "$END_TIME" \
    --symbol LTC/USD:USD \
    --interval 1m \
    --exchange binance \
    --output data/validation/historical_ronda1.csv

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Descarga de datos falló${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Datos históricos descargados${NC}"
echo ""

# Verify we got the right number of candles
CANDLE_COUNT=$(.venv/bin/python -c "
import pandas as pd
df = pd.read_csv('data/validation/historical_ronda1.csv')
print(len(df))
")

echo -e "${BLUE}📊 Velas descargadas: $CANDLE_COUNT${NC}"

if [ "$CANDLE_COUNT" -lt 8 ]; then
    echo -e "${RED}⚠️  ADVERTENCIA: Se esperaban ~10 velas, se obtuvieron $CANDLE_COUNT${NC}"
    echo -e "${YELLOW}   Esto puede afectar la comparación${NC}"
fi

echo ""

# ============================================================================
# PASO 4: EJECUTAR BACKTEST
# ============================================================================
echo -e "${YELLOW}🎮 PASO 4: Ejecutando backtest con los mismos datos...${NC}"
echo ""

.venv/bin/python main.py \
    --mode=backtest \
    --data=data/validation/historical_ronda1.csv \
    --player=paroli \
    --initial-balance=$INITIAL_BALANCE \
    --max-candles=10

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Backtest falló${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Backtest completado${NC}"
echo ""

# Get the latest backtest log
BACKTEST_LOG=$(ls -t logs/backtest_*.json 2>/dev/null | head -1)

if [ -z "$BACKTEST_LOG" ]; then
    echo -e "${RED}❌ No se encontró log de backtest${NC}"
    exit 1
fi

echo "📄 Log de backtest: $BACKTEST_LOG"
echo ""

# ============================================================================
# PASO 5: COMPARAR RESULTADOS
# ============================================================================
echo -e "${YELLOW}📊 PASO 5: Comparando resultados...${NC}"
echo ""

.venv/bin/python tests/validation/compare_results.py \
    --testing "$DEMO_LOG" \
    --backtest "$BACKTEST_LOG" \
    --tolerance 0.5 \
    --output logs/comparison_ronda1.txt

COMPARISON_RESULT=$?

echo ""

# ============================================================================
# RESULTADO FINAL
# ============================================================================
if [ $COMPARISON_RESULT -eq 0 ]; then
    echo -e "${GREEN}================================================================================${NC}"
    echo -e "${GREEN}🎉 RONDA 1 COMPLETADA: ✅ VALIDACIÓN EXITOSA${NC}"
    echo -e "${GREEN}================================================================================${NC}"
    echo ""
    echo -e "${GREEN}✅ El backtesting refleja correctamente el comportamiento de demo trading${NC}"
    echo ""
    echo "📝 Archivos generados:"
    echo "   - Demo:        $DEMO_LOG"
    echo "   - Datos:       data/validation/historical_ronda1.csv ($CANDLE_COUNT velas)"
    echo "   - Backtest:    $BACKTEST_LOG"
    echo "   - Comparación: logs/comparison_ronda1.txt"
    echo ""
    echo -e "${BLUE}🚀 Próximo paso: Ejecutar Ronda 2 (30 velas)${NC}"
    exit 0
else
    echo -e "${RED}================================================================================${NC}"
    echo -e "${RED}❌ RONDA 1 COMPLETADA: VALIDACIÓN FALLIDA${NC}"
    echo -e "${RED}================================================================================${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Las métricas están fuera de tolerancia${NC}"
    echo ""
    echo "📝 Revisar:"
    echo "   - Demo:        $DEMO_LOG"
    echo "   - Datos:       data/validation/historical_ronda1.csv ($CANDLE_COUNT velas)"
    echo "   - Backtest:    $BACKTEST_LOG"
    echo "   - Comparación: logs/comparison_ronda1.txt"
    echo ""
    echo -e "${YELLOW}🔍 Analizar diferencias antes de continuar a Ronda 2${NC}"
    exit 1
fi
