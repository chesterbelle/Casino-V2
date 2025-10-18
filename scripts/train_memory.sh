#!/bin/bash
################################################################################
# 🧠 Script de Entrenamiento de Memoria (GHOST Mode)
################################################################################
#
# Entrena la memoria del sistema con datos históricos en modo GHOST.
# NO apuesta dinero real, solo aprende los winrates de cada estrategia.
#
# Uso:
#   ./scripts/train_memory.sh [dataset_pattern]
#
# Ejemplos:
#   ./scripts/train_memory.sh                          # Todos los datasets
#   ./scripts/train_memory.sh "*training.csv"          # Solo training
#   ./scripts/train_memory.sh "BTCUSDT*.csv"           # Solo BTC
#
################################################################################

set -e

echo "=================================="
echo "🧠 ENTRENAMIENTO DE MEMORIA (GHOST MODE)"
echo "=================================="
echo ""

# Patrón de datasets (default: todos los training)
PATTERN="${1:-*_training.csv}"
DATA_DIR="tables/data/raw"

# Buscar datasets
DATASETS=($(ls $DATA_DIR/$PATTERN 2>/dev/null))

if [ ${#DATASETS[@]} -eq 0 ]; then
    echo "❌ No se encontraron datasets con patrón: $PATTERN"
    echo "   Directorio: $DATA_DIR"
    echo ""
    echo "💡 Ejecuta primero: ./scripts/download_training_data.sh"
    exit 1
fi

echo "📊 Datasets encontrados: ${#DATASETS[@]}"
for ds in "${DATASETS[@]}"; do
    echo "  - $(basename $ds)"
done
echo ""

# Backup del config actual
if [ -f "config.py" ]; then
    echo "💾 Creando backup de config.py..."
    cp config.py config.py.backup
    echo "  ✅ Backup guardado: config.py.backup"
fi
echo ""

# Crear config temporal para entrenamiento
echo "⚙️  Configurando modo GHOST (solo entrenamiento)..."
cat > config_training.py << 'EOF'
# Configuración temporal para ENTRENAMIENTO DE MEMORIA
# Generado automáticamente por train_memory.sh

import os
from config import *  # Importar config base

# ====================
# MODO ENTRENAMIENTO
# ====================
MODE = "backtest"
FORCE_GHOST_ALL = True  # SOLO GHOST, no apuesta real

# Dataset será configurado dinámicamente por el script
# DATASET_PATH se setea al ejecutar

# ====================
# SENSORES: TODOS ACTIVOS
# ====================
ACTIVE_SENSORS = {
    # Mean Reversion (8)
    "RSIReversion": True,
    "BollingerTouch": True,
    "KeltnerReversion": True,
    "StochasticReversion": True,
    "BollingerSqueeze": True,
    "WilliamsRReversion": True,
    "CCIReversion": True,
    "ZScoreReversion": True,
    
    # Momentum/Trend (5)
    "EMACrossover": True,
    "MACDCrossover": True,
    "Supertrend": True,
    "ADXFilter": True,
    "ParabolicSAR": True,
    
    # Volume (4)
    "OBVBreakout": True,
    "VWAPDeviation": True,
    "MFIReversion": True,
    "AccumulationDistribution": True,
}

# ====================
# MEMORIA: CONFIGURACIÓN PARA ENTRENAMIENTO
# ====================
MIN_SUPPORT = 500           # Necesita 500 trades antes de aprobar
MEMORY_WINDOW = 500         # Ventana de memoria
AUTOSAVE_INTERVAL = 50      # Guardar cada 50 trades

# ====================
# BAYESIAN: MÁS ESTRICTO
# ====================
BAYES_CREDIBILITY_THRESHOLD = 0.7  # 70% confianza mínima

print("=" * 60)
print("⚙️  CONFIGURACIÓN: MODO ENTRENAMIENTO (GHOST)")
print("=" * 60)
print(f"  FORCE_GHOST_ALL: {FORCE_GHOST_ALL}")
print(f"  MIN_SUPPORT: {MIN_SUPPORT}")
print(f"  SENSORES ACTIVOS: {len(ACTIVE_SENSORS)}")
print("=" * 60)
EOF

echo "  ✅ Config de entrenamiento creado"
echo ""

# Ejecutar entrenamiento para cada dataset
TOTAL=${#DATASETS[@]}
CURRENT=0
FAILED=0

echo "🚀 Iniciando entrenamiento..."
echo ""

for DATASET in "${DATASETS[@]}"; do
    CURRENT=$((CURRENT + 1))
    DATASET_NAME=$(basename "$DATASET")
    
    echo "[$CURRENT/$TOTAL] Entrenando con: $DATASET_NAME"
    echo "  📊 Procesando velas..."
    
    # Configurar DATASET_PATH temporalmente
    export DATASET_PATH="$DATASET"
    
    # Ejecutar training
    if python3 -c "
import sys
sys.path.insert(0, '.')
import config_training as config
config.DATASET_PATH = '$DATASET'

# Ejecutar main con config de training
import main
" 2>&1 | tee "logs/training_${DATASET_NAME%.csv}.log"; then
        echo "  ✅ Entrenamiento completado"
    else
        echo "  ❌ Error en entrenamiento"
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

# Limpiar config temporal
rm -f config_training.py

echo "=================================="
echo "📊 RESUMEN DE ENTRENAMIENTO"
echo "=================================="
echo "  Datasets procesados: $TOTAL"
echo "  Exitosos: $((TOTAL - FAILED))"
echo "  Fallidos: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ ¡Entrenamiento completado!"
    echo ""
    echo "📁 Memoria guardada en:"
    echo "   gemini/data/memory_log.csv"
    echo "   gemini/data/memory_state.json"
    echo ""
    echo "📊 Revisar estadísticas:"
    echo "   python3 scripts/analyze_memory.py"
    echo ""
    echo "🎯 Próximo paso:"
    echo "   ./scripts/validate_strategies.sh"
else
    echo "⚠️  Algunos entrenamientos fallaron"
    echo "   Revisa los logs en: logs/"
fi

# Restaurar config original
if [ -f "config.py.backup" ]; then
    echo ""
    echo "💾 Config original preservado en: config.py.backup"
    echo "   (El actual config.py no fue modificado)"
fi

echo "=================================="
