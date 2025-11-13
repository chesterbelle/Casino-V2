#!/bin/bash

# =========================================================
# 🎯 EJECUTOR DE RONDA 1 CON MONITOR INTELIGENTE
# =========================================================
# Ejecuta Ronda 1 (30 velas) con monitoreo automático de errores

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}🎯 RONDA 1 DE VALIDACIÓN - 30 VELAS CON MONITOR INTELIGENTE${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Verificar que no hay procesos previos
if pgrep -f "main.py" > /dev/null; then
    echo -e "${YELLOW}⚠️ Detectado proceso main.py previo, cancelando...${NC}"
    pkill -f "main.py"
    sleep 2
fi

if pgrep -f "monitor_testing.sh" > /dev/null; then
    echo -e "${YELLOW}⚠️ Detectado monitor previo, cancelando...${NC}"
    pkill -f "monitor_testing.sh"
    sleep 1
fi

echo -e "${GREEN}🚀 Iniciando Ronda 1 de validación...${NC}"
echo -e "${GREEN}📊 Configuración:${NC}"
echo -e "   🏦 Exchange: Binance Testnet"
echo -e "   📈 Símbolo: LTC/USDT:USDT"
echo -e "   ⏱️ Intervalo: 1m"
echo -e "   🕯️ Velas: 30"
echo -e "   🔍 Monitor: Activo (cancela automáticamente si hay errores)"
echo ""

# Iniciar el proceso principal en background
echo -e "${GREEN}🎯 Iniciando proceso principal...${NC}"
PYTHONPATH=/home/chesterbelle/Casino-V2 CASINO_EXCHANGE=BINANCE .venv/bin/python main.py \
    --mode=demo \
    --symbol=LTC/USDT:USDT \
    --interval=1m \
    --max-candles=30 &

MAIN_PID=$!
echo -e "${GREEN}✅ Proceso iniciado con PID: $MAIN_PID${NC}"

# Esperar un momento para que se genere el log
sleep 3

# Iniciar el monitor en una nueva terminal o en background
echo -e "${GREEN}🔍 Iniciando monitor inteligente...${NC}"
echo -e "${YELLOW}💡 El monitor cancelará automáticamente si detecta errores críticos${NC}"
echo -e "${YELLOW}💡 Presiona Ctrl+C para cancelar manualmente${NC}"
echo ""

# Ejecutar el monitor (esto tomará el control de la terminal)
./monitor_testing.sh

# Si llegamos aquí, el monitor terminó
echo ""
echo -e "${GREEN}✅ Ronda 1 completada o cancelada${NC}"

# Verificar si el proceso principal sigue corriendo
if kill -0 "$MAIN_PID" 2>/dev/null; then
    echo -e "${YELLOW}⚠️ Proceso principal aún activo, cancelando...${NC}"
    kill -TERM "$MAIN_PID" 2>/dev/null
    sleep 2
    if kill -0 "$MAIN_PID" 2>/dev/null; then
        kill -KILL "$MAIN_PID" 2>/dev/null
    fi
fi

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}🎯 RONDA 1 FINALIZADA${NC}"
echo -e "${BLUE}============================================================${NC}"
