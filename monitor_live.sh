#!/bin/bash
# Monitor del sistema live trading

echo "🔍 Monitoreando sistema live trading..."
echo ""

# Buscar proceso Python
PID=$(pgrep -f "main.py --symbol=LTC")
if [ -z "$PID" ]; then
    echo "❌ No se encontró proceso activo"
    exit 1
fi

echo "✅ Proceso encontrado: PID $PID"
echo ""

# Mostrar últimas líneas del output
echo "📊 Últimas líneas de output:"
echo "---"
tail -50 /proc/$PID/fd/1 2>/dev/null || echo "No se puede leer output directo"
echo ""

# Información del proceso
echo "💻 Info del proceso:"
ps aux | grep $PID | grep -v grep
echo ""

echo "⏰ Tiempo de ejecución:"
ps -p $PID -o etime=
