#!/bin/bash
################################################################################
# 📥 Script de Descarga de Datos para Entrenamiento
################################################################################
# 
# Descarga datos históricos de múltiples símbolos para entrenar el sistema.
# 
# Uso:
#   ./scripts/download_training_data.sh
#
################################################################################

set -e  # Exit on error

echo "=================================="
echo "📥 DESCARGA DE DATOS PARA ENTRENAMIENTO"
echo "=================================="
echo ""

# Configuración
SYMBOLS=("BTCUSDT" "ETHUSDT" "LTCUSDT" "BNBUSDT" "SOLUSDT")
INTERVAL="5m"
DAYS=365  # 1 año de datos
TAG="training"

echo "📋 Configuración:"
echo "  Símbolos: ${SYMBOLS[@]}"
echo "  Intervalo: $INTERVAL"
echo "  Días: $DAYS"
echo "  Tag: $TAG"
echo ""

# Verificar que el script de descarga existe
if [ ! -f "utils/download_kline_dataset.py" ]; then
    echo "❌ Error: utils/download_kline_dataset.py no encontrado"
    echo "   Asegúrate de estar en la raíz del proyecto"
    exit 1
fi

# Crear directorio de salida
mkdir -p tables/data/raw

echo "🚀 Iniciando descargas..."
echo ""

# Contador
TOTAL=${#SYMBOLS[@]}
CURRENT=0
FAILED=0

# Descargar cada símbolo
for SYMBOL in "${SYMBOLS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$TOTAL] Descargando $SYMBOL..."
    
    if python3 utils/download_kline_dataset.py \
        --symbol "$SYMBOL" \
        --interval "$INTERVAL" \
        --days $DAYS \
        --tag "$TAG"; then
        echo "  ✅ $SYMBOL descargado exitosamente"
    else
        echo "  ❌ Error descargando $SYMBOL"
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

echo "=================================="
echo "📊 RESUMEN DE DESCARGAS"
echo "=================================="
echo "  Total símbolos: $TOTAL"
echo "  Exitosos: $((TOTAL - FAILED))"
echo "  Fallidos: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ ¡Todas las descargas completadas!"
    echo ""
    echo "📁 Archivos generados:"
    ls -lh tables/data/raw/*_${INTERVAL}_${TAG}.csv 2>/dev/null || echo "  (Ninguno con tag '$TAG')"
    echo ""
    echo "🎯 Próximo paso:"
    echo "   ./scripts/train_memory.sh"
else
    echo "⚠️  Algunas descargas fallaron"
    echo "   Revisa los errores arriba"
fi

echo "=================================="
