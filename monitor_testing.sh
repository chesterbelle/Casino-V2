#!/bin/bash

# =========================================================
# 🔍 MONITOR SIMPLE DE VALIDACIÓN - RONDA 1 (30 velas)
# =========================================================
# Monitor simple para ver el progreso en tiempo real

# Detectar el log file más reciente
LOG_FILE=$(ls -t logs/main_*.log 2>/dev/null | head -1)

if [[ -z "$LOG_FILE" ]]; then
    echo "❌ No se encontró log file. Asegúrate de que main.py esté ejecutándose."
    exit 1
fi

echo "📝 Monitoreando: $LOG_FILE"
echo ""

while true; do
    clear
    echo "============================================================"
    echo "🔍 MONITOR DE VALIDACIÓN - RONDA 1 (30 velas)"
    echo "============================================================"
    echo ""

    # Velas procesadas
    candles_count=$(grep -c "📊 Received candle" "$LOG_FILE" 2>/dev/null || echo "0")
    echo "🕯️ Velas procesadas:"
    echo "   $candles_count/30 ($(( candles_count * 100 / 30 ))%)"
    echo ""

    # Órdenes ejecutadas
    orders_count=$(grep -c "✅ Orden ejecutada" "$LOG_FILE" 2>/dev/null || echo "0")
    echo "📦 Órdenes ejecutadas:"
    echo "   $orders_count"
    echo ""

    # TP/SL registrados
    tpsl_count=$(grep -c "Registered TP/SL pair" "$LOG_FILE" 2>/dev/null || echo "0")
    echo "🎯 Pares TP/SL registrados:"
    echo "   $tpsl_count"
    echo ""

    # OCO Manual checks
    oco_checks=$(grep -c "OCO Manual.*No active orders" "$LOG_FILE" 2>/dev/null || echo "0")
    echo "🔄 OCO Manual checks:"
    echo "   $oco_checks"
    echo ""

    # Última vela procesada
    echo "🕯️ Última vela:"
    last_candle=$(grep "📊 Received candle" "$LOG_FILE" | tail -1 | cut -d'|' -f1,4- 2>/dev/null || echo "   Ninguna")
    echo "   $last_candle"
    echo ""

    # Última orden ejecutada
    echo "📦 Última orden:"
    last_order=$(grep "✅ Orden ejecutada" "$LOG_FILE" | tail -1 | cut -d'|' -f1,4- 2>/dev/null || echo "   Ninguna")
    echo "   $last_order"
    echo ""

    # Último OCO
    echo "🔄 Último OCO:"
    last_oco=$(grep "OCO Manual" "$LOG_FILE" | tail -1 | cut -d'|' -f1,4- 2>/dev/null || echo "   Ninguna")
    echo "   $last_oco"
    echo ""

    # Errores recientes
    errors=$(grep -i "error\|❌\|failed" "$LOG_FILE" | tail -3 2>/dev/null)
    if [[ -n "$errors" ]]; then
        echo "⚠️ Errores recientes:"
        echo "$errors" | while read -r line; do
            echo "   $(echo "$line" | cut -d'|' -f1,4-)"
        done
        echo ""
    fi

    # Verificar si el proceso sigue corriendo
    if ! pgrep -f "main.py" > /dev/null; then
        echo "❌ Proceso main.py terminó"
        break
    fi

    echo "============================================================"
    echo "⏱️ Actualizando cada 15 segundos... (Ctrl+C para salir)"

    sleep 15
done
