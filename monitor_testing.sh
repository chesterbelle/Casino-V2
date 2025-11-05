#\!/bin/bash
while true; do
    clear
    echo "=== TESTING MODE MONITOR ==="
    echo ""
    echo "Candles procesadas:"
    grep "New candle received" testing_60_v2.log | wc -l
    echo ""
    echo "Órdenes ejecutadas:"
    grep "Orden creada" testing_60_v2.log | wc -l
    echo ""
    echo "Último progreso:"
    grep "Progress" testing_60_v2.log | tail -1
    echo ""
    echo "Última orden:"
    grep "Orden ejecutada" testing_60_v2.log | tail -1
    echo ""
    sleep 30
done
