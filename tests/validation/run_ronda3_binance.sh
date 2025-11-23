#!/bin/sh
set -euo pipefail

# Ronda 3 - Binance (60 velas)
ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

echo "[ronda3] Iniciando Ronda 3 (Binance)"

# Paths
DEMO_LOGS_DIR="logs"
HIST_DATA="data/validation/historical_ronda3.csv"
BACKTEST_LOGS_DIR="logs"
COMPARISON_LOG="logs/comparison_ronda3.txt"

# 1) Ejecutar demo trading
echo "[ronda3] Ejecutando demo trading (60 velas)"
./.venv/bin/python main.py --mode=demo --exchange=binance --player=paroli --symbol=LTC/USDT:USDT --interval=1m --max-candles=60 || true

# Detectar último demo log
DEMO_LOG=$(ls -t ${DEMO_LOGS_DIR}/demo_*.json 2>/dev/null | head -n1 || true)
if [ -z "$DEMO_LOG" ]; then
  echo "[ronda3] No se encontró demo log"
else
  echo "[ronda3] Demo log: $DEMO_LOG"
fi

# 2) Extraer timestamps y calcular fechas
if [ -n "$DEMO_LOG" ] && [ -f "$DEMO_LOG" ]; then
  echo "[ronda3] Extrayendo timestamps del demo log"
  TIMESTAMPS=$(python3 - "$DEMO_LOG" <<'PY'
import json, sys
from datetime import datetime

log_path = sys.argv[1]
with open(log_path) as f:
    data = json.load(f)

ts_list = []
for event in data.get('events', []):
    if isinstance(event, dict) and 'timestamp' in event:
        ts_list.append(event['timestamp'])

if ts_list:
    first_ts = min(ts_list)
    last_ts = max(ts_list)
    start_dt = datetime.fromtimestamp(first_ts / 1000)
    end_dt = datetime.fromtimestamp(last_ts / 1000)
    print(f"{start_dt.strftime('%Y-%m-%d %H:%M:%S')} {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
PY
)

  if [ -n "$TIMESTAMPS" ]; then
    START_DATE=$(echo $TIMESTAMPS | cut -d' ' -f1-2)
    END_DATE=$(echo $TIMESTAMPS | cut -d' ' -f3-4)
    echo "[ronda3] Período detectado: $START_DATE → $END_DATE"
  else
    echo "[ronda3] No se encontraron timestamps, usando período por defecto"
    START_DATE=$(date -d '2 hours ago' '+%Y-%m-%d %H:%M:%S')
    END_DATE=$(date '+%Y-%m-%d %H:%M:%S')
  fi
else
  echo "[ronda3] No se encontró demo log, usando período por defecto"
  START_DATE=$(date -d '2 hours ago' '+%Y-%m-%d %H:%M:%S')
  END_DATE=$(date '+%Y-%m-%d %H:%M:%S')
fi

# 3) Descargar datos históricos
echo "[ronda3] Descargando datos históricos → ${HIST_DATA}"
python tests/validation/download_historical_data.py --exchange binance --symbol LTC/USDT --interval 1m --start "$START_DATE" --end "$END_DATE" --output ${HIST_DATA} || echo "[ronda3] download failed"

# 3.5) Extraer balance inicial
if [ -n "$DEMO_LOG" ] && [ -f "$DEMO_LOG" ]; then
  INITIAL_BALANCE=$(python3 - "$DEMO_LOG" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
print(data.get('initial_balance', 10000))
PY
)
  echo "[ronda3] Balance inicial: $INITIAL_BALANCE"
else
  INITIAL_BALANCE=10000
fi

# 4) Backtest
echo "[ronda3] Ejecutando backtest (balance: $INITIAL_BALANCE)"
./.venv/bin/python main.py --mode=backtest --player=paroli --data=${HIST_DATA} --initial-balance=$INITIAL_BALANCE || true

# 5) Comparar
echo "[ronda3] Comparando resultados"
python tests/validation/compare_results.py --demo-log ${DEMO_LOG:-} --backtest-log ${BACKTEST_LOGS_DIR}/backtest_*.json --out ${COMPARISON_LOG} || echo "[ronda3] compare failed"

echo "[ronda3] Finalizado"
exit 0
