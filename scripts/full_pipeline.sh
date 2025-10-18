#!/bin/bash
################################################################################
# 🚀 Pipeline Completo de Entrenamiento y Validación
################################################################################
#
# Ejecuta todo el proceso automatizado:
# 1. Descarga datos
# 2. Entrena memoria
# 3. Analiza resultados
# 4. Valida estrategias
#
# Uso:
#   ./scripts/full_pipeline.sh
#
################################################################################

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║     🎰 CASINO V2 - PIPELINE COMPLETO DE ENTRENAMIENTO         ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Crear directorios necesarios
mkdir -p logs
mkdir -p results
mkdir -p tables/data/raw

# Timestamp
START_TIME=$(date +%s)
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

echo "⏰ Inicio: $TIMESTAMP"
echo ""

# ============================================================================
# FASE 1: DESCARGA DE DATOS
# ============================================================================

echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ FASE 1: DESCARGA DE DATOS                                     │"
echo "└────────────────────────────────────────────────────────────────┘"
echo ""

if ./scripts/download_training_data.sh; then
    echo "✅ Fase 1 completada"
else
    echo "❌ Error en Fase 1"
    exit 1
fi

echo ""
read -p "⏸️  Presiona ENTER para continuar con Fase 2..."
echo ""

# ============================================================================
# FASE 2: ENTRENAMIENTO DE MEMORIA
# ============================================================================

echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ FASE 2: ENTRENAMIENTO DE MEMORIA (GHOST MODE)                 │"
echo "└────────────────────────────────────────────────────────────────┘"
echo ""

if ./scripts/train_memory.sh; then
    echo "✅ Fase 2 completada"
else
    echo "❌ Error en Fase 2"
    exit 1
fi

echo ""
read -p "⏸️  Presiona ENTER para continuar con Fase 3..."
echo ""

# ============================================================================
# FASE 3: ANÁLISIS DE MEMORIA
# ============================================================================

echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ FASE 3: ANÁLISIS DE MEMORIA                                   │"
echo "└────────────────────────────────────────────────────────────────┘"
echo ""

if python3 scripts/analyze_memory.py; then
    echo "✅ Fase 3 completada"
else
    echo "❌ Error en Fase 3"
    exit 1
fi

echo ""
read -p "⏸️  Presiona ENTER para continuar con Fase 4..."
echo ""

# ============================================================================
# FASE 4: VALIDACIÓN DE ESTRATEGIAS
# ============================================================================

echo "┌────────────────────────────────────────────────────────────────┐"
echo "│ FASE 4: VALIDACIÓN DE ESTRATEGIAS (BET MODE)                  │"
echo "└────────────────────────────────────────────────────────────────┘"
echo ""

if ./scripts/validate_strategies.sh; then
    echo "✅ Fase 4 completada"
else
    echo "❌ Error en Fase 4"
    exit 1
fi

# ============================================================================
# RESUMEN FINAL
# ============================================================================

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║     ✅ PIPELINE COMPLETADO EXITOSAMENTE                        ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "⏱️  Tiempo total: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""
echo "📁 Archivos generados:"
echo "   - Memoria: gemini/data/memory_state.json"
echo "   - Logs: logs/"
echo "   - Resultados: results/"
echo ""
echo "🎯 Próximos pasos:"
echo "   1. Revisar análisis de memoria arriba"
echo "   2. Revisar resultados de validación"
echo "   3. Si todo OK → configurar para live/paper trading"
echo ""
echo "📚 Documentación:"
echo "   - docs/guides/new_sensors_config.md"
echo "   - docs/guides/live-trading.md (próximamente)"
echo ""
echo "════════════════════════════════════════════════════════════════"
