#!/bin/bash
################################################################################
# ✅ Script de Validación de Estrategias
################################################################################
#
# Valida las estrategias entrenadas ejecutando backtests REALES (con BET).
# Usa walk-forward testing para evitar overfitting.
#
# Uso:
#   ./scripts/validate_strategies.sh
#
################################################################################

set -e

echo "=================================="
echo "✅ VALIDACIÓN DE ESTRATEGIAS"
echo "=================================="
echo ""

# Buscar datasets de validación
VALIDATION_PATTERN="*_15m_*.csv"
DATA_DIR="tables/data/raw"

DATASETS=($(ls $DATA_DIR/$VALIDATION_PATTERN 2>/dev/null | head -n 3))

if [ ${#DATASETS[@]} -eq 0 ]; then
    echo "❌ No se encontraron datasets para validación"
    exit 1
fi

echo "📊 Datasets de validación:"
for ds in "${DATASETS[@]}"; do
    echo "  - $(basename $ds)"
done
echo ""

# Verificar que la memoria existe
if [ ! -f "gemini/data/memory_state.json" ]; then
    echo "❌ No se encontró memoria entrenada"
    echo "   Ejecuta primero: ./scripts/train_memory.sh"
    exit 1
fi

echo "🧠 Memoria encontrada:"
python3 << 'EOF'
import json
with open("gemini/data/memory_state.json", "r") as f:
    state = json.load(f)
    strategies = state.get("strategies", {})
    print(f"  Total estrategias: {len(strategies)}")
    
    # Estrategias con datos suficientes
    approved = [s for s, d in strategies.items() if d.get("wins", 0) + d.get("losses", 0) >= 500]
    print(f"  Estrategias aprobadas (>=500 trades): {len(approved)}")
    
    if approved:
        print(f"\n  Top 5 por winrate:")
        sorted_strats = sorted(
            [(s, d.get("winrate", 0)) for s, d in strategies.items() if s in approved],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        for name, wr in sorted_strats:
            print(f"    - {name[:50]:50s}: {wr:.2%}")
EOF

echo ""
echo "🚀 Iniciando validación con BET real..."
echo ""

# Ejecutar validación
TOTAL=${#DATASETS[@]}
CURRENT=0

RESULTS_DIR="results/validation_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

for DATASET in "${DATASETS[@]}"; do
    CURRENT=$((CURRENT + 1))
    DATASET_NAME=$(basename "$DATASET")
    
    echo "[$CURRENT/$TOTAL] Validando con: $DATASET_NAME"
    
    # Ejecutar con BET (no GHOST)
    python3 << EOF | tee "$RESULTS_DIR/validation_${DATASET_NAME%.csv}.txt"
import sys
sys.path.insert(0, '.')
import config
config.MODE = "backtest"
config.DATASET_PATH = "$DATASET"
config.STARTING_BALANCE = 10000.0
# NO forzar GHOST - usar BET real

import main
EOF
    
    echo ""
done

echo "=================================="
echo "📊 VALIDACIÓN COMPLETADA"
echo "=================================="
echo ""
echo "📁 Resultados guardados en:"
echo "   $RESULTS_DIR/"
echo ""
echo "🎯 Analizar resultados:"
echo "   cat $RESULTS_DIR/*.txt | grep 'Balance final\\|Winrate\\|Trades'"
echo ""
echo "=================================="
