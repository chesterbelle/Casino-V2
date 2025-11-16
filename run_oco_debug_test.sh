#!/bin/bash

# 🔍 Script para ejecutar el test de debug de OCO
# Ejecutar: bash run_oco_debug_test.sh

set -e

echo "╔════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                   🔍 TEST DE DEBUG: EJECUCIÓN DE ORDEN OCO                        ║"
echo "║                                                                                    ║"
echo "║  Este test valida EXACTAMENTE cómo el Croupier ejecuta una orden con TP/SL        ║"
echo "║  y debuguea cada paso para identificar dónde falla el OCO.                        ║"
echo "╚════════════════════════════════════════════════════════════════════════════════════╝"

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo "❌ Error: Ejecutar desde la raíz del proyecto Casino-V2"
    exit 1
fi

# Activar venv si existe
if [ -d ".venv" ]; then
    echo "📌 Activando entorno virtual..."
    source .venv/bin/activate
fi

# Crear directorio de logs si no existe
mkdir -p logs

echo ""
echo "📌 Ejecutando test de debug OCO..."
echo ""

# Ejecutar el test
python tests/test_oco_execution_debug.py

TEST_EXIT_CODE=$?

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════════════╗"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "║                    ✅ TEST COMPLETADO EXITOSAMENTE                              ║"
else
    echo "║                    ❌ TEST FALLÓ - Revisar logs para detalles                   ║"
fi

echo "╚════════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Logs disponibles en: logs/"
echo ""

exit $TEST_EXIT_CODE
