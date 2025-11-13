#!/bin/bash
# Ronda 2: Validación con 30 velas
# Duración: ~30 minutos
#
# FLUJO CORRECTO:
# 1. Ejecutar demo (30 velas en tiempo real, ~30 min) - Binance Testnet
# 2. Extraer timestamps de las velas REALMENTE procesadas
# 3. Descargar esas velas específicas de Binance
# 4. Ejecutar backtest con esas velas
# 5. Comparar resultados

set -e  # Exit on error

echo "================================================================================"
echo "🎯 RONDA 2: Validación con 30 velas (VERSIÓN CORRECTA)"
echo "================================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# PASO 1: DEMO TRADING (30 velas en tiempo real)
# ============================================================================
echo -e "${YELLOW}📊 PASO 1: Ejecutando demo trading (30 velas, ~30 minutos)...${NC}"
echo -e "${BLUE}⏰ Esto tomará aproximadamente 30 minutos reales${NC}"
echo -e "${BLUE}   Cada vela = 1 minuto de tiempo real${NC}"
echo -e "${BLUE}   Exchange: Binance Testnet${NC}"
echo ""

.venv/bin/python main.py \
    --mode=demo \
    --exchange=binance \
    --player=paroli \
    --symbol=LTC/USD:USD \
    --interval=1m \
    --max-candles=30

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

# Calculate start time (30 minutes before end)
# El demo procesó 30 velas de 1 minuto = 30 minutos atrás
START_TIME=$(.venv/bin/python -c "
from datetime import datetime, timedelta
end = datetime.fromisoformat('$END_TIMESTAMP')
start = end - timedelta(minutes=30)
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
    --exchange binance \
    --symbol LTC/USDT:USDT \
    --interval 1m \
    --start "$START_TIME" \
    --end "$END_TIME" \
    --output data/validation/historical_ronda2.csv

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Descarga de datos históricos falló${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Datos históricos descargados${NC}"
echo ""

# Verify we have 30 candles
CANDLE_COUNT=$(wc -l < data/validation/historical_ronda2.csv)
CANDLE_COUNT=$((CANDLE_COUNT - 1))  # Subtract header
echo -e "${GREEN}📊 Velas descargadas: $CANDLE_COUNT${NC}"
echo ""

# ============================================================================
# PASO 4: BACKTEST
# ============================================================================
echo -e "${YELLOW}🎮 PASO 4: Ejecutando backtest con los mismos datos...${NC}"
echo ""

.venv/bin/python main.py \
    --mode=backtest \
    --player=paroli \
    --data=data/validation/historical_ronda2.csv \
    --max-candles=30 \
    --initial-balance=$INITIAL_BALANCE

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Backtest falló${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Backtest completado${NC}"
echo ""

# Get the latest backtest log
BACKTEST_LOG=$(ls -t logs/backtest_*.json 2>/dev/null | head -1)
echo "📄 Log de backtest: $BACKTEST_LOG"
echo ""

# ============================================================================
# PASO 5: COMPARAR RESULTADOS
# ============================================================================
echo -e "${YELLOW}📊 PASO 5: Comparando resultados...${NC}"
echo ""

.venv/bin/python tests/validation/compare_results.py \
    --testing $DEMO_LOG \
    --backtest $BACKTEST_LOG \
    --output logs/comparison_ronda2.txt

COMPARISON_EXIT=$?

echo ""
if [ $COMPARISON_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ VALIDACIÓN EXITOSA${NC}"
    echo -e "${GREEN}   Todas las métricas están dentro de tolerancia${NC}"
else
    echo -e "${RED}❌ VALIDACIÓN FALLIDA${NC}"
    echo -e "${RED}   Algunas métricas están fuera de tolerancia${NC}"
fi

echo ""
echo "================================================================================"
echo "📋 RESUMEN RONDA 2"
echo "================================================================================"
echo ""
echo "📄 Logs generados:"
echo "   Demo:       $DEMO_LOG"
echo "   Backtest:   $BACKTEST_LOG"
echo "   Comparison: logs/comparison_ronda2.txt"
echo ""
echo "📊 Datos históricos:"
echo "   Archivo: data/validation/historical_ronda2.csv"
echo "   Velas:   $CANDLE_COUNT"
echo ""
echo "================================================================================"

exit $COMPARISON_EXIT
