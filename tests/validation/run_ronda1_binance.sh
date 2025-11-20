#!/bin/sh
set -euo pipefail

# Ronda 1 - Binace (10 velas)
# - Ejecuta demo trading por ~10 velas (modo demo/testnet configurado)
# - Descarga datos históricos de Binance para el rango
# - Ejecuta backtest con los datos descargados
# - Compara resultados

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

echo "[ronda1] Iniciando Ronda 1 (Binance)"

# Paths
DEMO_LOGS_DIR="logs"
HIST_DATA="data/validation/historical_ronda1.csv"
BACKTEST_LOGS_DIR="logs"
COMPARISON_LOG="logs/comparison_ronda1.txt"

# 1) Ejecutar demo trading con los flags indicados por el usuario
echo "[ronda1] Ejecutando demo trading (10 velas)"
./.venv/bin/python main.py --mode=demo --exchange=binance --player=paroli --symbol=LTC/USDT:USDT --interval=1m --max-candles=10 || true

# Intenta detectar el último demo log generado
DEMO_LOG=$(ls -t ${DEMO_LOGS_DIR}/demo_*.json 2>/dev/null | head -n1 || true)
if [ -z "$DEMO_LOG" ]; then
  echo "[ronda1] No se encontró demo log en ${DEMO_LOGS_DIR}. Continúo, pero revisa la ejecución demo."
else
  echo "[ronda1] Demo log: $DEMO_LOG"
fi

# 2) Extraer timestamps del demo log (si existe)
if [ -n "$DEMO_LOG" ] && [ -f "$DEMO_LOG" ]; then
  echo "[ronda1] Extrayendo timestamps del demo log"
  python - <<'PY'
import json,sys
p='${DEMO_LOG}'
with open(p) as f:
    data=json.load(f)
# asumimos que el log tiene campo 'candles' o entradas con 'timestamp'
ts=[]
for entry in data.get('events', []) + (data.get('candles', []) if isinstance(data.get('candles', []), list) else []):
    if isinstance(entry, dict) and 'timestamp' in entry:
        ts.append(entry['timestamp'])
if ts:
    print(ts[0], ts[-1])
PY
fi

# 3) Descargar datos históricos de Binance para la ventana (si no existe el script de descarga, usar placeholder)
echo "[ronda1] Descargando datos históricos de Binance (si es necesario) -> ${HIST_DATA}"
python tests/validation/download_historical_data.py --exchange binance --symbol BTC/USDT --interval 1m --limit 100 --out ${HIST_DATA} || echo "[ronda1] download script devolvió error o no existe; revisar tests/validation/download_historical_data.py"

# 4) Ejecutar backtest con los datos descargados
echo "[ronda1] Ejecutando backtest con ${HIST_DATA}"
./.venv/bin/python main.py --mode=backtest --player=paroli --data=${HIST_DATA} --initial-balance=10000 || true

# 5) Comparar resultados (intenta usar compare_results.py)
echo "[ronda1] Comparando resultados"
python tests/validation/compare_results.py --demo-log ${DEMO_LOG:-} --backtest-log ${BACKTEST_LOGS_DIR}/backtest_*.json --out ${COMPARISON_LOG} || echo "[ronda1] compare script devolvió error o no existe; revisar tests/validation/compare_results.py"

echo "[ronda1] Finalizado. Revisa ${COMPARISON_LOG} y los logs en logs/."

exit 0
